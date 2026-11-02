import { useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { useQueryClient } from "@tanstack/react-query";
import { LogIn } from "lucide-react";
import { signIn } from "@/lib/auth.functions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Administrator sign-in — FINAUDIT AI" },
      {
        name: "description",
        content: "Authorized account access to the private FINAUDIT AI workspace.",
      },
      { property: "og:title", content: "Administrator sign-in — FINAUDIT AI" },
      {
        property: "og:description",
        content: "Authorized account access to the private FINAUDIT AI workspace.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Login,
});

function Login() {
  const login = useServerFn(signIn);
  const navigate = useNavigate();
  const queries = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  return (
    <div className="page-layout">
      <section className="mx-auto mt-12 max-w-sm space-y-6">
        <div>
          <h1 className="text-2xl font-semibold">Administrator sign-in</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            FINAUDIT AI · Private document processing
          </p>
        </div>
        <form
          className="space-y-4"
          onSubmit={async (event) => {
            event.preventDefault();
            setBusy(true);
            setError("");
            try {
              const result = await login({ data: { email, password } });
              if (!result.success) {
                setError(result.message);
                return;
              }
              setPassword("");
              await queries.invalidateQueries({ queryKey: ["owner-session"] });
              await navigate({ to: "/" });
            } catch {
              setError("Sign-in is unavailable. Please try again.");
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="space-y-2">
            <Label htmlFor="owner-email">Email</Label>
            <Input
              id="owner-email"
              type="email"
              autoComplete="username"
              required
              maxLength={254}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="owner-password">Password</Label>
            <Input
              id="owner-password"
              type="password"
              autoComplete="current-password"
              required
              minLength={12}
              maxLength={256}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <Button type="submit" className="w-full" disabled={busy}>
            <LogIn />
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>
        <Button
          variant="link"
          disabled={busy || !email}
          onClick={async () => {
            const { supabase } = await import("@/integrations/supabase/client");
            const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
              redirectTo: `${window.location.origin}/reset-password`,
            });
            setNotice(
              resetError
                ? "Password reset is unavailable. Try again later."
                : "If this account exists, a password reset email has been sent.",
            );
          }}
        >
          Forgot password?
        </Button>
        {notice && (
          <p role="status" className="text-sm text-muted-foreground">
            {notice}
          </p>
        )}
        <Button variant="outline" asChild>
          <Link to="/">View sample preview</Link>
        </Button>
      </section>
    </div>
  );
}
