import { createFileRoute } from "@tanstack/react-router";
import { handleDemoSession } from "@/lib/demo-session";
export const Route = createFileRoute("/api/public/demo-session")({
  server: { handlers: ({ createHandlers }) => createHandlers({ ANY: ({ request }) => handleDemoSession(request, {
    demoEnabled: process.env["FINAUDIT_TEMPORARY_DEMO_ENABLED"],
    demoSecret: process.env["FINAUDIT_DEMO_SESSION_SECRET"],
    backendUrl: process.env["FINAUDIT_BACKEND_URL"],
    backendToken: process.env["FINAUDIT_API_TOKEN"],
  }) }) },
});