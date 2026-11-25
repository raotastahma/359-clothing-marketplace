import { type ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { useAuth } from "./auth-context";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { authError, status } = useAuth();

  if (status === "checking") {
    return (
      <div className="flex h-screen items-center justify-center bg-muted/30">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-primary" />
      </div>
    );
  }

  if (status !== "authenticated") {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          authError,
          from: `${location.pathname}${location.search}`,
        }}
      />
    );
  }

  return children;
}
