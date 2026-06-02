"""
Gold-case evaluation harness.

Runs a fixed set of questions through the real pipeline and checks the answer
against expected facts (regex, case-insensitive, whitespace-normalized). This
is a regression guard: it locks in the category/rate/total/timing behaviour so
a prompt tweak or re-ingest can't silently break it (e.g. the Jaipur
"state capital -> Category B" case that a prompt edit once regressed).

Each case:
  q       : the question
  must    : regex patterns that must ALL appear in the answer
  forbid  : regex patterns that must NOT appear (optional)

Gold values are read straight from the two policy PDFs:
  Domestic rate matrix [A | B | C]
    9/10  LA 4000/2500/2000  BA 1000/750/500  DA 1500/1000/750
    7/8   LA 2500/1800/1200  BA 800/600/450   DA 1200/900/600
    5/6   LA 1800/1200/800   BA 500/400/300   DA 750/600/450
    1-4   LA 1000/700/500    BA 400/300/200   DA 600/450/300
  Foreign DA [A | B | C]
    9&10  250/200/175    8  200/150/125    <=7  125/100/75
"""
import sys
import re
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

from pipelines.rag_pipeline import RAGPipeline


CASES = [
    # ---- Category resolution ----
    {"q": "Which travel category is Delhi?",
     "must": [r"categor\w*\W*'?a'?\b"]},
    {"q": "Can I travel to Jaipur by flight?",
     "must": [r"state capital", r"categor\w*\W*'?b'?\b"]},
    {"q": "Which travel category is Gurgaon for domestic travel?",
     "must": [r"categor\w*\W*'?c'?\b"]},
    {"q": "A Band 9 executive travels to Japan. What is the daily allowance? And Band 8?",
     "must": [r"categor\w*\W*'?a'?", r"\$?\s*250\b", r"\$?\s*200\b"]},
    {"q": "How are USA, Singapore and UAE classified for foreign DA?",
     "must": [r"singapore", r"uae", r"\bb\b"]},
    {"q": "How are Nepal and Bhutan treated for foreign DA?",
     "must": [r"nepal", r"bhutan", r"exclud|not\W+(?:assigned|classif|categor)|no categor"]},

    # ---- Rates (single) ----
    {"q": "For a Band 8 employee staying overnight in Mumbai with a hotel bill, what LA and BA apply?",
     "must": [r"categor\w*\W*'?a'?", r"\b2500\b", r"\b800\b"]},
    {"q": "What own-arrangement daily allowance does a Band 7 employee get in a Category B city?",
     "must": [r"\b900\b"]},
    {"q": "What daily allowance does a Band 9 executive get for travel to the USA?",
     "must": [r"\bb\b", r"\$?\s*200\b"]},

    # ---- Multi-day / multi-city totals ----
    # We assert the per-band GRAND TOTALS, not intermediate subtotals: the grand
    # total is the same number regardless of how the model lays out the table
    # (per-city columns vs per-component subtotals), so it checks the arithmetic
    # is right end-to-end without coupling the test to one presentation.
    # Delhi=A, Jaipur=B (State capital), hotel stay (LA+BA), 3 days each:
    #   9/10 (4000+1000)*3+(2500+750)*3=24750  7/8 (2500+800)*3+(1800+600)*3=17100
    #   5/6  (1800+500)*3+(1200+400)*3=11700   1-4 (1000+400)*3+(700+300)*3=7200
    {"q": "How much is the entitlement for 3 days in Delhi and 3 days in Jaipur?",
     "must": [r"24[,\s]?750", r"17[,\s]?100", r"11[,\s]?700", r"7[,\s]?200"]},
    # Mumbai=A (3 days) + Bangalore=A (2 days), hotel stay (LA+BA):
    #   9/10 5000*5=25000  7/8 3300*5=16500  5/6 2300*5=11500  1-4 1400*5=7000
    {"q": "How much is the entitlement for 3 days in Mumbai and 2 days in Bangalore?",
     "must": [r"25[,\s]?000", r"16[,\s]?500", r"11[,\s]?500", r"7[,\s]?000"]},

    # ---- Timing rules ----
    {"q": "What boarding allowance applies to a same-day journey of 10 hours, and one of 7 hours?",
     "must": [r"half", r"nil|no\W+ba|not entitled|no boarding"]},
    {"q": "On a continuing journey, away one full day plus an extra 14 hours, how is BA/DA computed for the extra hours?",
     "must": [r"one\W+(?:full\W+)?day", r"additional"]},
    {"q": "On a residential training program where meals are provided, what LA and BA can be claimed?",
     "must": [r"no\w*\W+(?:lodging|la)|not\W+(?:be\W+)?entitled\W+to\W+(?:any\W+)?(?:lodging|la)", r"50\s*%"]},
    {"q": "My station stay unexpectedly extends to 12 days. How does lodging change?",
     "must": [r"75\s*%", r"11th"]},

    # ---- Operating procedure ----
    {"q": "Which expenses are not reimbursable under the domestic travel policy?",
     "must": [r"hard drink", r"cigarette", r"health club"]},
    {"q": "Within how many days must a Travel Expenses Voucher be submitted, and what happens to an advance unadjusted for 30 days?",
     "must": [r"three\W+days|\b3\W+days", r"30\W+days"]},

    # ---- Foreign details ----
    {"q": "On a foreign visit, if both boarding and lodging are provided, what percentage of DA applies? And if only lodging?",
     "must": [r"30\s*%", r"50\s*%"]},
    {"q": "When does foreign DA entitlement begin and end, and what fraction must be backed by bills?",
     "must": [r"board\w*\W+the\W+plane", r"60\s*%"]},
    {"q": "Which bands does the foreign travel policy apply to?",
     "must": [r"7\D+8\D+9\D+10|band\W+7,?\s*8,?\s*9"]},

    # ---- Eligibility / scope ----
    {"q": "Which employees are excluded from the domestic travel policy?",
     "must": [r"client site", r"30\W+days"]},

    # ---- Genuinely absent ----
    {"q": "How do I book the hotel through the company portal?",
     "must": [r"could not find|not (?:contain|specify|provide|mention)|does not|no information|unable to find"]},
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def main():
    pipe = RAGPipeline()
    passed = 0
    failures = []
    for i, case in enumerate(CASES, 1):
        pipe.memory.clear()
        ans = _norm("".join(pipe.stream_answer(case["q"])))
        miss = [p for p in case["must"] if not re.search(p, ans, re.I)]
        bad = [p for p in case.get("forbid", []) if re.search(p, ans, re.I)]
        ok = not miss and not bad
        passed += ok
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {i:2d}. {case['q'][:70]}")
        if not ok:
            if miss:
                print(f"        missing: {miss}")
            if bad:
                print(f"        forbidden present: {bad}")
            failures.append((i, case["q"], ans))

    print("\n" + "=" * 60)
    print(f"RESULT: {passed}/{len(CASES)} passed")
    if failures:
        print("\n--- failed answers (for inspection) ---")
        for i, q, ans in failures:
            print(f"\n[{i}] {q}\n{ans[:500]}")
    sys.exit(0 if passed == len(CASES) else 1)


if __name__ == "__main__":
    main()
