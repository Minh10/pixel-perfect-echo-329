import { createServerOnlyFn } from "@tanstack/react-start";
import { createClient } from "@supabase/supabase-js";
import { allowedProxyPath, authorizedUser, configuredBackend } from "./proxy-policy";
import { AUTH_COOKIE } from "../auth-policy";
import { demoGuard } from "../demo-guard";
import {
  demoConfigured,
  demoCookie,
  demoSameOrigin,
  MAX_DAILY_PDF_UPLOADS,
  MAX_DAILY_WORK_REQUESTS,
  verifyDemoSession,
  type TemporaryConfig,
} from "../temporary-demo";
import { validateDemoBody } from "./demo-request";

interface ProxyConfig extends TemporaryConfig {
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
    let demo = false;
    let body: Uint8Array<ArrayBuffer> | undefined;
    if (config.demoEnabled === "true") {
      const id = await verifyDemoSession(demoCookie(request), config.demoSecret);
      if (!id)
        return failure(401, "unauthorized", "Enter the temporary demo to access live reports.");
      if (!demoConfigured(config) || !configuredBackend(config.backendUrl))
        return failure(
          503,
          "backend_unavailable",
          "Document service unavailable. Use the sample preview.",
        );
      if (request.method !== "GET" && !demoSameOrigin(request))
        return failure(403, "forbidden", "Request origin is not allowed.");
      if (request.headers.get("sec-fetch-site") === "cross-site")
        return failure(403, "forbidden", "Cross-site resources are not allowed.");
      try {
        const guard = await demoGuard();
        if (!(await guard.valid(id)))
          return failure(401, "unauthorized", "Demo session expired or ended.");
        const minute = Math.floor(Date.now() / 60000);
        const day = new Date().toISOString().slice(0, 10);
        if (
          !(await guard.consume(`requests:${minute}`, 120)) ||
          !(await guard.consume(`session:${id}:${minute}`, 60))
        )
          return failure(429, "demo_limit", "Temporary demo request limit reached.");
        if (request.method === "POST") {
          if (
            !(await guard.consume(`work:${day}`, MAX_DAILY_WORK_REQUESTS)) ||
            !(await guard.consume(`work-minute:${minute}`, 2))
          )
            return failure(429, "demo_limit", `Daily AI action limit (${MAX_DAILY_WORK_REQUESTS}) or 2-per-minute pace reached; wait a minute or until 00:00 UTC (07:00 Vietnam).`);
          if (
            path === "api/v1/documents" &&
            !(await guard.consume(`uploads:${day}`, MAX_DAILY_PDF_UPLOADS))
          )
            return failure(
              429,
              "demo_limit",
              `Daily PDF upload limit (${MAX_DAILY_PDF_UPLOADS}) reached; resets at 00:00 UTC.`,
            );
        }
        demo = true;
      } catch {
        return failure(
          503,
          "demo_limits_unavailable",
          "Demo limits unavailable. Live access is disabled.",
        );
      }
      try {
        body = await validateDemoBody(request, path);
      } catch {
        return failure(
          400,
          "invalid_request",
          "Demo accepts one unencrypted PDF up to 10 MiB / 30 pages, or bounded document-tool input.",
        );
      }
    }
    const authorization = request.headers.get("Authorization");
    // The same HttpOnly cookie authenticates JSON, images, crops and downloads.
    const cookieToken = request.headers
      .get("Cookie")
      ?.split(";")
      .map((part) => part.trim())
      .find((part) => part.startsWith(`${AUTH_COOKIE}=`))
      ?.slice(`${AUTH_COOKIE}=`.length);
    const token = authorization?.startsWith("Bearer ") ? authorization.slice(7) : cookieToken;
    if (!demo && !token) return failure(401, "unauthorized", "Sign in to access private reports.");
    const backend = configuredBackend(config.backendUrl);
    if (!demo && (!config.authorizedUserId || !config.authUrl || !config.authKey))
      return failure(403, "forbidden", "Private access is not configured.");
    if (request.method !== "GET") {
      const origin = request.headers.get("Origin");
      if (!origin || origin !== new URL(request.url).origin)
        return failure(403, "forbidden", "Request origin is not allowed.");
    }
    try {
      if (!demo) {
        const authKey = config.authKey;
        if (!authKey || !config.authUrl || !token)
          return failure(403, "forbidden", "Private access is not configured.");
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
      }
      if (!backend || !config.backendToken)
        return failure(
          503,
          "backend_unavailable",
          "The document service is not connected. Use the sample preview.",
        );
      const target = new URL(path, backend);
      const incoming = new URL(request.url);
      for (const [key, value] of incoming.searchParams) {
        if (!validDocumentQuery(key, value) || target.searchParams.has(key))
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
        body: demo ? body : request.method === "GET" ? undefined : request.body,
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

export function validDocumentQuery(key: string, value: string): boolean {
  if (key === "dpi")
    return /^[0-9]{2,3}$/.test(value) && Number(value) >= 36 && Number(value) <= 150;
  if (key === "page") return /^[1-9][0-9]{0,4}$/.test(value);
  if (key === "parser") return ["auto", "docling", "pymupdf"].includes(value);
  if (key === "category") return ["table", "figure", "disclosure"].includes(value);
  return false;
}
