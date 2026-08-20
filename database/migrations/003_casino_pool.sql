-- Apply in Supabase alongside the matching code deploy.
-- Adds the casino resource pool: one row per bettable resource (ER, CM, EL, CS).
-- Every game loss feeds the pool, every game win is paid out of the pool.
-- ER seeds at its floor of 50,000,000,000. CM/EL/CS seed at 1,000,000 with a floor of 250,000.
-- Keyed on resources(id), like local_treasury and faction_treasury, so a typo
-- cannot create a phantom pool row and a resource rename does not break it.

CREATE TABLE IF NOT EXISTS public.casino_pool (
  resource_id integer NOT NULL,
  amount bigint NOT NULL DEFAULT 0 CHECK (amount >= 0),
  floor_amount bigint NOT NULL,
  CONSTRAINT casino_pool_pkey PRIMARY KEY (resource_id),
  CONSTRAINT casino_pool_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(id)
);

INSERT INTO public.casino_pool (resource_id, amount, floor_amount)
SELECT id, 50000000000, 50000000000 FROM public.resources WHERE name = 'ER'
ON CONFLICT (resource_id) DO NOTHING;

INSERT INTO public.casino_pool (resource_id, amount, floor_amount)
SELECT id, 1000000, 250000 FROM public.resources WHERE name = 'CM'
ON CONFLICT (resource_id) DO NOTHING;

INSERT INTO public.casino_pool (resource_id, amount, floor_amount)
SELECT id, 1000000, 250000 FROM public.resources WHERE name = 'EL'
ON CONFLICT (resource_id) DO NOTHING;

INSERT INTO public.casino_pool (resource_id, amount, floor_amount)
SELECT id, 1000000, 250000 FROM public.resources WHERE name = 'CS'
ON CONFLICT (resource_id) DO NOTHING;

ALTER TABLE public.casino_pool ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS bot_app_all ON public.casino_pool;
CREATE POLICY bot_app_all ON public.casino_pool
  FOR ALL TO bot_app
  USING (true) WITH CHECK (true);
