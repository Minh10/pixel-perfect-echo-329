import { useState } from "react";
import { createFileRoute, Link, redirect, useNavigate } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DemoBadge } from "@/components/app/states";
import { acceptsDemoEntry, setDemoEntry } from "@/lib/demo-entry";
import { DEFAULT_DOCUMENT_ID, IS_DEMO } from "@/lib/api/service";

// Sample UX only: never calls real sign-in, creates cookies, or unlocks the proxy.
export const Route = createFileRoute("/login")({
  beforeLoad: () => {
    if (!IS_DEMO) throw redirect({ to: "/", replace: true });
  },
  head: () => ({
    meta: [
      { title: "Demo workspace — FINAUDIT AI" },
      { name: "description", content: "Public FINAUDIT AI financial-report demonstration." },
      { property: "og:title", content: "Demo workspace — FINAUDIT AI" },
      { property: "og:description", content: "Public FINAUDIT AI financial-report demonstration." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: DemoEntry,
});

function DemoEntry() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  return (
    <div className="page-layout">
      <section className="mx-auto mt-12 max-w-sm space-y-6">
        <div className="space-y-2">
          <DemoBadge />
          <h1 className="text-2xl font-semibold">Demo entry</h1>
          <p className="text-sm text-muted-foreground">
            Public sample only. Use admin / admin. Not secure authentication; no private reports
            or paid processing access.
          </p>
        </div>
        <form
          className="space-y-4"
          onSubmit={async (event) => {
            event.preventDefault();
            if (!acceptsDemoEntry(username, password)) {
              setError("Use admin / admin for the sample demo.");
              return;
            }
            if (!DEFAULT_DOCUMENT_ID) return;
            setDemoEntry(true);
            setPassword("");
            await navigate({
              to: "/intelligence",
              search: { doc: DEFAULT_DOCUMENT_ID },
              replace: true,
            });
          }}
        >
          <div className="space-y-2">
            <Label htmlFor="demo-username">Username</Label>
            <Input id="demo-username" autoComplete="off" required maxLength={40}
              value={username} onChange={(event) => setUsername(event.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="demo-password">Password</Label>
            <Input id="demo-password" type="password" autoComplete="off" required maxLength={40}
              value={password} onChange={(event) => setPassword(event.target.value)} />
          </div>
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full">Enter sample demo</Button>
        </form>
        <Button asChild variant="outline" className="w-full">
          <Link to="/">Continue without entry</Link>
        </Button>
      </section>
    </div>
  );
}
