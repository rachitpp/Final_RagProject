import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import "./index.css";
import ChatPage from "@/pages/ChatPage";
import AuthPage from "@/pages/AuthPage";

const router = createBrowserRouter([
  { path: "/", element: <ChatPage /> },
  { path: "/login", element: <AuthPage initialMode="login" /> },
  { path: "/activate", element: <AuthPage initialMode="activate" /> },
  { path: "*", element: <Navigate to="/" replace /> },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
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
