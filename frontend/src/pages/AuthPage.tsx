import { useLayoutEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowRight, BadgeCheck, Loader2, Moon, ShieldCheck, Sun } from "lucide-react";
import { useTheme } from "@/hooks/useTheme";
import { useAuth } from "@/hooks/useAuth";
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
      navigate("/", { replace: true });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Something went wrong.");
      setSubmitting(false);
    }
  };

  // Switch between login/activate without dragging stale field state or a
  // half-typed error across the morph.
  const switchMode = () => {
    setMode(isLogin ? "activate" : "login");
    setPassword("");
    setConfirm("");
  };

  // Morph the box height between the two forms (and when the mismatch hint shows
  // /hides) by measuring the live content and animating to its height.
  const contentRef = useRef<HTMLDivElement>(null);
  const [boxH, setBoxH] = useState<number | undefined>(undefined);
  useLayoutEffect(() => {
    const el = contentRef.current;
    if (el) setBoxH(el.offsetHeight);
  }, [mode, mismatch]);

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
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-paper px-6 py-12 text-ink">
      {/* theme toggle — top right (stays mounted across the morph) */}
      <button
        type="button"
        onClick={toggle}
        aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        className="absolute right-5 top-5 z-20 rounded-md p-2 text-ink-faint transition duration-200 hover:bg-paper-3 hover:text-ink"
      >
        {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </button>

      <div className="relative z-10 w-full max-w-sm">
        {/* title — cross-fades on mode change */}
        <div key={`head-${mode}`} className="animate-auth-swap text-center">
          <h1 className="font-serif text-[1.9rem] font-bold leading-[1.08] tracking-tight text-ink">
            {COPY[mode].title}
          </h1>
          <p className="mt-1.5 font-serif text-[1.02rem] leading-relaxed text-ink-soft">
            {COPY[mode].subtitle}
          </p>
        </div>

        {/* box: border/padding stay put; the inner height morphs between forms */}
        <div className="mt-8 rounded-2xl border border-rule-strong bg-paper-4 p-7 shadow-[0_10px_36px_-18px_rgba(0,0,0,0.4)]">
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
                  onChange={setEmployeeId}
                  placeholder="EMP-10427"
                  autoComplete="username"
                />

                {!isLogin && (
                  <AuthField
                    className="mt-6"
                    label="Work email"
                    type="email"
                    value={email}
                    onChange={setEmail}
                    placeholder="you@company.com"
                    autoComplete="email"
                  />
                )}

                <AuthField
                  className="mt-6"
                  label={isLogin ? "Password" : "New password"}
                  type={showPw ? "text" : "password"}
                  value={password}
                  onChange={setPassword}
                  placeholder="••••••••"
                  autoComplete={isLogin ? "current-password" : "new-password"}
                  adornment={showHide}
                />

                {!isLogin && (
                  <AuthField
                    className="mt-6"
                    label="Confirm password"
                    type={showPw ? "text" : "password"}
                    value={confirm}
                    onChange={setConfirm}
                    placeholder="••••••••"
                    autoComplete="new-password"
                  />
                )}

                {mismatch && (
                  <p className="mt-2 animate-auth-swap font-sans text-[0.76rem] text-destructive">
                    Passwords don't match.
                  </p>
                )}

                <button
                  type="submit"
                  disabled={!canSubmit}
                  className="group/btn mt-8 flex w-full items-center justify-center gap-2 rounded-lg bg-ink px-4 py-3 font-sans text-[0.9rem] font-medium text-paper transition duration-200 hover:bg-ink-soft disabled:bg-paper-5 disabled:text-ink-faint"
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

        {/* switch — flips mode in place (no navigation → no remount → smooth) */}
        <div key={`switch-${mode}`} className="mt-6 animate-auth-swap text-center [animation-delay:120ms]">
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
          className="mt-8 flex animate-auth-swap items-center justify-center gap-2 text-center font-sans text-[0.76rem] text-ink-faint [animation-delay:180ms]"
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

      {/* ambient brand watermark, bottom-right */}
      <div className="brand-watermark" aria-hidden="true">◐</div>
    </div>
  );
}
