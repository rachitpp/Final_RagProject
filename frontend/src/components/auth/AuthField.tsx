import { type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Minimal underline field: an uppercase label over a borderless input whose only
 * chrome is a bottom hairline that lights gold on focus. `adornment` renders at
 * the right of the line (e.g. the password Show/Hide toggle).
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
}) {
  return (
    <label className={cn("block", className)}>
      <span className="block font-sans text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-ink-faint">
        {label}
      </span>
      <div className="mt-1 flex items-center gap-3 border-b border-rule-strong transition-colors duration-200 focus-within:border-gold">
        <input
          autoFocus={autoFocus}
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
          className="w-full bg-transparent py-2.5 font-sans text-[0.98rem] text-ink outline-none placeholder:text-ink-faint"
        />
        {adornment}
      </div>
    </label>
  );
}
