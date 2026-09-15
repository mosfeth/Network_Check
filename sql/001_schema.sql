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

CREATE INDEX IF NOT EXISTS idx_machines_client ON public.machines(client_id);
CREATE INDEX IF NOT EXISTS idx_measurements_machine ON public.measurements(machine_id);
CREATE INDEX IF NOT EXISTS idx_measurements_measured_at ON public.measurements(measured_at DESC);

ALTER TABLE public.clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.machines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.measurements ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_clients" ON public.clients FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_machines" ON public.machines FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_measurements" ON public.measurements FOR ALL TO service_role USING (true) WITH CHECK (true);