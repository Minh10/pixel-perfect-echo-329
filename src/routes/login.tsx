import { createFileRoute, redirect } from "@tanstack/react-router";

// Retain old links without exposing account-management UI in the public demo.
export const Route = createFileRoute("/login")({
  beforeLoad: () => {
    throw redirect({ to: "/", replace: true });
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
});
