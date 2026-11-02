import { createServerOnlyFn } from "@tanstack/react-start";
import { createClient } from "@supabase/supabase-js";
import {
  getCookie,
  setCookie,
  deleteCookie,
  setResponseHeader,
} from "@tanstack/react-start/server";
import type { Session } from "@supabase/supabase-js";
import { AUTH_COOKIE, REFRESH_COOKIE, AUTH_COOKIE_OPTIONS, isOwner } from "./auth-policy";

export const authClient = createServerOnlyFn(() => {
  const url = process.env["SUPABASE_URL"];
  const key = process.env["SUPABASE_PUBLISHABLE_KEY"];
  if (!url || !key) throw new Error("Sign-in is unavailable.");
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
    global: {
      fetch: (input, init) => {
        const headers = new Headers(init?.headers);
        if (key.startsWith("sb_") && headers.get("Authorization") === `Bearer ${key}`)
          headers.delete("Authorization");
        headers.set("apikey", key);
        return fetch(input, { ...init, headers });
      },
    },
  });
});

export const clearAuthCookies = createServerOnlyFn(() => {
  deleteCookie(AUTH_COOKIE, AUTH_COOKIE_OPTIONS);
  deleteCookie(REFRESH_COOKIE, AUTH_COOKIE_OPTIONS);
});

export const saveAuthCookies = createServerOnlyFn((session: Session) => {
  setCookie(AUTH_COOKIE, session.access_token, {
    ...AUTH_COOKIE_OPTIONS,
    maxAge: session.expires_in,
  });
  setCookie(REFRESH_COOKIE, session.refresh_token, {
    ...AUTH_COOKIE_OPTIONS,
    maxAge: 60 * 60 * 24 * 7,
  });
  setResponseHeader("Cache-Control", "private, no-store");
});

export const readOwnerSession = createServerOnlyFn(async (refresh = false) => {
  setResponseHeader("Cache-Control", "private, no-store");
  const owner = process.env["FINAUDIT_AUTHORIZED_USER_ID"];
  if (!owner) return null;
  const client = authClient();
  let token = getCookie(AUTH_COOKIE);
  if (!token && refresh) {
    const refreshToken = getCookie(REFRESH_COOKIE);
    if (refreshToken) {
      const { data, error } = await client.auth.refreshSession({ refresh_token: refreshToken });
      if (!error && data.session && isOwner(data.user?.id, owner)) {
        saveAuthCookies(data.session);
        token = data.session.access_token;
      } else clearAuthCookies();
    }
  }
  if (!token) return null;
  const { data, error } = await client.auth.getUser(token);
  if (error || !data.user || !isOwner(data.user.id, owner)) return null;
  return { userId: data.user.id, email: data.user.email ?? "", token };
});
