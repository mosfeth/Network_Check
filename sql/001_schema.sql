CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.clients (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.machines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id uuid NOT NULL REFERENCES public.clients(id) ON DELETE CASCADE,
    tag text NOT NULL,
    ip inet NOT NULL,
    frequency_seconds int NOT NULL CHECK (frequency_seconds >= 10),
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (client_id, tag)
);

CREATE TABLE IF NOT EXISTS public.measurements (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id uuid NOT NULL REFERENCES public.clients(id) ON DELETE CASCADE,
    machine_id uuid NOT NULL REFERENCES public.machines(id) ON DELETE CASCADE,
    latency_ms numeric,
    jitter_ms numeric,
    packet_loss_percent numeric NOT NULL,
    packets_sent int NOT NULL,
    packets_received int NOT NULL,
    status text NOT NULL CHECK (status IN ('ok', 'partial', 'unreachable', 'error')),
    measured_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.traceroutes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id uuid NOT NULL REFERENCES public.clients(id) ON DELETE CASCADE,
    machine_id uuid NOT NULL REFERENCES public.machines(id) ON DELETE CASCADE,
    target_ip inet NOT NULL,
    max_hops int NOT NULL,
    total_hops int,
    destination_reached boolean NOT NULL DEFAULT false,
    measured_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.traceroute_hops (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    traceroute_id uuid NOT NULL REFERENCES public.traceroutes(id) ON DELETE CASCADE,
    hop_number int NOT NULL,
    ip inet,
    hostname text,
    latency_ms numeric,
    packet_loss_percent numeric,
    asn bigint,
    asn_name text,
    measured_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.alert_rules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id uuid NOT NULL REFERENCES public.clients(id) ON DELETE CASCADE,
    machine_id uuid REFERENCES public.machines(id) ON DELETE CASCADE,
    name text NOT NULL,
    metric text NOT NULL CHECK (metric IN ('latency', 'loss', 'jitter')),
    condition text NOT NULL CHECK (condition IN ('gt', 'gte', 'lt', 'lte')),
    threshold_warn numeric NOT NULL,
    threshold_crit numeric NOT NULL,
    evaluation_window_seconds int NOT NULL DEFAULT 300,
    cooldown_seconds int NOT NULL DEFAULT 900,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.alert_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id uuid NOT NULL REFERENCES public.alert_rules(id) ON DELETE CASCADE,
    client_id uuid NOT NULL REFERENCES public.clients(id) ON DELETE CASCADE,
    machine_id uuid NOT NULL REFERENCES public.machines(id) ON DELETE CASCADE,
    status text NOT NULL CHECK (status IN ('firing', 'resolved', 'acknowledged')),
    severity text NOT NULL CHECK (severity IN ('warning', 'critical')),
    metric_value numeric NOT NULL,
    threshold_value numeric NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz,
    acknowledged_at timestamptz,
    acknowledged_by text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_machines_client ON public.machines(client_id);
CREATE INDEX IF NOT EXISTS idx_measurements_machine ON public.measurements(machine_id);
CREATE INDEX IF NOT EXISTS idx_measurements_measured_at ON public.measurements(measured_at DESC);
CREATE INDEX IF NOT EXISTS idx_traceroutes_machine ON public.traceroutes(machine_id);
CREATE INDEX IF NOT EXISTS idx_traceroutes_measured_at ON public.traceroutes(measured_at DESC);
CREATE INDEX IF NOT EXISTS idx_traceroute_hops_traceroute ON public.traceroute_hops(traceroute_id);
CREATE INDEX IF NOT EXISTS idx_alert_rules_client ON public.alert_rules(client_id);
CREATE INDEX IF NOT EXISTS idx_alert_rules_machine ON public.alert_rules(machine_id);
CREATE INDEX IF NOT EXISTS idx_alert_events_rule ON public.alert_events(rule_id);
CREATE INDEX IF NOT EXISTS idx_alert_events_machine ON public.alert_events(machine_id);
CREATE INDEX IF NOT EXISTS idx_alert_events_status ON public.alert_events(status);
CREATE INDEX IF NOT EXISTS idx_alert_events_started_at ON public.alert_events(started_at DESC);

ALTER TABLE public.clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.machines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.measurements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.traceroutes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.traceroute_hops ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alert_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alert_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_clients" ON public.clients FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_machines" ON public.machines FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_measurements" ON public.measurements FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_traceroutes" ON public.traceroutes FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_traceroute_hops" ON public.traceroute_hops FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_alert_rules" ON public.alert_rules FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_alert_events" ON public.alert_events FOR ALL TO service_role USING (true) WITH CHECK (true);