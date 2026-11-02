import { createServerOnlyFn } from "@tanstack/react-start";
import { configuredBackend } from "./api/proxy-policy";
import { acceptsDemoEntry } from "./demo-entry";
import { demoGuard } from "./demo-guard";
import { DEMO_COOKIE, DEMO_TTL, demoConfigured, demoCookie, demoSameOrigin, signDemoSession, verifyDemoSession, type TemporaryConfig } from "./temporary-demo";

const reply = (status: number, body: object, cookie?: string) => Response.json(body, { status, headers: { "Cache-Control": "no-store", ...(cookie ? { "Set-Cookie": cookie } : {}) } });
const cookieHeader = (value: string, age: number) => `${DEMO_COOKIE}=${value}; Path=/; Max-Age=${age}; Secure; HttpOnly; SameSite=Strict`;

export const handleDemoSession = createServerOnlyFn(async (request: Request, config: TemporaryConfig) => {
  if (request.method === "GET") {
    const enabled = demoConfigured(config) && Boolean(configuredBackend(config.backendUrl));
    try {
      const id = enabled ? await verifyDemoSession(demoCookie(request), config.demoSecret) : null;
      return reply(200, { enabled, entered: id ? await (await demoGuard()).valid(id) : false });
    } catch { return reply(503, { error: "Demo limits unavailable." }); }
  }
  if (request.method !== "POST" && request.method !== "DELETE") return reply(405, { error: "Method not allowed." });
  if (!demoSameOrigin(request)) return reply(403, { error: "Request origin is not allowed." });
  try {
    const guard = await demoGuard();
    if (request.method === "DELETE") {
      const id = await verifyDemoSession(demoCookie(request), config.demoSecret);
      if (id) await guard.revoke(id);
      return reply(200, { ok: true }, cookieHeader("", 0));
    }
    if (!demoConfigured(config) || !configuredBackend(config.backendUrl) || !config.demoSecret) return reply(503, { error: "Document service unavailable. Continue with the sample preview." });
    // Global login bound also protects against rotating IPs and header spoofing.
    if (!await guard.consume(`login:${Math.floor(Date.now() / 60000)}`, 10)) return reply(429, { error: "Too many demo entries. Try later." });
    if (!request.headers.get("content-type")?.startsWith("application/json")) return reply(415, { error: "JSON required." });
    const text = await request.text();
    if (text.length > 256) return reply(413, { error: "Entry too large." });
    const data = JSON.parse(text);
    if (!acceptsDemoEntry(data.username, data.password)) return reply(401, { error: "Use admin / admin for the temporary demo." });
    const id = crypto.randomUUID();
    await guard.create(id, new Date(Date.now() + DEMO_TTL * 1000).toISOString());
    return reply(200, { ok: true }, cookieHeader(await signDemoSession(id, config.demoSecret), DEMO_TTL));
  } catch { return reply(503, { error: "Demo session unavailable. No live access granted." }); }
});