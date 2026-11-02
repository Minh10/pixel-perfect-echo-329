import { createFileRoute } from "@tanstack/react-router";
import { proxyDocumentRequest } from "@/lib/api/document-proxy";

async function handle({ request, params }: { request: Request; params: { _splat?: string } }) {
  return proxyDocumentRequest(request, params._splat ?? "", {
    backendUrl: process.env["FINAUDIT_BACKEND_URL"],
    backendToken: process.env["FINAUDIT_API_TOKEN"],
    authorizedUserId: process.env["FINAUDIT_AUTHORIZED_USER_ID"],
    authUrl: process.env["SUPABASE_URL"],
    authKey: process.env["SUPABASE_PUBLISHABLE_KEY"],
  });
}

export const Route = createFileRoute("/api/document-service/$")({
  server: { handlers: { GET: handle, POST: handle, DELETE: handle } },
});