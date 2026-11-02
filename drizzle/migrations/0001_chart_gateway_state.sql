CREATE TABLE public.finaudit_chart_gateway_state (
  key text PRIMARY KEY,
  payload jsonb NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);
GRANT ALL ON public.finaudit_chart_gateway_state TO service_role;
REVOKE ALL ON public.finaudit_chart_gateway_state FROM anon, authenticated;
ALTER TABLE public.finaudit_chart_gateway_state ENABLE ROW LEVEL SECURITY;
COMMENT ON TABLE public.finaudit_chart_gateway_state IS 'Server-only chart summary cache and durable terminal gateway pause; no public policies.';