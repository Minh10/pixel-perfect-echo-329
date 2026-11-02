CREATE TABLE public.finaudit_demo_sessions (id uuid PRIMARY KEY, expires_at timestamptz NOT NULL, revoked boolean NOT NULL DEFAULT false);
GRANT ALL ON public.finaudit_demo_sessions TO service_role;
REVOKE ALL ON public.finaudit_demo_sessions FROM anon, authenticated;
ALTER TABLE public.finaudit_demo_sessions ENABLE ROW LEVEL SECURITY;
CREATE TABLE public.finaudit_demo_budgets (bucket text PRIMARY KEY, used integer NOT NULL DEFAULT 0);
GRANT ALL ON public.finaudit_demo_budgets TO service_role;
REVOKE ALL ON public.finaudit_demo_budgets FROM anon, authenticated;
ALTER TABLE public.finaudit_demo_budgets ENABLE ROW LEVEL SECURITY;
CREATE FUNCTION public.consume_demo_budget(p_bucket text, p_limit integer) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE n integer;
BEGIN
IF p_limit < 1 OR p_limit > 10000 OR length(p_bucket) > 200 THEN RETURN false; END IF;
INSERT INTO public.finaudit_demo_budgets(bucket, used) VALUES(p_bucket, 1)
ON CONFLICT(bucket) DO UPDATE SET used = finaudit_demo_budgets.used + 1
WHERE finaudit_demo_budgets.used < p_limit RETURNING used INTO n;
RETURN n IS NOT NULL;
END $$;
REVOKE ALL ON FUNCTION public.consume_demo_budget(text, integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.consume_demo_budget(text, integer) TO service_role;