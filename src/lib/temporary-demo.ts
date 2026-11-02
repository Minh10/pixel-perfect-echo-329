// No identity or owner privileges: a bounded temporary demonstration only.
export const DEMO_COOKIE = "__Host-finaudit_demo";
export const DEMO_TTL = 60 * 60;
export const MAX_PDF_BYTES = 10 * 1024 * 1024;
export const MAX_PDF_PAGES = 30;
export const MAX_JSON_BYTES = 16 * 1024;
export interface TemporaryConfig {
  demoEnabled?: string | undefined;
  demoSecret?: string | undefined;
  backendUrl?: string | undefined;
  backendToken?: string | undefined;
}
export function demoConfigured(config: TemporaryConfig): boolean {
  return (
    config.demoEnabled === "true" &&
    Boolean(config.demoSecret && config.backendUrl && config.backendToken)
  );
}
function encode(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replace(/=+$/, "");
}
function decode(value: string): Uint8Array<ArrayBuffer> {
  return Uint8Array.from(atob(value.replaceAll("-", "+").replaceAll("_", "/")), (c) =>
    c.charCodeAt(0),
  );
}
async function key(secret: string) {
  return crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
}
export async function signDemoSession(
  id: string,
  secret: string,
  now = Date.now(),
): Promise<string> {
  const payload = encode(
    new TextEncoder().encode(
      JSON.stringify({ id, exp: Math.floor(now / 1000) + DEMO_TTL, scope: "temporary-demo" }),
    ),
  );
  return `${payload}.${encode(new Uint8Array(await crypto.subtle.sign("HMAC", await key(secret), new TextEncoder().encode(payload))))}`;
}
export async function verifyDemoSession(
  cookie: string | undefined,
  secret: string | undefined,
  now = Date.now(),
): Promise<string | null> {
  if (!cookie || !secret || cookie.length > 1024) return null;
  try {
    const [payload, signature, extra] = cookie.split(".");
    if (!payload || !signature || extra) return null;
    if (
      !(await crypto.subtle.verify(
        "HMAC",
        await key(secret),
        decode(signature),
        new TextEncoder().encode(payload),
      ))
    )
      return null;
    const data = JSON.parse(new TextDecoder().decode(decode(payload)));
    const seconds = Math.floor(now / 1000);
    return data.scope === "temporary-demo" &&
      /^[a-f0-9-]{36}$/.test(data.id) &&
      Number.isInteger(data.exp) &&
      data.exp > seconds &&
      data.exp <= seconds + DEMO_TTL
      ? data.id
      : null;
  } catch {
    return null;
  }
}
export function demoCookie(request: Request): string | undefined {
  return request.headers
    .get("cookie")
    ?.split(";")
    .map((s) => s.trim())
    .find((s) => s.startsWith(`${DEMO_COOKIE}=`))
    ?.slice(DEMO_COOKIE.length + 1);
}
export function demoSameOrigin(request: Request): boolean {
  return (
    request.headers.get("origin") === new URL(request.url).origin &&
    request.headers.get("sec-fetch-site") !== "cross-site"
  );
}
