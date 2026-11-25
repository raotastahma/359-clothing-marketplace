import { createContext, useContext } from "react";

export type BrandPortalRole = "owner" | "manager" | "viewer" | string;

export type BrandSession = {
  brand: {
    id: string;
    name: string;
    slug: string;
    logo_url?: string | null;
    commission_rate?: number | null;
  };
  role: BrandPortalRole;
};

export type LoginCredentials = {
  email: string;
  password: string;
};

export type AuthStatus = "checking" | "authenticated" | "unauthenticated";

export type AuthContextValue = {
  authError: string | null;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
  session: BrandSession | null;
  status: AuthStatus;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider.");
  return context;
}
