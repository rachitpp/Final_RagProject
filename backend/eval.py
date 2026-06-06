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
  band    : (optional) inject this band as the authenticated caller, so the
            answer is band-scoped exactly like a logged-in user (E101=9, E107=3).
            Omit for the bandless "answer for every band" behaviour.

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
    # "Entitlement" = the full lodging + boarding the policy grants (the model
    # rightly totals both, not lodging alone). Delhi=A, Jaipur=B; grand totals
    # per band = (LA+BA)*3 for each leg, summed: see the band-by-band figures.
    {"q": "How much is the entitlement for 3 days in Delhi and 3 days in Jaipur?",
     "must": [r"24[,\s]?750", r"17[,\s]?100", r"11[,\s]?700", r"\b7[,\s]?200\b"]},
    {"q": "How much is the entitlement for 3 days in Mumbai and 2 days in Bangalore?",
     "must": [r"20[,\s]?000", r"12[,\s]?500"]},

    # ---- Timing rules ----
    {"q": "What boarding allowance applies to a same-day journey of 10 hours, and one of 7 hours?",
     "must": [r"half", r"nil|no\W+ba|not entitled|no boarding"]},
    {"q": "On a continuing journey, away one full day plus an extra 14 hours, how is BA/DA computed for the extra hours?",
     "must": [r"one\W+(?:full\W+)?day", r"additional"]},
    {"q": "On a residential training program where meals are provided, what LA and BA can be claimed?",
     "must": [r"no\w*\W+(?:lodging|la)|not entitled\W+to\W+(?:any\W+)?lodging", r"50\s*%"]},
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

    # ---- Band-scoped answers (authenticated caller) ----
    # Guards the foreign category-C-by-exclusion fix: Brazil is not listed, so the
    # model must resolve Category C and read the C row ($175 for Band 9&10),
    # NEVER the Category-A row ($250) — the exact bug these cases lock in.
    {"q": "What is my standard daily allowance for a trip to Brazil?", "band": 9,
     "must": [r"categor\w*\W*'?c'?\b", r"\b175\b"], "forbid": [r"\$?\s*250\b"]},
    {"q": "I am going to Brazil and the company provides both my boarding and lodging. What is my daily allowance?",
     "band": 9, "must": [r"categor\w*\W*'?c'?\b", r"52[.,]?50?"], "forbid": [r"\$?\s*75\b"]},
    # Band scoping: same Brazil trip, lower band reads the "Upto Band 7" column ($75).
    {"q": "What is my standard daily allowance for a trip to Brazil?", "band": 7,
     "must": [r"categor\w*\W*'?c'?\b", r"\b75\b"], "forbid": [r"\$?\s*175\b", r"\$?\s*250\b"]},
    # Eligibility gate: foreign policy covers Bands 7-10 only, so a lower band must be
    # routed to the Foreign Travel sanction, NOT given a rate — for an explicitly
    # listed country (USA) AND a by-exclusion one (Brazil).
    {"q": "What is my daily allowance for a business trip to the USA?", "band": 3,
     "must": [r"sanction|not eligible|outside|does not (?:apply|cover)|not covered"]},
    {"q": "What is my daily allowance for a business trip to Brazil?", "band": 3,
     "must": [r"sanction|not eligible|outside|does not (?:apply|cover)|not covered"]},
    # Domestic band scoping: all bands eligible, but the rate differs by band.
    {"q": "I am staying in a hotel in Mumbai for 1 night. What is my lodging entitlement?",
     "band": 3, "must": [r"categor\w*\W*'?a'?\b", r"\b1000\b"], "forbid": [r"\b4000\b"]},
    {"q": "I am staying in a hotel in Mumbai for 1 night. What is my lodging entitlement?",
     "band": 9, "must": [r"categor\w*\W*'?a'?\b", r"\b4000\b"]},
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class _Profile:
    """Minimal authenticated-caller stand-in: the pipeline duck-types `.band`."""
    def __init__(self, band: int):
        self.band = band


def main():
    pipe = RAGPipeline()
    passed = 0
    failures = []
    for i, case in enumerate(CASES, 1):
        # Each gold case is independent: no history passed -> no follow-up
        # rewriting (the pipeline is stateless, so there's nothing to clear).
        profile = _Profile(case["band"]) if "band" in case else None
        ans = _norm("".join(pipe.stream_answer(case["q"], user_profile=profile)))
        miss = [p for p in case["must"] if not re.search(p, ans, re.I)]
        bad = [p for p in case.get("forbid", []) if re.search(p, ans, re.I)]
        ok = not miss and not bad
        passed += ok
        mark = "PASS" if ok else "FAIL"
        tag = f" [B{case['band']}]" if "band" in case else ""
        print(f"[{mark}] {i:2d}.{tag} {case['q'][:66]}")
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
