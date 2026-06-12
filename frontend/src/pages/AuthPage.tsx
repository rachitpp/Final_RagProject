import {
  useLayoutEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BadgeCheck,
  FileText,
  Loader2,
  Moon,
  ShieldCheck,
  Sun,
} from "lucide-react";
import { useTheme } from "@/hooks/useTheme";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";
import AuthField from "@/components/auth/AuthField";

/**
 * Auth screen — login + first-time activation, wired to the backend.
 *
 * Login and activation live in ONE mounted component so switching between them is
 * a smooth in-place morph (the bordered box animates its height, the copy
 * cross-fades) instead of a route swap that would remount the frame and replay
 * the entrance. `/login` and `/activate` both render this with the right
 * `initialMode`; the switch link only flips local state, so no remount happens.
 *
 * By design the user only ever provides employee_id + password (+ email & a
 * password to activate) — band/grade and every entitlement attribute are
 * server-authoritative, never typed here, so personalization can't be spoofed.
 * Submit calls POST /auth/login or /auth/activate (both return a JWT, so a
 * successful activation also signs the user in) and redirects to the chat.
 */
type Mode = "login" | "activate";

const COPY: Record<Mode, { title: string; subtitle: string }> = {
  login: { title: "Welcome back", subtitle: "Sign in to continue." },
  activate: { title: "Activate account", subtitle: "Set a password to get started." },
};

export default function AuthPage({ initialMode }: { initialMode: Mode }) {
  const { theme, toggle } = useTheme();
  const { login, activate } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>(initialMode);

  const [employeeId, setEmployeeId] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shaking, setShaking] = useState(false);
  const [capsOn, setCapsOn] = useState(false);

  const isLogin = mode === "login";
  const mismatch = !isLogin && confirm !== "" && password !== confirm;
  const canSubmit =
    !submitting &&
    (isLogin
      ? employeeId.trim() !== "" && password !== ""
      : employeeId.trim() !== "" &&
        email.trim() !== "" &&
        password !== "" &&
        confirm !== "" &&
        !mismatch);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      if (isLogin) {
        await login(employeeId.trim(), password);
      } else {
        await activate(employeeId.trim(), email.trim(), password);
      }
      // Both endpoints return a JWT, so we're authenticated either way.
      navigate("/chat", { replace: true });
    } catch (err) {
      // Inline, not a toast: the message stays visible until the user retypes,
      // and the card shake gives the instant "didn't go through" cue.
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setShaking(true);
      setSubmitting(false);
    }
  };

  // Field edits clear the inline error (the user is addressing it).
  const edit = (set: (v: string) => void) => (v: string) => {
    set(v);
    setError(null);
  };

  // Caps-lock detection for the password fields — keydown+keyup so toggling
  // the CapsLock key itself updates the hint immediately.
  const trackCaps = (e: KeyboardEvent<HTMLInputElement>) =>
    setCapsOn(e.getModifierState("CapsLock"));

  // Switch between login/activate without dragging stale field state or a
  // half-typed error across the morph.
  const switchMode = () => {
    setMode(isLogin ? "activate" : "login");
    setPassword("");
    setConfirm("");
    setError(null);
  };

  // Morph the box height between the two forms (and when the mismatch/error/
  // caps-lock hints show/hide) by measuring the live content and animating to it.
  const contentRef = useRef<HTMLDivElement>(null);
  const [boxH, setBoxH] = useState<number | undefined>(undefined);
  useLayoutEffect(() => {
    const el = contentRef.current;
    if (el) setBoxH(el.offsetHeight);
  }, [mode, mismatch, error, capsOn]);

  const showHide = (
    <button
      type="button"
      onClick={() => setShowPw((s) => !s)}
      className="shrink-0 font-sans text-[0.68rem] font-semibold uppercase tracking-[0.12em] text-ink-faint transition duration-200 hover:text-gold"
    >
      {showPw ? "Hide" : "Show"}
    </button>
  );

  return (
    <div className="relative flex h-screen overflow-hidden bg-paper text-ink">
      {/* theme toggle — top right of the whole screen (stays mounted across morph) */}
      <button
        type="button"
        onClick={toggle}
        aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        className="absolute right-5 top-5 z-20 rounded-md p-2 text-ink-faint transition duration-200 hover:bg-paper-3 hover:text-ink"
      >
        {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </button>

      {/* ── left: branded panel (lg+) — ties sign-in to the product so the form
          isn't a lone card in a void ── */}
      <aside className="relative hidden w-[46%] max-w-2xl animate-auth-swap flex-col justify-between overflow-hidden border-r border-rule bg-paper-2 px-12 py-14 lg:flex">
        <div className="relative z-10 font-serif text-lg font-bold tracking-tight text-ink">
          <span className="text-gold" aria-hidden="true">◐</span> Policy Assistant
        </div>

        <div className="relative z-10 max-w-md">
          <h2 className="font-serif text-[2.4rem] font-bold leading-[1.08] tracking-tight text-ink">
            Answers from the policy,{" "}
            <span className="text-gold-strong">cited to the page.</span>
          </h2>
          <p className="mt-5 font-serif text-[1.05rem] leading-relaxed text-ink-soft">
            Sign in to ask about travel reimbursement and leave — every figure is
            grounded in the policy and scoped to your band.
          </p>
          {/* mini product demo — a faux cited exchange instead of feature bullets
              (show, don't tell). The chip copies Markdown.tsx's citation chip
              classes so it looks exactly like the real product. */}
          <div className="mt-9 rounded-xl border border-rule-strong bg-paper p-5 shadow-[0_18px_48px_-26px_rgba(0,0,0,0.55)]">
            <p className="font-sans text-[0.84rem] leading-relaxed text-ink-muted">
              “What's my daily allowance for a 3-day Mumbai trip?”
            </p>
            <div className="mt-3.5 border-t border-rule pt-3.5">
              <p className="font-serif text-[0.95rem] leading-[1.7] text-ink-soft">
                Your band's metro-city rate applies to all three days — the
                total is computed from the entitlement table, not estimated.{" "}
                <cite className="mx-0.5 inline-flex items-center gap-1 whitespace-nowrap rounded-md border border-gold/30 bg-gold/10 px-1.5 py-0.5 align-middle font-mono text-[0.72em] not-italic text-gold">
                  <FileText className="h-3 w-3" />
                  domestic travel.pdf, p.2
                </cite>
              </p>
            </div>
          </div>
        </div>

        <div className="relative z-10 font-sans text-[0.76rem] text-ink-faint">
          Grounded answers · page-cited · band-aware
        </div>

        {/* ambient brand glyph, contained to the panel */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-16 -right-12 select-none font-serif text-[20rem] leading-none text-ink opacity-[0.03]"
        >
          ◐
        </div>
      </aside>

      {/* ── right: the form ──
          The page is locked to the viewport (h-screen + overflow-hidden on the
          root): switching login ⇄ activate grows the CARD, never the document,
          so no body scrollbar appears and nothing jumps. If the taller activate
          form exceeds a short viewport, THIS column scrolls internally; my-auto
          (not items-center) keeps centering safe — an overflowing flex-centered
          child would clip its top unreachably, auto margins fall back to
          top-aligned + scrollable. */}
      <div className="relative z-10 flex flex-1 justify-center overflow-y-auto px-6 py-6">
      <div className="relative z-10 my-auto w-full max-w-xs">
        {/* brand — mobile only (the left panel carries it on lg+) */}
        <div className="mb-5 animate-auth-swap text-center font-serif text-lg font-bold tracking-tight text-ink lg:hidden">
          <span className="text-gold" aria-hidden="true">◐</span> Policy Assistant
        </div>
        {/* title — cross-fades on mode change */}
        <div key={`head-${mode}`} className="animate-auth-swap text-center">
          <h1 className="font-serif text-[1.6rem] font-bold leading-[1.08] tracking-tight text-ink">
            {COPY[mode].title}
          </h1>
          <p className="mt-1 font-serif text-[0.94rem] leading-relaxed text-ink-soft">
            {COPY[mode].subtitle}
          </p>
        </div>

        {/* box: border/padding stay put; the inner height morphs between forms.
            Entrance lives on the outer wrapper so the shake (re-applied per
            rejected submit) never replays it. */}
        <div className="mt-5 animate-auth-swap [animation-delay:60ms]">
        <div
          onAnimationEnd={(e) => {
            if (e.animationName === "auth-shake") setShaking(false);
          }}
          className={cn(
            "rounded-2xl border border-rule-strong bg-paper-4 p-5 shadow-[0_10px_36px_-18px_rgba(0,0,0,0.4)]",
            shaking && "animate-auth-shake",
          )}
        >
          <div
            className="overflow-hidden transition-[height] duration-[540ms] ease-[cubic-bezier(0.16,1,0.3,1)]"
            style={{ height: boxH }}
          >
            <div ref={contentRef} key={`form-${mode}`} className="animate-auth-swap [animation-delay:60ms]">
              <form onSubmit={onSubmit}>
                <AuthField
                  autoFocus
                  label="Employee ID"
                  value={employeeId}
                  onChange={edit(setEmployeeId)}
                  placeholder="EMP-10427"
                  autoComplete="username"
                  invalid={!!error}
                />

                {!isLogin && (
                  <AuthField
                    className="mt-4"
                    label="Work email"
                    type="email"
                    value={email}
                    onChange={edit(setEmail)}
                    placeholder="you@company.com"
                    autoComplete="email"
                    invalid={!!error}
                  />
                )}

                <AuthField
                  className="mt-4"
                  label={isLogin ? "Password" : "New password"}
                  type={showPw ? "text" : "password"}
                  value={password}
                  onChange={edit(setPassword)}
                  placeholder="••••••••"
                  autoComplete={isLogin ? "current-password" : "new-password"}
                  adornment={showHide}
                  invalid={!!error}
                  onKeyDown={trackCaps}
                  onKeyUp={trackCaps}
                />

                {capsOn && (
                  <p className="mt-2 animate-auth-swap font-sans text-[0.76rem] text-gold">
                    Caps Lock is on.
                  </p>
                )}

                {!isLogin && (
                  <AuthField
                    className="mt-4"
                    label="Confirm password"
                    type={showPw ? "text" : "password"}
                    value={confirm}
                    onChange={edit(setConfirm)}
                    placeholder="••••••••"
                    autoComplete="new-password"
                    invalid={!!error}
                    onKeyDown={trackCaps}
                    onKeyUp={trackCaps}
                  />
                )}

                {mismatch && (
                  <p className="mt-2 animate-auth-swap font-sans text-[0.76rem] text-destructive">
                    Passwords don't match.
                  </p>
                )}

                {error && (
                  <p
                    role="alert"
                    className="mt-4 animate-auth-swap font-sans text-[0.78rem] leading-relaxed text-destructive"
                  >
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={!canSubmit}
                  className="group/btn mt-6 flex w-full items-center justify-center gap-2 rounded-lg bg-ink px-4 py-2.5 font-sans text-[0.86rem] font-semibold text-paper transition duration-200 hover:bg-ink-soft disabled:bg-paper-5 disabled:text-ink-faint"
                >
                  {submitting ? (
                    <>
                      {isLogin ? "Signing in" : "Activating"}
                      <Loader2 className="h-4 w-4 animate-spin" />
                    </>
                  ) : (
                    <>
                      {isLogin ? "Sign in" : "Activate account"}
                      <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover/btn:translate-x-0.5" />
                    </>
                  )}
                </button>
              </form>
            </div>
          </div>
        </div>
        </div>

        {/* switch — flips mode in place (no navigation → no remount → smooth) */}
        <div key={`switch-${mode}`} className="mt-4 animate-auth-swap text-center [animation-delay:120ms]">
          <button
            type="button"
            onClick={switchMode}
            className="font-sans text-[0.82rem] text-ink-muted underline-offset-4 transition duration-200 hover:text-gold hover:underline"
          >
            {isLogin
              ? "First time here? Activate your account"
              : "Already have an account? Sign in"}
          </button>
        </div>

        {/* footer — cross-fades with the mode */}
        <div
          key={`foot-${mode}`}
          className="mt-4 flex animate-auth-swap items-center justify-center gap-2 text-center font-sans text-[0.76rem] text-ink-faint [animation-delay:180ms]"
        >
          {isLogin ? (
            <>
              <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-sage" />
              <span>Your entitlements are resolved automatically after sign-in.</span>
            </>
          ) : (
            <>
              <BadgeCheck className="h-3.5 w-3.5 shrink-0 text-sage" />
              <span>We match your details to the HR roster — access is set automatically.</span>
            </>
          )}
        </div>
      </div>

      </div>
    </div>
  );
}
