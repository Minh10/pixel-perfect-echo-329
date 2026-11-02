import { createServerOnlyFn } from "@tanstack/react-start";

// Durable, atomic counters shared across instances; no memory-only rate limits.
export const demoGuard = createServerOnlyFn(async () => {
  const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
  return {
    async consume(bucket: string, limit: number) {
      const { data, error } = await supabaseAdmin.rpc("consume_demo_budget", { p_bucket: bucket, p_limit: limit });
      if (error) throw new Error("Demo limits unavailable");
      return data === true;
    },
    async create(id: string, expires: string) {
      const { error } = await supabaseAdmin.from("finaudit_demo_sessions").insert({ id, expires_at: expires });
      if (error) throw new Error("Demo session unavailable");
    },
    async valid(id: string) {
      const { data, error } = await supabaseAdmin.from("finaudit_demo_sessions").select("id").eq("id", id).eq("revoked", false).gt("expires_at", new Date().toISOString()).maybeSingle();
      if (error) throw new Error("Demo session unavailable");
      return Boolean(data);
    },
    async revoke(id: string) {
      const { error } = await supabaseAdmin.from("finaudit_demo_sessions").update({ revoked: true }).eq("id", id);
      if (error) throw new Error("Demo session unavailable");
    },
  };
});