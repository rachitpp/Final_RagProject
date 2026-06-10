import { type KeyboardEvent, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Minimal underline field: an uppercase label over a borderless input whose only
 * chrome is a bottom hairline. On focus the line AND the label light gold, with
 * a soft halo under the line, so the active field reads from across the room.
 * `invalid` tints label + line destructive (cleared by the caller on retype).
 * `adornment` renders at the right of the line (e.g. the password Show/Hide).
 */
export default function AuthField({
  label,
  type = "text",
  value,
  onChange,
  placeholder,
  autoComplete,
  adornment,
  className,
  autoFocus,
  invalid,
  onKeyDown,
  onKeyUp,
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoComplete?: string;
  adornment?: ReactNode;
  className?: string;
  autoFocus?: boolean;
  invalid?: boolean;
  onKeyDown?: (e: KeyboardEvent<HTMLInputElement>) => void;
  onKeyUp?: (e: KeyboardEvent<HTMLInputElement>) => void;
}) {
  return (
    <label className={cn("group block", className)}>
      <span
        className={cn(
          "block font-sans text-[0.68rem] font-semibold uppercase tracking-[0.16em] transition-colors duration-200",
          invalid ? "text-destructive" : "text-ink-faint group-focus-within:text-gold",
        )}
      >
        {label}
      </span>
      <div
        className={cn(
          "mt-1 flex items-center gap-3 border-b transition-[border-color,box-shadow] duration-200",
          invalid
            ? "border-destructive"
            : "border-rule-strong focus-within:border-gold focus-within:[box-shadow:0_12px_24px_-12px_var(--focus-halo)]",
        )}
      >
        <input
          autoFocus={autoFocus}
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          onKeyUp={onKeyUp}
          placeholder={placeholder}
          autoComplete={autoComplete}
          className="w-full bg-transparent py-2.5 font-sans text-[0.98rem] text-ink outline-none placeholder:text-ink-faint"
        />
        {adornment}
      </div>
    </label>
  );
}
