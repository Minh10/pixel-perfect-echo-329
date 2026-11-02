import { createFileRoute, redirect } from "@tanstack/react-router";

// Retain old links without exposing account-management UI in the public demo.
export const Route = createFileRoute("/reset-password")({
  beforeLoad: () => {
    throw redirect({ to: "/", replace: true });
  },
  head: () => ({
    meta: [
      { title: "Sample workspace — FINAUDIT AI" },
      { name: "description", content: "Public FINAUDIT AI financial-report demonstration." },
      { property: "og:title", content: "Sample workspace — FINAUDIT AI" },
      { property: "og:description", content: "Public FINAUDIT AI financial-report demonstration." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
});
