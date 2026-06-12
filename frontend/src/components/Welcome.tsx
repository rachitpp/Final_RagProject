import { ShieldCheck } from "lucide-react";

const STARTERS = [
  ["LODGING", "What's my lodging allowance for a trip to Mumbai?"],
  ["LEAVE", "How many privilege leaves do I get a year?"],
  ["FOREIGN", "What's my per diem for a 5-day trip to London?"],
  ["CITIES", "How are cities classified into categories?"],
] as const;

export default function Welcome({
  onPick,
  name,
  band,
}: {
  onPick: (q: string) => void;
  name?: string;
  band?: number;
}) {
  const firstName = name?.trim().split(/\s+/)[0];

  // Spacing is deliberately UNEVEN to group the five elements into three
  // blocks (kicker+headline · subtitle+band chip · starters): tight inside a
  // block, one wide break before the starters — even gaps read as a flat list.
  return (
    <div>
      <div className="animate-rise font-sans text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-ink-faint">
        Ready when you are
      </div>
      <h1 className="mt-2 animate-rise font-serif text-[2rem] font-bold leading-[1.08] tracking-tight text-ink [animation-delay:90ms] sm:text-[2.6rem] sm:leading-[1.05]">
        {firstName ? `Welcome back, ${firstName}.` : "What would you like to know?"}
      </h1>
      <p className="mt-5 max-w-md animate-rise font-serif text-[1.08rem] leading-relaxed text-ink-soft [animation-delay:180ms]">
        Ask about your travel reimbursements and leave — answers are tailored to you.
      </p>

      {/* make the band-scoping (the product's core promise) visible before the
          first question is even asked — it qualifies the subtitle, so it hangs
          right under it as part of the same block */}
      {typeof band === "number" && (
        <div className="mt-3 animate-rise [animation-delay:230ms]">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-gold/30 bg-gold/10 px-3 py-1.5 font-sans text-[0.76rem] font-medium text-gold">
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
            Answers scoped to Band {band}
          </span>
        </div>
      )}

      <div className="mt-12 grid animate-rise grid-cols-1 gap-2 [animation-delay:280ms] sm:grid-cols-2">
        {STARTERS.map(([label, q]) => (
          <button
            key={label}
            type="button"
            onClick={() => onPick(q)}
            className="flex flex-col gap-1 rounded-lg border border-rule-strong px-3.5 py-2.5 text-left transition duration-200 hover:-translate-y-px hover:border-gold/40 hover:bg-paper-3"
          >
            <span className="font-mono text-[0.62rem] uppercase tracking-wide text-ink-faint">
              {label}
            </span>
            <span className="font-serif text-[0.86rem] leading-snug text-ink-soft">
              {q}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
