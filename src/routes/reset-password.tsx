import { useEffect, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const Route = createFileRoute("/reset-password")({
  head: () => ({
    meta: [
      { title: "Reset password — FINAUDIT AI" },
      { name: "description", content: "Reset your authorized FINAUDIT AI account password." },
      { property: "og:title", content: "Reset password — FINAUDIT AI" },
      {
        property: "og:description",
        content: "Reset your authorized FINAUDIT AI account password.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: ResetPassword,
});
function ResetPassword() {
  const [recovery, setRecovery] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  useEffect(() => {
    const hash = new URLSearchParams(window.location.hash.slice(1));
    setRecovery(hash.get("type") === "recovery");
    let cleanup: (() => void) | undefined;
    void import("@/integrations/supabase/client").then(({ supabase }) => {
      const { data } = supabase.auth.onAuthStateChange((event) => {
        if (event === "PASSWORD_RECOVERY") setRecovery(true);
      });
      cleanup = () => data.subscription.unsubscribe();
    });
    return () => cleanup?.();
  }, []);
  return (
    <div className="page-layout">
      <section className="mx-auto mt-12 max-w-sm space-y-5">
        <h1 className="text-2xl font-semibold">Reset password</h1>
        {!recovery ? (
          <p className="text-sm text-muted-foreground">
            Open the password reset link from your email.
          </p>
        ) : (
          !done && (
            <form
              className="space-y-4"
              onSubmit={async (event) => {
                event.preventDefault();
                if (password !== confirmation) {
                  setMessage("Passwords do not match.");
                  return;
                }
                setBusy(true);
                try {
                  const { supabase } = await import("@/integrations/supabase/client");
                  const { error } = await supabase.auth.updateUser({ password });
                  if (error) {
                    setMessage(
                      "Password could not be updated. Request a new reset link or choose a stronger password.",
                    );
                    return;
                  }
                  await supabase.auth.signOut();
                  setDone(true);
                  setPassword("");
                  setConfirmation("");
                  setMessage("Password updated. Sign in with your new password.");
                } finally {
                  setBusy(false);
                }
              }}
            >
              <Label htmlFor="new-password">New password</Label>
              <Input
                id="new-password"
                type="password"
                autoComplete="new-password"
                minLength={8}
                maxLength={256}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <Label htmlFor="confirm-password">Confirm password</Label>
              <Input
                id="confirm-password"
                type="password"
                autoComplete="new-password"
                required
                value={confirmation}
                onChange={(e) => setConfirmation(e.target.value)}
              />
              <Button disabled={busy} type="submit">
                Update password
              </Button>
            </form>
          )
        )}
        {message && (
          <p role="status" className="text-sm text-muted-foreground">
            {message}
          </p>
        )}
        <Button variant="outline" asChild>
          <Link to="/login">Return to sign-in</Link>
        </Button>
      </section>
    </div>
  );
}
