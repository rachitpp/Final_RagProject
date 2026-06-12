import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  activate as apiActivate,
  AuthError,
  fetchMe,
  getToken,
  login as apiLogin,
  logout as apiLogout,
  type Profile,
} from "@/lib/api";
import { AuthContext } from "./useAuth";

/**
 * Single source of truth for auth state, wrapped around the router root.
 *
 * `isAuthenticated` mirrors the presence of the JWT in localStorage. A `storage`
 * listener keeps tabs in sync: signing out (or in) in one tab updates the others,
 * since `storage` events fire in every tab EXCEPT the one that made the change
 * (that one is updated directly by the action below).
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(
    () => getToken() !== null,
  );
  const [profile, setProfile] = useState<Profile | null>(null);
  // Bumped when another tab swaps the token while we stay "authenticated"
  // (sign-out + different sign-in over there): same boolean, different user —
  // the profile must refetch so this tab re-keys onto the right person.
  const [sessionEpoch, setSessionEpoch] = useState(0);

  const logout = useCallback(() => {
    apiLogout();
    setProfile(null);
    setIsAuthenticated(false);
  }, []);

  // Load the display profile whenever we're authenticated (on mount with a
  // stored token, and right after login/activate). A 401 here means the stored
  // token is dead → sign out cleanly. Profile is cleared in the events that drop
  // auth (logout / cross-tab sync), not here, so the effect makes no synchronous
  // setState of its own.
  useEffect(() => {
    if (!isAuthenticated) return;
    let cancelled = false;
    fetchMe()
      .then((p) => !cancelled && setProfile(p))
      .catch((err) => {
        if (!cancelled && err instanceof AuthError) logout();
      });
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, sessionEpoch, logout]);

  useEffect(() => {
    // Recompute from storage on any change in another tab (covers token
    // set/remove and localStorage.clear()). Cheap, so we don't filter by key.
    const sync = () => {
      const authed = getToken() !== null;
      setIsAuthenticated(authed);
      if (!authed) setProfile(null);
      // Still authed ≠ same user: the other tab may have signed in as someone
      // else. Re-resolve the profile from the (possibly new) token.
      else setSessionEpoch((e) => e + 1);
    };
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);

  const login = useCallback(async (employeeId: string, password: string) => {
    await apiLogin(employeeId, password);
    setIsAuthenticated(true);
  }, []);

  const activate = useCallback(
    async (employeeId: string, email: string, password: string) => {
      await apiActivate(employeeId, email, password);
      setIsAuthenticated(true);
    },
    [],
  );

  // Memoized so context consumers don't re-render on every AuthProvider render
  // (the callbacks are already stable; only auth state changes flip this).
  const value = useMemo(
    () => ({ isAuthenticated, profile, login, activate, logout }),
    [isAuthenticated, profile, login, activate, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
