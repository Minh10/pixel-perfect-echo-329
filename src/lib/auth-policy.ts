export const AUTH_COOKIE = "__Host-finaudit_access";
export const REFRESH_COOKIE = "__Host-finaudit_refresh";
export const AUTH_COOKIE_OPTIONS = { httpOnly: true, secure: true, sameSite: "lax" as const, path: "/" };

export function isOwner(actual: string | undefined, expected: string | undefined) {
  return Boolean(actual && expected && actual === expected);
}

export function sameOrigin(request: Request) {
  return request.headers.get("Origin") === new URL(request.url).origin;
}