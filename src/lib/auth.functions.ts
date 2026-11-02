import { createServerFn } from "@tanstack/react-start";
import { getRequest, getCookie, setResponseHeader } from "@tanstack/react-start/server";
import { z } from "zod";
import { authClient, readOwnerSession, saveAuthCookies, clearAuthCookies } from "./auth-session";
import { AUTH_COOKIE, isOwner, sameOrigin } from "./auth-policy";

export const signIn = createServerFn({ method: "POST" })
  .inputValidator((input: unknown) => z.object({ email: z.string().email().max(254), password: z.string().min(1).max(256) }).parse(input))
  .handler(async ({ data }) => {
    setResponseHeader("Cache-Control", "private, no-store");
    if (!sameOrigin(getRequest())) return { success: false, message: "Request origin is not allowed." };
    const owner = process.env["FINAUDIT_AUTHORIZED_USER_ID"];
    if (!owner) return { success: false, message: "Private sign-in is not configured yet. The sample preview remains available." };
    try {
      const client = authClient();
      const { data: result, error } = await client.auth.signInWithPassword(data);
      if (error || !result.session || !isOwner(result.user?.id, owner)) {
        if (result.session) await client.auth.signOut();
        clearAuthCookies();
        return { success: false, message: "Unable to sign in with this account." };
      }
      saveAuthCookies(result.session);
      return { success: true, message: "" };
    } catch { return { success: false, message: "Sign-in is temporarily unavailable." }; }
  });

export const ownerSession = createServerFn({ method: "GET" }).handler(async () => {
  const session = await readOwnerSession();
  return { signedIn: Boolean(session), email: session?.email ?? "" };
});

export const refreshOwnerSession = createServerFn({ method: "POST" }).handler(async () => {
  if (!sameOrigin(getRequest())) return { signedIn: false, email: "" };
  const session = await readOwnerSession(true);
  return { signedIn: Boolean(session), email: session?.email ?? "" };
});

export const signOut = createServerFn({ method: "POST" }).handler(async () => {
  if (!sameOrigin(getRequest())) return { success: false };
  const token = getCookie(AUTH_COOKIE);
  try { if (token) await authClient().auth.admin.signOut(token, "global"); } finally { clearAuthCookies(); }
  return { success: true };
});