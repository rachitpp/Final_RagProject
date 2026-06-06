import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import {
  createBrowserRouter,
  Navigate,
  RouterProvider,
} from "react-router-dom";
import { Toaster } from "sonner";
import "./index.css";
import { RequireAuth, RequireAnon } from "@/components/guards";
import { AuthProvider } from "@/hooks/AuthProvider";
import { AuthPage, ChatPage, RootLayout } from "@/routes";

const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      {
        path: "/",
        element: (
          <RequireAuth>
            <ChatPage />
          </RequireAuth>
        ),
      },
      {
        path: "/login",
        element: (
          <RequireAnon>
            <AuthPage initialMode="login" />
          </RequireAnon>
        ),
      },
      {
        path: "/activate",
        element: (
          <RequireAnon>
            <AuthPage initialMode="activate" />
          </RequireAnon>
        ),
      },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
    <Toaster
      position="bottom-right"
      duration={2600}
      offset={16}
      toastOptions={{
        style: {
          background: "var(--paper-4)",
          color: "var(--ink)",
          border: "1px solid var(--rule-strong)",
          borderRadius: "12px",
          fontFamily: "var(--font-sans)",
          fontSize: "0.84rem",
          boxShadow: "0 12px 32px -12px rgba(0,0,0,0.55)",
        },
      }}
    />
  </StrictMode>,
);
