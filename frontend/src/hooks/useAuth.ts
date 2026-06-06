import { createContext, useContext } from "react";
import type { Profile } from "@/lib/api";

/**
 * Shared auth state. The single source of truth is the <AuthProvider> (see
 * AuthProvider.tsx); this module just holds the Context + the `useAuth` hook so
 * components can read/update it. The `profile` (name/band) is fetched from
 * /auth/me for display only — personalization stays server-authoritative.
 */
export interface AuthValue {
  isAuthenticated: boolean;
  profile: Profile | null;
  login: (employeeId: string, password: string) => Promise<void>;
  activate: (employeeId: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthValue | null>(null);

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an <AuthProvider>");
  }
  return ctx;
}
