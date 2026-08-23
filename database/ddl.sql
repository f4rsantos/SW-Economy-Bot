-- Copyright (c) 2026 f4rsantos. All rights reserved.
-- Unauthorized copying, modification, or distribution of this file,
-- via any medium, is strictly prohibited without explicit written
-- permission from the copyright holder. Contact: f4rsantos@gmail.com













CREATE TABLE public.badges (
  id integer NOT NULL DEFAULT nextval('badges_id_seq'::regclass),
  name text NOT NULL UNIQUE,
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  is_purchasable boolean NOT NULL DEFAULT false,
  needs_world boolean NOT NULL DEFAULT false,
  CONSTRAINT badges_pkey PRIMARY KEY (id)
);

CREATE TABLE public.badge_costs (
  badge_id integer NOT NULL,
  resource_id integer NOT NULL,
  amount bigint NOT NULL CHECK (amount > 0),
  CONSTRAINT badge_costs_pkey PRIMARY KEY (badge_id, resource_id),
  CONSTRAINT badge_costs_badge_id_fkey FOREIGN KEY (badge_id) REFERENCES public.badges(id),
  CONSTRAINT badge_costs_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(id)
);

CREATE TABLE public.badge_progress_resources (
  user_id bigint NOT NULL,
  badge_id integer NOT NULL,
  resource_id integer NOT NULL,
  current_amount bigint NOT NULL DEFAULT 0 CHECK (current_amount >= 0),
  updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT badge_progress_resources_pkey PRIMARY KEY (user_id, badge_id, resource_id),
  CONSTRAINT badge_progress_resources_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id),
  CONSTRAINT badge_progress_resources_badge_id_fkey FOREIGN KEY (badge_id) REFERENCES public.badges(id),
  CONSTRAINT badge_progress_resources_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(id)
);

CREATE TABLE public.battle_participants (
  battle_id integer NOT NULL,
  fleet_id integer NOT NULL,
  side text NOT NULL,
  CONSTRAINT battle_participants_pkey PRIMARY KEY (battle_id, fleet_id),
  CONSTRAINT battle_participants_battle_id_fkey FOREIGN KEY (battle_id) REFERENCES public.battles(id),
  CONSTRAINT battle_participants_fleet_id_fkey FOREIGN KEY (fleet_id) REFERENCES public.fleets(id)
);

CREATE TABLE public.battles (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  war_id integer NOT NULL,
  world_id integer,
  date_start timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT battles_pkey PRIMARY KEY (id),
  CONSTRAINT battles_war_id_fkey FOREIGN KEY (war_id) REFERENCES public.wars(id)
);

CREATE TABLE public.blockade_fleets (
  blockade_id integer NOT NULL,
  fleet_id integer NOT NULL,
  CONSTRAINT blockade_fleets_pkey PRIMARY KEY (blockade_id, fleet_id),
  CONSTRAINT blockade_fleets_blockade_id_fkey FOREIGN KEY (blockade_id) REFERENCES public.blockades(id),
  CONSTRAINT blockade_fleets_fleet_id_fkey FOREIGN KEY (fleet_id) REFERENCES public.fleets(id)
);

CREATE TABLE public.blockade_targets (
  blockade_id integer NOT NULL,
  faction_id integer NOT NULL,
  CONSTRAINT blockade_targets_pkey PRIMARY KEY (blockade_id, faction_id),
  CONSTRAINT blockade_targets_blockade_id_fkey FOREIGN KEY (blockade_id) REFERENCES public.blockades(id),
  CONSTRAINT blockade_targets_faction_id_fkey FOREIGN KEY (faction_id) REFERENCES public.factions(id)
);

CREATE TABLE public.blockades (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  world_id integer NOT NULL,
  date_start timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  date_end timestamp with time zone,
  CONSTRAINT blockades_pkey PRIMARY KEY (id),
  CONSTRAINT blockades_world_id_fkey FOREIGN KEY (world_id) REFERENCES public.worlds(id)
);

CREATE TABLE public.building_costs (
  building_id integer NOT NULL,
  resource_id integer NOT NULL,
  amount bigint NOT NULL CHECK (amount > 0),
  CONSTRAINT building_costs_pkey PRIMARY KEY (building_id, resource_id),
  CONSTRAINT building_costs_building_id_fkey FOREIGN KEY (building_id) REFERENCES public.buildings(id),
  CONSTRAINT building_costs_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(id)
);

CREATE TABLE public.buildings (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  name text NOT NULL,
  description text,
  is_generator boolean NOT NULL,
  CONSTRAINT buildings_pkey PRIMARY KEY (id)
);

CREATE TABLE public.buildings_generators (
  building_id integer NOT NULL,
  resource_id integer NOT NULL,
  is_unique boolean NOT NULL,
  production integer NOT NULL,
  percentage_affects boolean NOT NULL,
  is_refinery boolean NOT NULL,
  max_levels integer NOT NULL,
  is_special boolean NOT NULL,
  CONSTRAINT buildings_generators_pkey PRIMARY KEY (building_id),
  CONSTRAINT buildings_generators_building_id_fkey FOREIGN KEY (building_id) REFERENCES public.buildings(id),
  CONSTRAINT buildings_generators_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(id)
);

CREATE TABLE public.buildings_storages (
  building_id integer NOT NULL,
  resource_id integer NOT NULL,
  is_unique boolean NOT NULL,
  storage integer NOT NULL,
  max_levels integer NOT NULL,
  is_special boolean NOT NULL,
  CONSTRAINT buildings_storages_pkey PRIMARY KEY (building_id),
  CONSTRAINT buildings_storages_building_id_fkey FOREIGN KEY (building_id) REFERENCES public.buildings(id),
  CONSTRAINT buildings_storages_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(id)
);

CREATE TABLE public.comets (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  name text NOT NULL,
  message text NOT NULL,
  discoverer bigint NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT NOW(),
  CONSTRAINT comets_pkey PRIMARY KEY (id),
  CONSTRAINT comets_discoverer_fkey FOREIGN KEY (discoverer) REFERENCES public.users(id)
);

CREATE TABLE public.custom_user_messages (
  user_id bigint NOT NULL,
  message text NOT NULL,
  created_by bigint NOT NULL,
  CONSTRAINT custom_user_messages_pkey PRIMARY KEY (user_id)
);

CREATE TABLE public.faction_treasury (
  faction_id integer NOT NULL,
  resource_id integer NOT NULL,
  amount bigint NOT NULL DEFAULT 0 CHECK (amount >= 0),
  storage bigint CHECK (storage >= 0),
  CONSTRAINT faction_treasury_pkey PRIMARY KEY (faction_id, resource_id),
  CONSTRAINT faction_treasury_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(id),
  CONSTRAINT faction_treasury_faction_id_fkey FOREIGN KEY (faction_id) REFERENCES public.factions(id)
);

CREATE TABLE public.faction_world_buildings (
  building_id integer NOT NULL,
  faction_id integer NOT NULL,
  world_id integer NOT NULL,
  amount integer NOT NULL CHECK (amount > 0),
  level integer NOT NULL DEFAULT 1 CHECK (level > 0),
  CONSTRAINT faction_world_buildings_pkey PRIMARY KEY (faction_id, world_id, building_id, level),
  CONSTRAINT faction_world_buildings_building_id_fkey FOREIGN KEY (building_id) REFERENCES public.buildings(id),
  CONSTRAINT faction_world_buildings_world_id_fkey FOREIGN KEY (world_id) REFERENCES public.worlds(id),
  CONSTRAINT faction_world_buildings_faction_id_fkey FOREIGN KEY (faction_id) REFERENCES public.factions(id)
);

CREATE TABLE public.factions (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  name text NOT NULL,
  formal_name text,
  color text NOT NULL,
  leader text,
  flag text,
  faction_type integer NOT NULL DEFAULT 0,
  capital_world_id integer,
  leader_id bigint,
  CONSTRAINT factions_pkey PRIMARY KEY (id),
  CONSTRAINT factions_leader_id_fkey FOREIGN KEY (leader_id) REFERENCES public.users(id),
  CONSTRAINT factions_capital_world_id_fkey FOREIGN KEY (capital_world_id) REFERENCES public.worlds(id)
);

CREATE TABLE public.fleet_status (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  name text NOT NULL,
  description text,
  CONSTRAINT fleet_status_pkey PRIMARY KEY (id)
);

CREATE TABLE public.fleet_types (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  name text NOT NULL,
  CONSTRAINT fleet_types_pkey PRIMARY KEY (id)
);

CREATE TABLE public.casino_pool (
  resource_id integer NOT NULL,
  amount bigint NOT NULL DEFAULT 0 CHECK (amount >= 0),
  floor_amount bigint NOT NULL DEFAULT 0 CHECK (floor_amount >= 0),
  CONSTRAINT casino_pool_pkey PRIMARY KEY (resource_id),
  CONSTRAINT casino_pool_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(id)
);

CREATE TABLE public.faction_scripts (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  faction_id integer NOT NULL,
  name text NOT NULL,
  script_text text NOT NULL,
  trigger_day text,
  trigger_type text,
  created_by bigint,
  created_at timestamp with time zone NOT NULL DEFAULT NOW(),
  updated_at timestamp with time zone NOT NULL DEFAULT NOW(),
  last_run_at timestamp with time zone,
  run_count integer NOT NULL DEFAULT 0,
  is_active boolean NOT NULL DEFAULT TRUE,
  CONSTRAINT faction_scripts_pkey PRIMARY KEY (id),
  CONSTRAINT faction_scripts_faction_id_fkey FOREIGN KEY (faction_id) REFERENCES public.factions(id),
  CONSTRAINT faction_scripts_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id)
);

CREATE TABLE public.fleet_vehicles (
  fleet_id integer NOT NULL,
  vehicle_id integer NOT NULL,
  amount integer NOT NULL CHECK (amount > 0),
  CONSTRAINT fleet_vehicles_pkey PRIMARY KEY (fleet_id, vehicle_id),
  CONSTRAINT fleet_vehicles_fleet_id_fkey FOREIGN KEY (fleet_id) REFERENCES public.fleets(id),
  CONSTRAINT fleet_vehicles_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(id)
);

CREATE TABLE public.fleets (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  faction_id integer NOT NULL,
  status_id integer NOT NULL,
  position integer NOT NULL,
  moving_to integer,
  moving_since timestamp with time zone,
  fighting_fleet_id integer,
  health integer NOT NULL DEFAULT 100 CHECK (health >= 0),
  total_cs integer NOT NULL DEFAULT 0 CHECK (total_cs >= 0),
  name text,
  faction_fleet_number integer NOT NULL,
  infantry_count bigint NOT NULL DEFAULT 0,
  fleet_type_id integer,
  CONSTRAINT fleets_pkey PRIMARY KEY (id),
  CONSTRAINT fleets_fleet_type_id_fkey FOREIGN KEY (fleet_type_id) REFERENCES public.fleet_types(id),
  CONSTRAINT fleets_faction_number_unique UNIQUE (faction_id, faction_fleet_number),
  CONSTRAINT fleets_status_id_fkey FOREIGN KEY (status_id) REFERENCES public.fleet_status(id),
  CONSTRAINT fleets_position_fkey FOREIGN KEY (position) REFERENCES public.worlds(id),
  CONSTRAINT fleets_moving_to_fkey FOREIGN KEY (moving_to) REFERENCES public.worlds(id),
  CONSTRAINT fleets_fighting_fleet_id_fkey FOREIGN KEY (fighting_fleet_id) REFERENCES public.fleets(id),
  CONSTRAINT fleets_faction_id_fkey FOREIGN KEY (faction_id) REFERENCES public.factions(id)
);

CREATE TABLE public.games (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  user_id bigint,
  score integer,
  date timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  game_type text,
  CONSTRAINT games_pkey PRIMARY KEY (id),
  CONSTRAINT games_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);

CREATE TABLE public.kanban_boards (
  id integer NOT NULL DEFAULT nextval('kanban_boards_id_seq'::regclass),
  name text NOT NULL UNIQUE,
  position integer NOT NULL,
  color integer NOT NULL DEFAULT 3447003,
  CONSTRAINT kanban_boards_pkey PRIMARY KEY (id)
);

CREATE TABLE public.kanban_organizations (
  id integer NOT NULL DEFAULT nextval('kanban_organizations_id_seq'::regclass),
  name text NOT NULL UNIQUE,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT kanban_organizations_pkey PRIMARY KEY (id)
);

CREATE TABLE public.kanban_subtasks (
  id integer NOT NULL DEFAULT nextval('kanban_subtasks_id_seq'::regclass),
  task_id integer NOT NULL,
  title text NOT NULL,
  done boolean NOT NULL DEFAULT false,
  position integer NOT NULL DEFAULT 0,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT kanban_subtasks_pkey PRIMARY KEY (id),
  CONSTRAINT kanban_subtasks_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.kanban_tasks(id)
);

CREATE TABLE public.kanban_task_assignees (
  task_id integer NOT NULL,
  user_id bigint NOT NULL,
  assigned_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT kanban_task_assignees_pkey PRIMARY KEY (task_id, user_id),
  CONSTRAINT kanban_task_assignees_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.kanban_tasks(id)
);

CREATE TABLE public.kanban_tasks (
  id integer NOT NULL DEFAULT nextval('kanban_tasks_id_seq'::regclass),
  title text NOT NULL,
  description text,
  board_id integer NOT NULL,
  org_id integer,
  priority text NOT NULL DEFAULT 'medium'::text CHECK (priority = ANY (ARRAY['low'::text, 'medium'::text, 'high'::text, 'critical'::text])),
  created_by bigint NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT kanban_tasks_pkey PRIMARY KEY (id),
  CONSTRAINT kanban_tasks_board_id_fkey FOREIGN KEY (board_id) REFERENCES public.kanban_boards(id),
  CONSTRAINT kanban_tasks_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.kanban_organizations(id)
);

CREATE TABLE public.local_treasury (
  world_id integer NOT NULL,
  faction_id integer NOT NULL,
  resource_id integer NOT NULL,
  amount bigint NOT NULL DEFAULT 0,
  storage bigint,
  CONSTRAINT local_treasury_pkey PRIMARY KEY (world_id, faction_id, resource_id),
  CONSTRAINT local_treasury_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(id),
  CONSTRAINT local_treasury_world_id_faction_id_fkey FOREIGN KEY (world_id, faction_id) REFERENCES public.world_factions(world_id, faction_id)
);

CREATE TABLE public.military_recruitment (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  faction_id integer NOT NULL,
  amount integer NOT NULL CHECK (amount > 0),
  role_name text NOT NULL DEFAULT 'soldiers'::text,
  start_time timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  completion_time timestamp with time zone NOT NULL,
  status character varying NOT NULL DEFAULT 'training'::character varying,
  fleet_id integer,
  CONSTRAINT military_recruitment_pkey PRIMARY KEY (id),
  CONSTRAINT military_recruitment_faction_id_fkey FOREIGN KEY (faction_id) REFERENCES public.factions(id),
  CONSTRAINT military_recruitment_fleet_id_fkey FOREIGN KEY (fleet_id) REFERENCES public.fleets(id) ON DELETE SET NULL
);

CREATE INDEX idx_military_recruitment_faction ON public.military_recruitment(faction_id);
CREATE INDEX idx_military_recruitment_completion ON public.military_recruitment(completion_time);
CREATE INDEX idx_military_recruitment_status ON public.military_recruitment(status);

CREATE TABLE public.spirit_types (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  key text NOT NULL,
  display_name text NOT NULL,
  effect_type text NOT NULL CHECK (effect_type IN ('efficiency', 'efficiency_factory')),
  fixed_value numeric,
  per_hex_value numeric,
  min_value numeric,
  max_value numeric,
  CONSTRAINT spirit_types_pkey PRIMARY KEY (id),
  CONSTRAINT spirit_types_key_key UNIQUE (key)
);

CREATE TABLE public.national_spirits (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  faction_id integer NOT NULL,
  spirit_type_id integer NOT NULL,
  modifier_value numeric NOT NULL,
  granted_at timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at timestamp with time zone,
  CONSTRAINT national_spirits_pkey PRIMARY KEY (id),
  CONSTRAINT national_spirits_faction_id_fkey FOREIGN KEY (faction_id) REFERENCES public.factions(id),
  CONSTRAINT national_spirits_spirit_type_id_fkey FOREIGN KEY (spirit_type_id) REFERENCES public.spirit_types(id),
  CONSTRAINT uq_national_spirits_faction_type UNIQUE (faction_id, spirit_type_id)
);

CREATE INDEX idx_national_spirits_faction ON public.national_spirits(faction_id);

INSERT INTO spirit_types (key, display_name, effect_type, fixed_value) VALUES
    ('victorious', 'Victorious', 'efficiency', 0.10),
    ('recovering', 'Recovering', 'efficiency', 0.50)
ON CONFLICT (key) DO NOTHING;

INSERT INTO spirit_types (key, display_name, effect_type, per_hex_value, min_value, max_value) VALUES
    ('resilience', 'Resilience', 'efficiency', 0.0008, 0.15, 0.50)
ON CONFLICT (key) DO NOTHING;

INSERT INTO spirit_types (key, display_name, effect_type, fixed_value) VALUES
    ('war_effort', 'War Effort', 'efficiency', 0.05),
    ('war_mobilization', 'War Mobilization', 'efficiency_factory', 0.15)
ON CONFLICT (key) DO NOTHING;

CREATE TABLE public.operators (
  id           bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  discord_id   bigint NOT NULL,
  license_hash text NOT NULL,
  locked       boolean NOT NULL DEFAULT false,
  created_at   timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT operators_pkey PRIMARY KEY (id),
  CONSTRAINT operators_discord_id_key UNIQUE (discord_id)
);

CREATE OR REPLACE FUNCTION public.enforce_operator_cap()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF (SELECT count(*) FROM public.operators) >= 10 THEN
    RAISE EXCEPTION 'operator cap of 10 reached';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_operator_cap
BEFORE INSERT ON public.operators
FOR EACH ROW EXECUTE FUNCTION public.enforce_operator_cap();

CREATE TABLE public.operator_refresh_tokens (
  id          bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  operator_id bigint NOT NULL,
  token_hash  text NOT NULL,
  expires_at  timestamptz NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT operator_refresh_tokens_pkey PRIMARY KEY (id),
  CONSTRAINT operator_refresh_tokens_operator_id_fkey
      FOREIGN KEY (operator_id) REFERENCES public.operators(id) ON DELETE CASCADE,
  CONSTRAINT operator_refresh_tokens_operator_id_key UNIQUE (operator_id),
  CONSTRAINT operator_refresh_tokens_token_hash_key UNIQUE (token_hash)
);

CREATE INDEX idx_operator_refresh_tokens_expires_at
  ON public.operator_refresh_tokens (expires_at);

CREATE TABLE public.refresh_tokens (
  id               bigint NOT NULL DEFAULT nextval('refresh_tokens_id_seq'::regclass),
  token_hash       text NOT NULL UNIQUE,
  family_id        uuid NOT NULL,
  user_id          bigint NOT NULL,
  discord_id       bigint NOT NULL,
  issued_at        timestamp with time zone NOT NULL DEFAULT now(),
  expires_at       timestamp with time zone NOT NULL,
  revoked          boolean NOT NULL DEFAULT false,
  revoked_at       timestamp with time zone,
  discord_username text NOT NULL DEFAULT ''::text,
  discord_avatar   text,
  CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id)
);

CREATE INDEX idx_refresh_tokens_expires_at ON public.refresh_tokens (expires_at);

CREATE OR REPLACE FUNCTION public.purge_expired_refresh_tokens()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  DELETE FROM public.refresh_tokens WHERE expires_at < now();
  RETURN NULL;
END;
$$;

CREATE TRIGGER trg_purge_expired_refresh_tokens
AFTER INSERT ON public.refresh_tokens
FOR EACH STATEMENT EXECUTE FUNCTION public.purge_expired_refresh_tokens();

CREATE TABLE public.operator_assets (
  id               integer NOT NULL DEFAULT 1,
  api_token        text,
  bot_config       jsonb NOT NULL DEFAULT '{}'::jsonb,
  database_url     text,
  firebase_api_key text,
  updated_at       timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT operator_assets_pkey PRIMARY KEY (id),
  CONSTRAINT operator_assets_singleton CHECK (id = 1)
);

GRANT USAGE ON SCHEMA public TO bot_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO bot_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO bot_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO bot_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT EXECUTE ON FUNCTIONS TO bot_app;

CREATE OR REPLACE FUNCTION public.purge_expired_operator_refresh_tokens()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  DELETE FROM public.operator_refresh_tokens WHERE expires_at < now();
  RETURN NULL;
END;
$$;

CREATE TRIGGER trg_purge_expired_operator_refresh_tokens
AFTER INSERT ON public.operator_refresh_tokens
FOR EACH STATEMENT EXECUTE FUNCTION public.purge_expired_operator_refresh_tokens();

CREATE OR REPLACE FUNCTION public.revoke_refresh_token_on_lock()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.locked = true AND OLD.locked = false THEN
    DELETE FROM public.operator_refresh_tokens WHERE operator_id = NEW.id;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_revoke_refresh_token_on_lock
AFTER UPDATE OF locked ON public.operators
FOR EACH ROW EXECUTE FUNCTION public.revoke_refresh_token_on_lock();

CREATE OR REPLACE FUNCTION public.is_valid_operator_jwt()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.operators o
    WHERE o.id = (auth.jwt() ->> 'operator_id')::bigint
      AND (auth.jwt() ->> 'app_role') = 'authenticated_operator'
      AND o.locked = false
  )
$$;

CREATE OR REPLACE FUNCTION public.rotate_operator_refresh_token(
  p_old_hash text,
  p_new_hash text,
  p_new_expires_at timestamptz
)
RETURNS TABLE (operator_id bigint)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  RETURN QUERY
  UPDATE public.operator_refresh_tokens
  SET token_hash = p_new_hash,
      expires_at = p_new_expires_at,
      created_at = now()
  WHERE token_hash = p_old_hash AND expires_at > now()
  RETURNING operator_refresh_tokens.operator_id;
END;
$$;

CREATE TABLE public.pact_members (
  pact_id integer NOT NULL,
  faction_id integer NOT NULL,
  date_joined timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT pact_members_pkey PRIMARY KEY (pact_id, faction_id),
  CONSTRAINT pact_members_pact_id_fkey FOREIGN KEY (pact_id) REFERENCES public.pacts(id),
  CONSTRAINT pact_members_faction_id_fkey FOREIGN KEY (faction_id) REFERENCES public.factions(id)
);

CREATE TABLE public.pact_types (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  name text NOT NULL,
  description text,
  influence_cost integer NOT NULL DEFAULT 0,
  CONSTRAINT pact_types_pkey PRIMARY KEY (id)
);

CREATE TABLE public.pacts (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  name text NOT NULL,
  pact_type_id integer NOT NULL,
  leader_id integer NOT NULL,
  date_created timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT pacts_pkey PRIMARY KEY (id),
  CONSTRAINT pacts_pact_type_id_fkey FOREIGN KEY (pact_type_id) REFERENCES public.pact_types(id),
  CONSTRAINT pacts_leader_id_fkey FOREIGN KEY (leader_id) REFERENCES public.factions(id)
);

CREATE TABLE public.resource_transfers (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  from_faction_id integer NOT NULL,
  to_faction_id integer NOT NULL,
  from_world_id integer NOT NULL,
  to_world_id integer NOT NULL,
  status_id smallint NOT NULL DEFAULT 1,
  start_time timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
  arrival_time timestamp with time zone NOT NULL,
  actual_arrival timestamp with time zone,
  intercepting_faction_id integer,
  intercepted_by_fleet_id integer,
  interception_time timestamp with time zone,
  interception_world_id integer,
  escort_fleet_id integer,
  CONSTRAINT resource_transfers_pkey PRIMARY KEY (id),
  CONSTRAINT resource_transfers_status_id_fkey FOREIGN KEY (status_id) REFERENCES public.transfer_statuses(id),
  CONSTRAINT resource_transfers_from_world_id_fkey FOREIGN KEY (from_world_id) REFERENCES public.worlds(id),
  CONSTRAINT resource_transfers_to_world_id_fkey FOREIGN KEY (to_world_id) REFERENCES public.worlds(id),
  CONSTRAINT resource_transfers_interception_world_id_fkey FOREIGN KEY (interception_world_id) REFERENCES public.worlds(id),
  CONSTRAINT resource_transfers_from_faction_id_fkey FOREIGN KEY (from_faction_id) REFERENCES public.factions(id),
  CONSTRAINT resource_transfers_to_faction_id_fkey FOREIGN KEY (to_faction_id) REFERENCES public.factions(id),
  CONSTRAINT resource_transfers_intercepting_faction_id_fkey FOREIGN KEY (intercepting_faction_id) REFERENCES public.factions(id),
  CONSTRAINT resource_transfers_intercepted_by_fleet_id_fkey FOREIGN KEY (intercepted_by_fleet_id) REFERENCES public.fleets(id),
  CONSTRAINT resource_transfers_escort_fleet_id_fkey FOREIGN KEY (escort_fleet_id) REFERENCES public.fleets(id)
);

CREATE TABLE public.transfer_statuses (
  id smallint NOT NULL,
  name text NOT NULL,
  CONSTRAINT transfer_statuses_pkey PRIMARY KEY (id),
  CONSTRAINT transfer_statuses_name_key UNIQUE (name)
);

CREATE TABLE public.resources (
  id integer NOT NULL,
  name text NOT NULL,
  refined_from integer,
  is_limited boolean NOT NULL,
  hard_limit integer,
  is_transferable boolean NOT NULL DEFAULT true,
  CONSTRAINT resources_pkey PRIMARY KEY (id),
  CONSTRAINT resources_refined_from_fkey FOREIGN KEY (refined_from) REFERENCES public.resources(id)
);

CREATE TABLE public.settings (
  last_income timestamp with time zone,
  income_day integer NOT NULL DEFAULT 6,
  min_version text,
  CONSTRAINT settings_pkey PRIMARY KEY (income_day)
);

CREATE TABLE public.trade_deals (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  sender_faction_id integer NOT NULL,
  receiver_faction_id integer NOT NULL,
  resource_id integer NOT NULL,
  amount integer NOT NULL CHECK (amount > 0),
  date_started timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  sender_world_id integer,
  receiver_world_id integer,
  escort_fleet_id integer,
  CONSTRAINT trade_deals_pkey PRIMARY KEY (id),
  CONSTRAINT trade_deals_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(id),
  CONSTRAINT trade_deals_sender_world_id_fkey FOREIGN KEY (sender_world_id) REFERENCES public.worlds(id),
  CONSTRAINT trade_deals_receiver_world_id_fkey FOREIGN KEY (receiver_world_id) REFERENCES public.worlds(id),
  CONSTRAINT trade_deals_sender_faction_id_fkey FOREIGN KEY (sender_faction_id) REFERENCES public.factions(id),
  CONSTRAINT trade_deals_receiver_faction_id_fkey FOREIGN KEY (receiver_faction_id) REFERENCES public.factions(id),
  CONSTRAINT trade_deals_escort_fleet_id_fkey FOREIGN KEY (escort_fleet_id) REFERENCES public.fleets(id)
);

CREATE TABLE public.transfer_resources (
  transfer_id integer NOT NULL,
  resource_id integer NOT NULL,
  amount bigint NOT NULL CHECK (amount > 0),
  CONSTRAINT transfer_resources_pkey PRIMARY KEY (transfer_id, resource_id),
  CONSTRAINT transfer_resources_transfer_id_fkey FOREIGN KEY (transfer_id) REFERENCES public.resource_transfers(id),
  CONSTRAINT transfer_resources_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(id)
);

CREATE TABLE public.users (
  id bigint NOT NULL,
  access_level integer NOT NULL,
  badge_ids integer[] DEFAULT '{}'::integer[],
  ephemeral_commands boolean NOT NULL DEFAULT false,
  notify_mode text NOT NULL DEFAULT 'off' CHECK (notify_mode IN ('off', 'dm', 'channel')),
  notify_channel_id bigint,
  notify_transfers boolean NOT NULL DEFAULT true,
  notify_movements boolean NOT NULL DEFAULT true,
  notify_origin boolean NOT NULL DEFAULT true,
  notify_destination boolean NOT NULL DEFAULT true,
  CONSTRAINT users_pkey PRIMARY KEY (id)
);

CREATE TABLE public.vehicle_construction (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  world_id integer NOT NULL,
  fleet_id integer NOT NULL,
  vehicle_id integer NOT NULL,
  quantity integer NOT NULL CHECK (quantity > 0),
  factory_space_used integer NOT NULL CHECK (factory_space_used > 0),
  start_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  completion_date timestamp with time zone NOT NULL,
  CONSTRAINT vehicle_construction_pkey PRIMARY KEY (id),
  CONSTRAINT vehicle_construction_world_id_fkey FOREIGN KEY (world_id) REFERENCES public.worlds(id),
  CONSTRAINT vehicle_construction_fleet_id_fkey FOREIGN KEY (fleet_id) REFERENCES public.fleets(id),
  CONSTRAINT vehicle_construction_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(id)
);

CREATE TABLE public.vehicle_costs (
  vehicle_id integer NOT NULL,
  resource_id integer NOT NULL,
  amount bigint NOT NULL CHECK (amount > 0),
  CONSTRAINT vehicle_costs_pkey PRIMARY KEY (vehicle_id, resource_id),
  CONSTRAINT vehicle_costs_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(id),
  CONSTRAINT vehicle_costs_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(id)
);

CREATE TABLE public.vehicle_types (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  name text NOT NULL,
  CONSTRAINT vehicle_types_pkey PRIMARY KEY (id)
);

CREATE TABLE public.vehicles (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  faction_id integer NOT NULL,
  type integer,
  name text NOT NULL,
  designation text CHECK (length(designation) <= 25),
  vehicle_data jsonb[],
  faction_vehicle_number integer NOT NULL,
  CONSTRAINT vehicles_pkey PRIMARY KEY (id),
  CONSTRAINT vehicles_faction_number_unique UNIQUE (faction_id, faction_vehicle_number),
  CONSTRAINT vehicles_type_fkey FOREIGN KEY (type) REFERENCES public.vehicle_types(id),
  CONSTRAINT vehicles_faction_id_fkey FOREIGN KEY (faction_id) REFERENCES public.factions(id)
);

CREATE TABLE public.war_participants (
  war_id integer NOT NULL,
  faction_id integer NOT NULL,
  side text NOT NULL,
  CONSTRAINT war_participants_pkey PRIMARY KEY (war_id, faction_id),
  CONSTRAINT war_participants_war_id_fkey FOREIGN KEY (war_id) REFERENCES public.wars(id),
  CONSTRAINT war_participants_faction_id_fkey FOREIGN KEY (faction_id) REFERENCES public.factions(id)
);

CREATE TABLE public.wars (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  date_start timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  name text,
  CONSTRAINT wars_pkey PRIMARY KEY (id)
);

CREATE TABLE public.world_factions (
  world_id integer NOT NULL,
  faction_id integer NOT NULL,
  territory integer,
  CONSTRAINT world_factions_pkey PRIMARY KEY (world_id, faction_id),
  CONSTRAINT world_factions_world_id_fkey FOREIGN KEY (world_id) REFERENCES public.worlds(id),
  CONSTRAINT world_factions_faction_id_fkey FOREIGN KEY (faction_id) REFERENCES public.factions(id)
);

CREATE TABLE public.world_resources (
  world_id integer NOT NULL,
  resource_id integer NOT NULL,
  percentage integer NOT NULL CHECK (percentage >= 1 AND percentage <= 100),
  hard_amount integer,
  CONSTRAINT world_resources_pkey PRIMARY KEY (world_id, resource_id),
  CONSTRAINT world_resources_world_id_fkey FOREIGN KEY (world_id) REFERENCES public.worlds(id),
  CONSTRAINT world_resources_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(id)
);

CREATE TABLE public.worlds (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  name text NOT NULL,
  orbit_of integer,
  background text,
  hex_count integer NOT NULL DEFAULT 0 CHECK (hex_count >= 0),
  population_capacity_per_hex integer,
  CONSTRAINT worlds_pkey PRIMARY KEY (id),
  CONSTRAINT worlds_orbit_of_fkey FOREIGN KEY (orbit_of) REFERENCES public.worlds(id)
);






INSERT INTO fleet_status (name, description) VALUES
    ('idle',        'Fleet is idle and ready for orders'),
    ('defence',     'Fleet is on defensive posture'),
    ('patrol',      'Fleet is on patrol'),
    ('in combat',   'Fleet is engaged in battle'),
    ('blockading',  'Fleet is participating in a blockade'),
    ('travelling',  'Fleet is moving between worlds'),
    ('mothballed',  'Fleet is in long-term storage, consuming minimal resources'),
    ('debris',      'Fleet is destroyed and cannot operate'),
    ('FTL supply',  'Fleet is assigned to FTL logistics for off-system hex maintenance')
ON CONFLICT (name) DO NOTHING;

INSERT INTO transfer_statuses (id, name) VALUES
    (1, 'in_transit'),
    (2, 'intercepted')
ON CONFLICT (id) DO NOTHING;

INSERT INTO kanban_boards (name, position, color) VALUES
    ('Backlog', 0, 9807270),
    ('Todo',    1, 3447003),
    ('Doing',   2, 16776960),
    ('QA',      3, 16753920),
    ('Done',    4, 65280)
ON CONFLICT (name) DO NOTHING;

DO $migrate_faction_type$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'factions' AND column_name = 'is_company') THEN
        ALTER TABLE public.factions ADD COLUMN IF NOT EXISTS faction_type integer NOT NULL DEFAULT 0;
        ALTER TABLE public.factions ADD COLUMN IF NOT EXISTS capital_world_id integer REFERENCES public.worlds(id);
        UPDATE public.factions SET faction_type = CASE WHEN is_company THEN 1 ELSE 0 END;
        ALTER TABLE public.factions DROP COLUMN is_company;
    END IF;
END
$migrate_faction_type$;

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS ephemeral_commands boolean NOT NULL DEFAULT false;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS notify_mode text NOT NULL DEFAULT 'off';
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS notify_channel_id bigint;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS notify_transfers boolean NOT NULL DEFAULT true;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS notify_movements boolean NOT NULL DEFAULT true;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS notify_origin boolean NOT NULL DEFAULT true;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS notify_destination boolean NOT NULL DEFAULT true;

CREATE TABLE IF NOT EXISTS public.fleet_types (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  name text NOT NULL,
  CONSTRAINT fleet_types_pkey PRIMARY KEY (id)
);

ALTER TABLE public.fleets ADD COLUMN IF NOT EXISTS fleet_type_id integer REFERENCES public.fleet_types(id);










CREATE OR REPLACE FUNCTION public.get_player_discord_id()
RETURNS bigint
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
  SELECT u.id
  FROM public.users u
  WHERE u.id = (auth.jwt() -> 'user_metadata' ->> 'provider_id')::bigint
    AND u.access_level >= 0
$$;

ALTER TABLE public.users                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.operators               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.operator_refresh_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.operator_assets         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.factions                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.worlds                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.world_factions          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.world_resources         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fleet_status            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fleets                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fleet_vehicles          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vehicles                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vehicle_types           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vehicle_construction    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vehicle_costs           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.buildings               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.buildings_generators    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.buildings_storages      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.building_costs          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.faction_world_buildings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.faction_treasury        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.local_treasury          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resources               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transfer_statuses       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.national_spirits        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.spirit_types             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trade_deals             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resource_transfers      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transfer_resources      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.badges                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.badge_costs             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.badge_progress_resources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pacts                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pact_types              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pact_members            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wars                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.war_participants        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.battles                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.battle_participants     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.blockades               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.blockade_fleets         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.blockade_targets        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.military_recruitment    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.settings                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.custom_user_messages    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.kanban_organizations    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.kanban_boards           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.kanban_tasks            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.kanban_task_assignees   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.kanban_subtasks         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.games                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.comets                  ENABLE ROW LEVEL SECURITY;


CREATE POLICY "players_read" ON public.fleet_status         FOR SELECT TO authenticated USING (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_read" ON public.vehicle_types        FOR SELECT TO authenticated USING (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_read" ON public.resources            FOR SELECT TO authenticated USING (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_read" ON public.transfer_statuses     FOR SELECT TO authenticated USING (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_read" ON public.spirit_types          FOR SELECT TO authenticated USING (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_read" ON public.buildings            FOR SELECT TO authenticated USING (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_read" ON public.buildings_generators FOR SELECT TO authenticated USING (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_read" ON public.buildings_storages   FOR SELECT TO authenticated USING (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_read" ON public.building_costs       FOR SELECT TO authenticated USING (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_read" ON public.vehicle_costs        FOR SELECT TO authenticated USING (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_read" ON public.pact_types           FOR SELECT TO authenticated USING (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_read" ON public.badges               FOR SELECT TO authenticated USING (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_read" ON public.badge_costs          FOR SELECT TO authenticated USING (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_read" ON public.badge_progress_resources FOR SELECT TO authenticated USING (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_read" ON public.settings             FOR SELECT TO authenticated USING (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_read" ON public.users                FOR SELECT TO authenticated USING (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_read" ON public.games                FOR SELECT TO authenticated USING (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_read" ON public.custom_user_messages FOR SELECT TO authenticated USING (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_read" ON public.comets               FOR SELECT TO authenticated USING (public.get_player_discord_id() IS NOT NULL);

CREATE POLICY operator_assets_select_any_operator ON public.operator_assets
FOR SELECT TO authenticated, anon
USING (public.is_valid_operator_jwt());


CREATE POLICY "players_all" ON public.factions                FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.worlds                  FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.world_factions          FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.world_resources         FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.fleets                  FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.fleet_vehicles          FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.vehicles                FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.vehicle_construction    FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.faction_world_buildings FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.faction_treasury        FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.local_treasury          FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.trade_deals             FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.resource_transfers      FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.transfer_resources      FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.pacts                   FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.pact_members            FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.wars                    FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.national_spirits        FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.war_participants        FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.battles                 FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.battle_participants     FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.blockades               FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.blockade_fleets         FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.blockade_targets        FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.military_recruitment    FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.kanban_organizations    FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.kanban_boards           FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.kanban_tasks            FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.kanban_task_assignees   FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);
CREATE POLICY "players_all" ON public.kanban_subtasks         FOR ALL TO authenticated USING (public.get_player_discord_id() IS NOT NULL) WITH CHECK (public.get_player_discord_id() IS NOT NULL);

-- bot_app connects via raw Postgres DSN (no Supabase JWT), so it matches none of the
-- TO authenticated policies above. Grant it full-trust access per table separately.
CREATE POLICY "bot_app_all" ON public.users FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.operators FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.operator_refresh_tokens FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.operator_assets FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.factions FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.worlds FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.world_factions FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.world_resources FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.fleet_status FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.fleets FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.fleet_vehicles FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.vehicles FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.vehicle_types FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.vehicle_construction FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.vehicle_costs FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.buildings FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.buildings_generators FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.buildings_storages FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.building_costs FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.faction_world_buildings FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.faction_treasury FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.local_treasury FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.resources FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.transfer_statuses FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.national_spirits FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.spirit_types FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.trade_deals FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.resource_transfers FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.transfer_resources FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.badges FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.badge_costs FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.badge_progress_resources FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.pacts FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.pact_types FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.pact_members FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.wars FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.war_participants FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.battles FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.battle_participants FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.blockades FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.blockade_fleets FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.blockade_targets FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.military_recruitment FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.settings FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.custom_user_messages FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.kanban_organizations FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.kanban_boards FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.kanban_tasks FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.kanban_task_assignees FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.kanban_subtasks FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.games FOR ALL TO bot_app USING (true) WITH CHECK (true);
CREATE POLICY "bot_app_all" ON public.comets FOR ALL TO bot_app USING (true) WITH CHECK (true);
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
