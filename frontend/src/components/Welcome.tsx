const STARTERS = [
  ["RATES", "What is the DA rate for a Category A city?"],
  ["CITIES", "How are cities classified into categories?"],
  ["LODGING", "What are the lodging limits for each band?"],
  ["TRAVEL", "Which mode of travel is allowed for each grade?"],
] as const;

export default function Welcome({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="pt-14">
      <div className="animate-rise font-sans text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-ink-faint">
        Ready when you are
      </div>
      <h1 className="mt-5 animate-rise font-serif text-[2.6rem] font-bold leading-[1.05] tracking-tight text-ink [animation-delay:90ms]">
        What would you like to know?
      </h1>
      <p className="mt-4 max-w-md animate-rise font-serif text-[1.08rem] leading-relaxed text-ink-soft [animation-delay:180ms]">
        Ask anything about your travel-reimbursement policy — or start with one of these.
      </p>

      <div className="mt-8 grid animate-rise grid-cols-1 gap-2.5 [animation-delay:280ms] sm:grid-cols-2">
        {STARTERS.map(([label, q]) => (
          <button
            key={label}
            type="button"
            onClick={() => onPick(q)}
            className="flex flex-col gap-1.5 rounded-xl border border-rule-strong px-4 py-3.5 text-left transition duration-200 hover:-translate-y-px hover:border-gold/40 hover:bg-paper-3"
          >
            <span className="font-mono text-[0.68rem] uppercase tracking-wide text-ink-faint">
              {label}
            </span>
            <span className="font-serif text-[0.95rem] leading-snug text-ink-soft">
              {q}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
