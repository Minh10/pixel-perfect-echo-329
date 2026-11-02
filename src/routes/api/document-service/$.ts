import { createFileRoute } from "@tanstack/react-router";
import { proxyDocumentRequest } from "@/lib/api/document-proxy";

export const Route = createFileRoute("/api/document-service/$")({
  server: {
    handlers: ({ createHandlers }) =>
      createHandlers({
        ANY: async ({ request, params }) =>
          proxyDocumentRequest(request, params._splat ?? "", {
            backendUrl: process.env["FINAUDIT_BACKEND_URL"],
            backendToken: process.env["FINAUDIT_API_TOKEN"],
            authorizedUserId: process.env["FINAUDIT_AUTHORIZED_USER_ID"],
            authUrl: process.env["SUPABASE_URL"],
            authKey: process.env["SUPABASE_PUBLISHABLE_KEY"],
          }),
      }),
  },
});
