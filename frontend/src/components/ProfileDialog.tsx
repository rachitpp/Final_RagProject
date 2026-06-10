import { Dialog } from "radix-ui";
import {
  CalendarDays,
  FileText,
  Globe,
  Plane,
  X,
  type LucideIcon,
} from "lucide-react";
import type { LibraryInfo, Profile } from "@/lib/api";

const TOPIC_ICONS: Record<string, LucideIcon> = {
  domestic: Plane,
  foreign: Globe,
  leave: CalendarDays,
};

/** "Chirag Grover" -> "CG". */
function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "•";
}

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  user: Profile | null;
  /** Indexed documents — shown as the user's policy access. */
  lib: LibraryInfo | null;
}

/** A read-only identity card: who's signed in, their band/role, and the policies
 *  their answers are scoped against. Makes the server-side personalization the
 *  app already does visible to the user. */
export default function ProfileDialog({ open, onOpenChange, user, lib }: Props) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-[2px] data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-rule-strong bg-paper-4 p-7 shadow-[0_24px_64px_-24px_rgba(0,0,0,0.7)] outline-none data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95">
          <Dialog.Close asChild>
            <button
              type="button"
              aria-label="Close"
              className="absolute right-4 top-4 rounded-md p-1.5 text-ink-faint transition duration-200 hover:bg-paper-3 hover:text-ink"
            >
              <X className="h-4 w-4" />
            </button>
          </Dialog.Close>

          {/* identity */}
          <div className="flex items-center gap-4">
            <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-ink font-serif text-lg font-semibold text-paper">
              {user ? initials(user.name) : "•"}
            </span>
            <div className="min-w-0">
              <Dialog.Title className="truncate font-serif text-xl font-bold tracking-tight text-ink">
                {user?.name ?? "Account"}
              </Dialog.Title>
              <Dialog.Description className="mt-0.5 truncate font-sans text-[0.82rem] text-ink-muted">
                {user?.employee_id ?? "—"}
              </Dialog.Description>
            </div>
          </div>

          {/* attributes */}
          <dl className="mt-6 grid grid-cols-2 gap-3">
            <div className="rounded-xl border border-rule bg-paper-3/40 px-4 py-3">
              <dt className="font-sans text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-ink-faint">
                Band
              </dt>
              <dd className="mt-1 font-serif text-lg font-bold text-ink">
                {user ? user.band : "—"}
              </dd>
            </div>
            <div className="rounded-xl border border-rule bg-paper-3/40 px-4 py-3">
              <dt className="font-sans text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-ink-faint">
                Role
              </dt>
              <dd className="mt-1 font-serif text-lg font-bold capitalize text-ink">
                {user?.role ?? "—"}
              </dd>
            </div>
          </dl>

          {/* policy access */}
          <div className="mt-6">
            <div className="font-sans text-[0.62rem] font-semibold uppercase tracking-[0.18em] text-ink-faint">
              Policy access
            </div>
            {lib && lib.documents.length > 0 ? (
              <ul className="mt-2.5 flex flex-col gap-1.5">
                {lib.documents.map((d) => {
                  const Icon = TOPIC_ICONS[d.topic] ?? FileText;
                  return (
                    <li
                      key={d.name}
                      className="flex items-center gap-2.5 font-sans text-[0.84rem] text-ink-soft"
                    >
                      <Icon className="h-4 w-4 shrink-0 text-gold" />
                      <span className="truncate">{d.title || d.name}</span>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="mt-2 font-sans text-[0.8rem] text-ink-faint">
                No policies available.
              </p>
            )}
          </div>

          <p className="mt-6 border-t border-rule pt-4 font-sans text-[0.74rem] leading-relaxed text-ink-faint">
            Your band and role are resolved from the HR roster and applied
            automatically — answers are tailored to your entitlements.
          </p>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
