import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router";
import {
  clearBrandTokens,
  hasStoredAccessToken,
  requestJson,
  setUnauthorizedHandler,
  storeBrandAccessToken,
  type ApiResponse,
} from "./api";
import { AuthContext, type AuthContextValue, type BrandSession, type LoginCredentials } from "./auth-context";

type LoginResponse = BrandSession & {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};

const SESSION_EXPIRED_MESSAGE = "Сессия истекла. Войдите снова.";

function requestErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Не удалось выполнить вход.";
}

function currentPath(location: ReturnType<typeof useLocation>): string {
  return `${location.pathname}${location.search}`;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [session, setSession] = useState<BrandSession | null>(null);
  const [status, setStatus] = useState<AuthContextValue["status"]>(
    hasStoredAccessToken() ? "checking" : "unauthenticated",
  );
  const [authError, setAuthError] = useState<string | null>(null);

  const recoverUnauthorized = useCallback(() => {
    clearBrandTokens();
    setSession(null);
    setStatus("unauthenticated");
    setAuthError(SESSION_EXPIRED_MESSAGE);

    if (location.pathname !== "/login") {
      navigate("/login", {
        replace: true,
        state: {
          authError: SESSION_EXPIRED_MESSAGE,
          from: currentPath(location),
        },
      });
    }
  }, [location, navigate]);

  useEffect(() => setUnauthorizedHandler(recoverUnauthorized), [recoverUnauthorized]);

  useEffect(() => {
    if (!hasStoredAccessToken()) {
      setSession(null);
      setStatus("unauthenticated");
      return;
    }

    let ignore = false;

    setStatus("checking");
    requestJson<ApiResponse<BrandSession>>("/brand-portal/me")
      .then((response) => {
        if (ignore) return;
        setSession(response.data);
        setAuthError(null);
        setStatus("authenticated");
      })
      .catch((error: unknown) => {
        if (ignore) return;
        clearBrandTokens();
        setSession(null);
        setAuthError(requestErrorMessage(error));
        setStatus("unauthenticated");
      });

    return () => {
      ignore = true;
    };
  }, []);

  const login = useCallback(async (credentials: LoginCredentials) => {
    setAuthError(null);

    try {
      const loginResponse = await requestJson<ApiResponse<LoginResponse>>("/brand-portal/auth/login", {
        auth: false,
        body: {
          email: credentials.email,
          password: credentials.password,
        },
        method: "POST",
        recoverUnauthorized: false,
      });

      storeBrandAccessToken(loginResponse.data.access_token);
      const sessionResponse = await requestJson<ApiResponse<BrandSession>>("/brand-portal/me");
      setSession(sessionResponse.data);
      setAuthError(null);
      setStatus("authenticated");
    } catch (error) {
      clearBrandTokens();
      setSession(null);
      setStatus("unauthenticated");
      const message = requestErrorMessage(error);
      setAuthError(message);
      throw new Error(message);
    }
  }, []);

  const logout = useCallback(() => {
    clearBrandTokens();
    setSession(null);
    setAuthError(null);
    setStatus("unauthenticated");
    navigate("/login", { replace: true });
  }, [navigate]);

  const value = useMemo<AuthContextValue>(
    () => ({
      authError,
      login,
      logout,
      session,
      status,
    }),
    [authError, login, logout, session, status],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
