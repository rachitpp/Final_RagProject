const STARTERS = [
  ["LODGING", "What's my lodging allowance for a trip to Mumbai?"],
  ["LEAVE", "How many privilege leaves do I get a year?"],
  ["FOREIGN", "What's my per diem for a 5-day trip to London?"],
  ["CITIES", "How are cities classified into categories?"],
] as const;

export default function Welcome({
  onPick,
  name,
}: {
  onPick: (q: string) => void;
  name?: string;
}) {
  const firstName = name?.trim().split(/\s+/)[0];

  return (
    <div>
      <div className="animate-rise font-sans text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-ink-faint">
        Ready when you are
      </div>
      <h1 className="mt-5 animate-rise font-serif text-[2rem] font-bold leading-[1.08] tracking-tight text-ink [animation-delay:90ms] sm:text-[2.6rem] sm:leading-[1.05]">
        {firstName ? `Welcome back, ${firstName}.` : "What would you like to know?"}
      </h1>
      <p className="mt-4 max-w-md animate-rise font-serif text-[1.08rem] leading-relaxed text-ink-soft [animation-delay:180ms]">
        Ask about your travel reimbursements and leave — answers are tailored to you.
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
