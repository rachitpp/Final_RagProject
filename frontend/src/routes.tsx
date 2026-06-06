import { lazy, Suspense } from "react";
import { Outlet } from "react-router-dom";

// Route-level code-splitting: the chat screen pulls in react-markdown + remark-gfm
// (a large dependency the auth screen never needs), so each page becomes its own
// chunk and the first load only fetches the route actually being viewed.
export const ChatPage = lazy(() => import("@/pages/ChatPage"));
export const AuthPage = lazy(() => import("@/pages/AuthPage"));

/** Brand-matched placeholder shown while a route chunk loads. */
function PageFallback() {
  return (
    <div className="flex h-screen items-center justify-center bg-paper text-ink">
      <span className="glyph-breathe font-serif text-3xl" aria-hidden="true">
        ◐
      </span>
      <span className="sr-only">Loading…</span>
    </div>
  );
}

/** One Suspense boundary wrapping every lazy route. */
export function RootLayout() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Outlet />
    </Suspense>
  );
}
