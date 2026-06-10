import { useCallback, useEffect, useState } from "react";
import { DropdownMenu } from "radix-ui";
import {
  CalendarDays,
  ChevronDown,
  FileText,
  Globe,
  LogOut,
  Moon,
  Plane,
  Plus,
  RotateCw,
  Sun,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import { fetchLibrary, type LibraryInfo, type Profile } from "@/lib/api";
import type { Conversation } from "@/lib/conversations";
import ConversationList from "@/components/ConversationList";
import ProfileDialog from "@/components/ProfileDialog";

/** First letters of the first two name parts, e.g. "Chirag Grover" -> "CG". */
function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "•";
}

/** Topic key (the backend registry's retrieval scope) -> sidebar icon. The
 *  display title itself comes straight from the backend, not parsed here. */
const TOPIC_ICONS: Record<string, LucideIcon> = {
  domestic: Plane,
  foreign: Globe,
  leave: CalendarDays,
};

export interface SidebarProps {
  onNewChat: () => void;
  disabled: boolean;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onSignOut: () => void;
  user: Profile | null;
  conversations: Conversation[];
  activeId: string;
  onSelectConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  onRenameConversation: (id: string, title: string) => void;
  /** Called after an action that should dismiss the mobile drawer (e.g. New chat). */
  onNavigate?: () => void;
}

/**
 * The sidebar's inner content (brand, library, account, theme). Rendered both in
 * the fixed desktop rail (`<Sidebar>`) and inside the mobile slide-in drawer, so
 * it lives in its own component and the host supplies the panel chrome + layout.
 */
export function SidebarContent({
  onNewChat,
  disabled,
  theme,
  onToggleTheme,
  onSignOut,
  user,
  conversations,
  activeId,
  onSelectConversation,
  onDeleteConversation,
  onRenameConversation,
  onNavigate,
}: SidebarProps) {
  const [lib, setLib] = useState<LibraryInfo | null>(null);
  const [libError, setLibError] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);

  // State is set only inside the async then/catch — never synchronously in the
  // effect body — so loading the library doesn't trigger a cascading render.
  const refreshLibrary = useCallback(() => {
    fetchLibrary()
      .then((l) => {
        setLib(l);
        setLibError(false);
      })
      .catch(() => setLibError(true));
  }, []);

  useEffect(() => {
    refreshLibrary();
  }, [refreshLibrary]);

  // Retry is an event handler, so the eager error reset (for the loading state)
  // is fine here.
  const onRetryLibrary = () => {
    setLibError(false);
    refreshLibrary();
  };

  const handleNewChat = () => {
    onNewChat();
    onNavigate?.();
  };

  return (
    <>
      <div className="font-serif text-xl font-bold tracking-tight text-ink">
        <span className="text-gold" aria-hidden="true">◐</span> Policy Assistant
      </div>
      <p className="mt-1 font-sans text-[0.82rem] leading-relaxed text-ink-muted">
        Travel &amp; leave, answered for you.
      </p>

      <button
        type="button"
        onClick={handleNewChat}
        disabled={disabled}
        className="mt-5 inline-flex items-center justify-center gap-2 rounded-lg border border-rule-strong px-3 py-2 font-sans text-sm text-ink transition duration-200 hover:bg-paper-3 disabled:opacity-50"
      >
        <Plus className="h-4 w-4" /> New chat
      </button>

      <div className="mt-6 border-t border-rule pt-4">
        <div className="font-sans text-[0.62rem] font-semibold uppercase tracking-[0.18em] text-ink-faint">
          Chats
        </div>
        <ConversationList
          conversations={conversations}
          activeId={activeId}
          disabled={disabled}
          onSelect={onSelectConversation}
          onDelete={onDeleteConversation}
          onRename={onRenameConversation}
          onAfterSelect={onNavigate}
        />
      </div>

      <div className="mt-6 border-t border-rule pt-4">
        <div className="font-sans text-[0.62rem] font-semibold uppercase tracking-[0.18em] text-ink-faint">
          Policies
        </div>

        {libError ? (
          <div className="mt-2 rounded-md border border-rule bg-paper-3/40 px-2.5 py-2 font-sans text-[0.76rem] text-ink-muted">
            Couldn't load your policies.
            <button
              type="button"
              onClick={onRetryLibrary}
              className="mt-1.5 inline-flex items-center gap-1 font-medium text-ink-soft transition duration-200 hover:text-gold"
            >
              <RotateCw className="h-3 w-3" /> Retry
            </button>
          </div>
        ) : !lib ? (
          <div className="mt-2 font-sans text-xs text-ink-muted">Loading…</div>
        ) : (
          <ul className="mt-2 flex max-h-[26vh] flex-col gap-px overflow-y-auto">
            {lib.documents.map((d) => {
              const Icon = TOPIC_ICONS[d.topic] ?? FileText;
              return (
                <li
                  key={d.name}
                  title={d.name}
                  className="group flex items-center gap-2.5 rounded-md px-1.5 py-1.5 font-sans text-[0.82rem] text-ink-soft transition duration-200 hover:bg-paper-3 hover:text-ink"
                >
                  <Icon className="h-4 w-4 shrink-0 text-ink-faint transition group-hover:text-gold" />
                  <span className="flex-1 truncate">{d.title || d.name}</span>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="mt-auto border-t border-rule pt-4">
        {/* user identity block — doubles as the sign-out menu trigger */}
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              type="button"
              className="group flex w-full items-center gap-2.5 rounded-lg px-1.5 py-1.5 text-left transition duration-200 hover:bg-paper-3"
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ink font-serif text-[0.78rem] font-semibold text-paper">
                {user ? initials(user.name) : "•"}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-sans text-[0.86rem] font-medium text-ink">
                  {user?.name ?? "Account"}
                </span>
                {user && (
                  <span className="block truncate font-sans text-[0.72rem] text-ink-faint">
                    {user.employee_id} · Band {user.band}
                  </span>
                )}
              </span>
              <ChevronDown className="h-4 w-4 shrink-0 text-ink-faint transition-transform duration-200 group-data-[state=open]:rotate-180" />
            </button>
          </DropdownMenu.Trigger>

          <DropdownMenu.Portal>
            <DropdownMenu.Content
              side="top"
              align="start"
              sideOffset={8}
              className="z-50 w-[var(--radix-dropdown-menu-trigger-width)] overflow-hidden rounded-xl border border-rule-strong bg-paper-4 shadow-[0_12px_32px_-12px_rgba(0,0,0,0.55)] data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
            >
              <DropdownMenu.Item
                // Defer opening until the menu has closed, so focus returns
                // cleanly before the dialog traps it.
                onSelect={() => setTimeout(() => setProfileOpen(true), 0)}
                className="flex cursor-pointer items-center gap-2 px-3.5 py-2.5 text-left font-sans text-[0.84rem] text-ink outline-none transition duration-200 data-[highlighted]:bg-paper-3"
              >
                <UserRound className="h-4 w-4 text-ink-faint" /> View profile
              </DropdownMenu.Item>
              <DropdownMenu.Separator className="my-1 h-px bg-rule" />
              <DropdownMenu.Item
                onSelect={onSignOut}
                className="flex cursor-pointer items-center gap-2 px-3.5 py-2.5 text-left font-sans text-[0.84rem] text-ink outline-none transition duration-200 data-[highlighted]:bg-paper-3"
              >
                <LogOut className="h-4 w-4 text-ink-faint" /> Sign out
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        <ProfileDialog
          open={profileOpen}
          onOpenChange={setProfileOpen}
          user={user}
          lib={lib}
        />

        {/* status + theme toggle */}
        <div className="mt-3 flex items-center justify-between">
          <div className="flex items-center gap-2 font-sans text-xs text-ink-faint">
            <span className="status-dot" aria-hidden="true" />
            <span>
              {lib ? (
                <>
                  Ready · <span className="text-ink-muted">{lib.model}</span>
                </>
              ) : libError ? (
                "Offline"
              ) : (
                "Connecting…"
              )}
            </span>
          </div>
          <button
            type="button"
            onClick={onToggleTheme}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            className="rounded-md p-1.5 text-ink-faint transition duration-200 hover:bg-paper-3 hover:text-ink"
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </>
  );
}

/** The fixed desktop rail. Hidden below `md`, where the mobile drawer takes over. */
export default function Sidebar(props: SidebarProps) {
  return (
    <aside className="z-10 hidden w-72 shrink-0 flex-col border-r border-rule bg-paper-2 px-5 py-7 md:flex">
      <SidebarContent {...props} />
    </aside>
  );
}
