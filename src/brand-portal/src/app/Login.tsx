import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";
import logoSrc from "../imports/logo_359.svg";
import { useAuth } from "./auth-context";
import { Button } from "./components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./components/ui/card";
import { Input } from "./components/ui/input";
import { Label } from "./components/ui/label";

type LoginLocationState = {
  authError?: string | null;
  from?: string;
};

function loginRedirectPath(state: unknown): string {
  const from = (state as LoginLocationState | null)?.from;
  if (!from || from === "/login") return "/";
  return from;
}

function loginStateError(state: unknown): string | null {
  return (state as LoginLocationState | null)?.authError ?? null;
}

export function Login() {
  const location = useLocation();
  const navigate = useNavigate();
  const { authError, login, status } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const redirectTo = useMemo(() => loginRedirectPath(location.state), [location.state]);
  const stateError = useMemo(() => loginStateError(location.state), [location.state]);
  const visibleError = formError ?? stateError ?? authError;

  useEffect(() => {
    if (status === "authenticated") {
      navigate(redirectTo, { replace: true });
    }
  }, [navigate, redirectTo, status]);

  const submitLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    setIsSubmitting(true);

    try {
      await login({
        email: email.trim(),
        password,
      });
      navigate(redirectTo, { replace: true });
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось выполнить вход.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (status === "authenticated") {
    return <Navigate to={redirectTo} replace />;
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
      <Card className="w-full max-w-[400px]">
        <CardHeader className="space-y-5 pb-4">
          <div className="flex items-center gap-3">
            <img src={logoSrc} alt="359" className="h-8 w-auto" />
            <div className="text-[11px] uppercase leading-none tracking-wider text-muted-foreground">
              Brand Portal
            </div>
          </div>
          <div>
            <CardTitle className="text-xl text-foreground">Вход для бренда</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">Введите email и пароль, чтобы открыть кабинет.</p>
          </div>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={submitLogin}>
            <div className="space-y-2">
              <Label htmlFor="brand-email">Email</Label>
              <Input
                id="brand-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                disabled={isSubmitting || status === "checking"}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="brand-password">Пароль</Label>
              <Input
                id="brand-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                disabled={isSubmitting || status === "checking"}
              />
            </div>

            {visibleError && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {visibleError}
              </div>
            )}

            <Button type="submit" className="w-full" disabled={isSubmitting || status === "checking"}>
              {isSubmitting || status === "checking" ? "Входим..." : "Войти"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
