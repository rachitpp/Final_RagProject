import { Fragment } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  CalendarDays,
  Calculator,
  FileText,
  Globe,
  MessageSquare,
  Moon,
  Plane,
  Route,
  Search,
  ShieldCheck,
  Sun,
  type LucideIcon,
} from "lucide-react";
import { useTheme } from "@/hooks/useTheme";

/**
 * Public landing at `/` — the first thing an unauthenticated visitor sees, and a
 * piece of documentation in its own right: what the assistant does, how its
 * retrieval → citation pipeline works, and why the answers are trustworthy.
 *
 * The hero carries a faithful, in-DOM preview of a real answer (same bubbles,
 * lede styling, citation chip and Sources footer the chat actually renders) —
 * not a screenshot — so the page shows the real product rather than a mockup.
 * Signed-in users never reach this (RequireAnon redirects them to /chat).
 */

const PIPELINE: { icon: LucideIcon; title: string; body: string }[] = [
  { icon: MessageSquare, title: "You ask", body: "in plain English" },
  { icon: Route, title: "It routes", body: "domestic, foreign or leave" },
  { icon: Search, title: "It retrieves", body: "exact passages + rate tables" },
  { icon: FileText, title: "It cites", body: "every figure, to the page" },
];

const FEATURES: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: ShieldCheck,
    title: "Scoped to your band",
    body: "Entitlements are resolved server-side from the HR roster — you only ever see what applies to you.",
  },
  {
    icon: FileText,
    title: "Verifiable citations",
    body: "Every claim links to the exact policy file and page, shown as a source chip you can check.",
  },
  {
    icon: Plane,
    title: "Travel and leave together",
    body: "Domestic trips, foreign trips and leave balances — one assistant across every policy.",
  },
  {
    icon: Calculator,
    title: "The math runs in code",
    body: "Per-diem and multi-leg totals go through a calculator tool, not the model — so a wrong sum can't slip in.",
  },
];

const POLICIES: { icon: LucideIcon; label: string }[] = [
  { icon: Plane, label: "Domestic Travel" },
  { icon: Globe, label: "Foreign Travel" },
  { icon: CalendarDays, label: "Leave" },
];

/** A faithful, static reproduction of one chat turn, using the exact bubble,
 *  lede, citation-chip and Sources-footer styling the live chat renders. */
function AnswerPreview() {
  return (
    <div className="relative">
      {/* soft focal glow behind the panel — the page's one bit of real depth */}
      <div
        aria-hidden="true"
        className="absolute -inset-6 rounded-[32px] bg-gold/[0.06] blur-2xl"
      />
      <div className="relative rounded-2xl border border-rule-strong bg-paper-2 shadow-[0_28px_72px_-28px_rgba(0,0,0,0.7)]">
        {/* window chrome */}
        <div className="flex items-center gap-2 border-b border-rule px-4 py-2.5">
          <span className="font-serif text-sm font-bold tracking-tight text-ink">
            <span className="text-gold" aria-hidden="true">◐</span> Policy Assistant
          </span>
          <span className="ml-auto flex items-center gap-1.5 font-sans text-[0.68rem] text-ink-faint">
            <span className="status-dot" aria-hidden="true" /> Ready
          </span>
        </div>

        <div className="px-5 py-5">
          {/* user turn */}
          <div className="flex flex-col items-end">
            <div className="mb-1.5 font-sans text-[0.7rem] font-semibold uppercase tracking-[0.12em] text-ink-soft">
              ◉&nbsp;&nbsp;You
            </div>
            <div className="max-w-[82%] rounded-[20px] bg-paper-4 px-4 py-2.5 font-sans text-[0.88rem] leading-relaxed text-ink">
              What's my lodging allowance for a trip to Mumbai?
            </div>
          </div>

          {/* assistant turn */}
          <div className="mt-5 border-t border-rule-strong pt-4">
            <div className="mb-2 font-sans text-[0.7rem] font-semibold uppercase tracking-[0.12em] text-ink-soft">
              ◐&nbsp;&nbsp;Assistant
            </div>
            <div className="assistant-prose font-serif text-[0.95rem] text-ink">
              <p className="my-2.5 leading-[1.75]">
                Mumbai is a <strong className="font-semibold text-ink">Category A</strong>{" "}
                city, so lodging is reimbursed up to the Category&nbsp;A ceiling for your
                band.
              </p>
              <p className="my-2.5 leading-[1.75]">
                Actuals must be supported by a GST-compliant hotel invoice.{" "}
                <cite className="mx-0.5 inline-flex items-center gap-1 whitespace-nowrap rounded-md border border-gold/30 bg-gold/10 px-1.5 py-0.5 align-middle font-mono text-[0.72em] not-italic text-gold">
                  <FileText className="h-3 w-3" />
                  domestic travel.pdf, p.4
                </cite>
              </p>
            </div>

            {/* Sources footer — matches SourcesPanel */}
            <div className="mt-4 border-t border-rule pt-3">
              <div className="mb-2 font-sans text-[0.62rem] font-semibold uppercase tracking-[0.18em] text-ink-faint">
                Source
              </div>
              <span className="inline-flex items-center gap-1.5 rounded-md border border-rule-strong bg-paper-3/50 px-2 py-1 font-sans text-[0.74rem] text-ink-soft">
                <FileText className="h-3.5 w-3.5 shrink-0 text-gold" />
                <span className="font-medium text-ink">Domestic Travel</span>
                <span className="text-ink-faint">p.4</span>
              </span>
            </div>
          </div>
        </div>
      </div>

      <p className="mt-3 text-center font-sans text-[0.72rem] text-ink-faint">
        Illustrative — exact ceilings come from the live policy and your band.
      </p>
    </div>
  );
}

export default function LandingPage() {
  const { theme, toggle } = useTheme();

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-paper text-ink">
      {/* ── top bar ── */}
      <header className="relative z-10 mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <span className="font-serif text-lg font-bold tracking-tight text-ink">
          <span className="text-gold" aria-hidden="true">◐</span> Policy Assistant
        </span>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={toggle}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            className="rounded-md p-2 text-ink-faint transition duration-200 hover:bg-paper-3 hover:text-ink"
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          <Link
            to="/login"
            className="rounded-lg border border-rule-strong px-3.5 py-1.5 font-sans text-[0.84rem] text-ink transition duration-200 hover:bg-paper-3"
          >
            Sign in
          </Link>
        </div>
      </header>

      {/* ── hero — asymmetric: claim on the left, real answer on the right ── */}
      <section className="relative z-10 mx-auto grid max-w-6xl items-center gap-12 px-6 pb-20 pt-12 lg:grid-cols-[1.05fr_1fr] lg:gap-10 lg:pt-20">
        <div>
          <div className="animate-rise font-sans text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-ink-faint">
            Company travel &amp; leave policy
          </div>
          <h1 className="mt-5 animate-rise font-serif text-[2.5rem] font-bold leading-[1.04] tracking-tight text-ink [animation-delay:90ms] sm:text-[3.2rem]">
            Answers from the policy,{" "}
            <span className="text-gold-strong">cited to the page.</span>
          </h1>
          <p className="mt-6 max-w-xl animate-rise font-serif text-[1.1rem] leading-relaxed text-ink-soft [animation-delay:180ms]">
            Ask about travel reimbursement or leave in plain English. Every figure
            is pulled from the policy document, linked to the exact page, and scoped
            to your band — so you can trust the number and check the source.
          </p>

          <div className="mt-9 flex animate-rise flex-wrap items-center gap-3 [animation-delay:280ms]">
            <Link
              to="/login"
              className="group/cta inline-flex items-center gap-2 rounded-lg bg-ink px-5 py-3 font-sans text-[0.92rem] font-medium text-paper transition duration-200 hover:bg-ink-soft"
            >
              Sign in
              <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover/cta:translate-x-0.5" />
            </Link>
            <Link
              to="/activate"
              className="font-sans text-[0.9rem] text-ink-muted underline-offset-4 transition duration-200 hover:text-gold hover:underline"
            >
              First time here? Activate your account
            </Link>
          </div>

          <div className="mt-9 flex animate-rise flex-wrap items-center gap-2 [animation-delay:360ms]">
            {POLICIES.map(({ icon: Icon, label }) => (
              <span
                key={label}
                className="inline-flex items-center gap-1.5 rounded-full border border-rule bg-paper-2 px-3 py-1 font-sans text-[0.76rem] text-ink-muted"
              >
                <Icon className="h-3.5 w-3.5 text-gold" /> {label}
              </span>
            ))}
          </div>
        </div>

        <div className="animate-rise [animation-delay:240ms]">
          <AnswerPreview />
        </div>
      </section>

      {/* ── how it works — a connected pipeline, not a grid of identical cards ── */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 py-14">
        <div className="rounded-2xl border border-rule bg-paper-2 px-6 py-10 sm:px-10">
          <h2 className="font-serif text-[1.7rem] font-bold tracking-tight text-ink">
            From question to cited answer
          </h2>
          <p className="mt-2 max-w-xl font-serif text-[1rem] leading-relaxed text-ink-soft">
            Each answer is retrieved from the source documents — not generated from
            the model's memory.
          </p>

          <div className="mt-9 flex flex-col gap-6 md:flex-row md:items-start md:gap-2">
            {PIPELINE.map(({ icon: Icon, title, body }, i) => (
              <Fragment key={title}>
                <div className="flex items-start gap-3 md:flex-1 md:flex-col">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-rule-strong bg-paper text-gold">
                    <Icon className="h-5 w-5" />
                  </span>
                  <div>
                    <div className="font-sans text-[0.95rem] font-semibold text-ink">
                      {title}
                    </div>
                    <div className="mt-0.5 font-serif text-[0.88rem] leading-snug text-ink-muted">
                      {body}
                    </div>
                  </div>
                </div>
                {i < PIPELINE.length - 1 && (
                  <ArrowRight className="ml-[1.25rem] h-4 w-4 shrink-0 rotate-90 text-ink-faint md:ml-0 md:mt-2.5 md:rotate-0" />
                )}
              </Fragment>
            ))}
          </div>

          <p className="mt-9 border-t border-rule pt-5 font-sans text-[0.82rem] leading-relaxed text-ink-faint">
            Multi-day and multi-leg totals are computed in code, so the arithmetic is
            auditable rather than guessed.
          </p>
        </div>
      </section>

      {/* ── what makes it trustworthy — a plain list, no boxes (textural contrast) ── */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 py-14">
        <h2 className="max-w-2xl font-serif text-[1.7rem] font-bold tracking-tight text-ink">
          Why you can trust the answer
        </h2>
        <div className="mt-8 grid gap-x-12 gap-y-8 sm:grid-cols-2">
          {FEATURES.map(({ icon: Icon, title, body }) => (
            <div key={title} className="flex gap-3.5">
              <Icon className="mt-0.5 h-5 w-5 shrink-0 text-gold" />
              <div>
                <h3 className="font-sans text-[0.98rem] font-semibold text-ink">{title}</h3>
                <p className="mt-1 max-w-sm font-serif text-[0.92rem] leading-relaxed text-ink-muted">
                  {body}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── closing CTA ── */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 py-16">
        <div className="flex flex-col items-start gap-6 rounded-2xl border border-rule-strong bg-paper-2 px-6 py-10 sm:flex-row sm:items-center sm:justify-between sm:px-10">
          <div>
            <h2 className="font-serif text-[1.7rem] font-bold leading-tight tracking-tight text-ink">
              Ask your first question.
            </h2>
            <p className="mt-2 font-serif text-[1rem] leading-relaxed text-ink-soft">
              Sign in with your employee ID — your entitlements are set up
              automatically.
            </p>
          </div>
          <Link
            to="/login"
            className="group/cta inline-flex shrink-0 items-center gap-2 rounded-lg bg-ink px-6 py-3 font-sans text-[0.92rem] font-medium text-paper transition duration-200 hover:bg-ink-soft"
          >
            Sign in
            <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover/cta:translate-x-0.5" />
          </Link>
        </div>
      </section>

      {/* ── footer ── */}
      <footer className="relative z-10 mx-auto max-w-6xl px-6 pb-10">
        <div className="flex flex-col items-center justify-between gap-3 border-t border-rule pt-6 font-sans text-[0.78rem] text-ink-faint sm:flex-row">
          <span>
            <span className="text-gold" aria-hidden="true">◐</span> Policy Assistant
          </span>
          <span>Grounded answers · page-cited · band-aware</span>
        </div>
      </footer>

      <div className="brand-watermark" aria-hidden="true">◐</div>
    </div>
  );
}
