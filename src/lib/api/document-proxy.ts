import { createServerOnlyFn } from "@tanstack/react-start";
import { createClient } from "@supabase/supabase-js";
import { allowedProxyPath, authorizedUser, configuredBackend } from "./proxy-policy";
import { AUTH_COOKIE } from "../auth-policy";

interface ProxyConfig {
  backendUrl?: string | undefined;
  backendToken?: string | undefined;
  authorizedUserId?: string | undefined;
  authUrl?: string | undefined;
  authKey?: string | undefined;
}

const failure = (status: number, code: string, message: string) =>
  Response.json({ error: { code, message } }, { status, headers: { "Cache-Control": "no-store" } });

export const proxyDocumentRequest = createServerOnlyFn(
  async (request: Request, path: string, config: ProxyConfig) => {
    if (!allowedProxyPath(request.method, path))
      return failure(404, "not_found", "Document endpoint not found.");
    const authorization = request.headers.get("Authorization");
    // The same HttpOnly cookie authenticates JSON, images, crops and downloads.
    const cookieToken = request.headers
      .get("Cookie")
      ?.split(";")
      .map((part) => part.trim())
      .find((part) => part.startsWith(`${AUTH_COOKIE}=`))
      ?.slice(`${AUTH_COOKIE}=`.length);
    const token = authorization?.startsWith("Bearer ") ? authorization.slice(7) : cookieToken;
    if (!token) return failure(401, "unauthorized", "Sign in to access private reports.");
    const backend = configuredBackend(config.backendUrl);
    if (!config.authorizedUserId || !config.authUrl || !config.authKey) return failure(403, "forbidden", "Private access is not configured.");
    if (request.method !== "GET") {
      const origin = request.headers.get("Origin");
      if (!origin || origin !== new URL(request.url).origin)
        return failure(403, "forbidden", "Request origin is not allowed.");
    }
    try {
      const authKey = config.authKey;
      const auth = createClient(config.authUrl, authKey, {
        auth: { persistSession: false, autoRefreshToken: false },
        global: {
          fetch: (input, init) => {
            const headers = new Headers(init?.headers);
            if (authKey.startsWith("sb_") && headers.get("Authorization") === `Bearer ${authKey}`)
              headers.delete("Authorization");
            headers.set("apikey", authKey);
            return fetch(input, { ...init, headers });
          },
        },
      });
      const { data, error } = await auth.auth.getUser(token);
      if (error || !data.user)
        return failure(401, "unauthorized", "Sign in to access private reports.");
      if (!authorizedUser(data.user.id, config.authorizedUserId))
        return failure(403, "forbidden", "This account is not authorized.");
      if (!backend || !config.backendToken) return failure(503, "backend_unavailable", "The document service is not connected. Use the sample preview.");
      const target = new URL(path, backend);
      const incoming = new URL(request.url);
      for (const [key, value] of incoming.searchParams) {
        if (!["dpi", "page", "category", "parser"].includes(key) || value.length > 40)
          return failure(400, "invalid_request", "Invalid document parameters.");
        target.searchParams.append(key, value);
      }
      const headers = new Headers({ Authorization: `Bearer ${config.backendToken}` });
      for (const name of ["Content-Type", "Accept", "Range"]) {
        const value = request.headers.get(name);
        if (value) headers.set(name, value);
      }
      const response = await fetch(target, {
        method: request.method,
        headers,
        body: request.method === "GET" ? undefined : request.body,
        redirect: "manual",
        signal: AbortSignal.timeout(120_000),
        // Streaming preserves multipart boundaries without buffering PDFs.
        duplex: "half",
      } as RequestInit);
      if (response.status >= 300 && response.status < 400)
        return failure(
          502,
          "backend_unavailable",
          "The document service returned an unexpected redirect.",
        );
      if (!response.ok)
        return failure(
          response.status >= 500 || [401, 403].includes(response.status) ? 502 : response.status,
          "document_service_error",
          "The document service could not complete this request.",
        );
      const outgoing = new Headers({
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
      });
      for (const name of [
        "Content-Type",
        "Content-Disposition",
        "Content-Range",
        "Accept-Ranges",
        "X-Document-Status",
      ]) {
        const value = response.headers.get(name);
        if (value) outgoing.set(name, value);
      }
      return new Response(response.body, { status: response.status, headers: outgoing });
    } catch {
      return failure(
        502,
        "backend_unavailable",
        "The document service is unavailable. No processing result was generated.",
      );
    }
  },
);
