-- Copyright (c) 2026 f4rsantos. All rights reserved.
-- Unauthorized copying, modification, or distribution of this file,
-- via any medium, is strictly prohibited without explicit written
-- permission from the copyright holder. Contact: f4rsantos@gmail.com













CREATE OR REPLACE FUNCTION sp_deduct_resources(
    p_faction_id    INT,
    p_world_id      INT,       
    p_resources     JSONB      
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    r           JSONB;
    v_res_id    INT;
    v_amount    BIGINT;
    v_current   BIGINT;
BEGIN
    FOR r IN SELECT * FROM jsonb_array_elements(p_resources)
    LOOP
        SELECT id INTO v_res_id FROM resources WHERE name = r->>'name';
        IF v_res_id IS NULL THEN
            RAISE EXCEPTION 'RESOURCE_NOT_FOUND: Unknown resource %', r->>'name';
        END IF;
        v_amount := (r->>'amount')::BIGINT;

        IF p_world_id IS NOT NULL AND r->>'name' IN ('CM','EL','CS','U-CM','U-EL','U-CS','Population') THEN
            SELECT COALESCE(amount, 0) INTO v_current
            FROM local_treasury
            WHERE faction_id = p_faction_id AND world_id = p_world_id AND resource_id = v_res_id;

            IF COALESCE(v_current, 0) < v_amount THEN
                RAISE EXCEPTION 'RESOURCE_INSUFFICIENT: Insufficient % — need %, have %',
                    r->>'name', v_amount, COALESCE(v_current, 0);
            END IF;

            UPDATE local_treasury
            SET amount = amount - v_amount
            WHERE faction_id = p_faction_id AND world_id = p_world_id AND resource_id = v_res_id;
        ELSE
            SELECT COALESCE(amount, 0) INTO v_current
            FROM faction_treasury
            WHERE faction_id = p_faction_id AND resource_id = v_res_id;

            IF COALESCE(v_current, 0) < v_amount THEN
                RAISE EXCEPTION 'RESOURCE_INSUFFICIENT: Insufficient % — need %, have %',
                    r->>'name', v_amount, COALESCE(v_current, 0);
            END IF;

            UPDATE faction_treasury
            SET amount = amount - v_amount
            WHERE faction_id = p_faction_id AND resource_id = v_res_id;
        END IF;
    END LOOP;
END;
$$;


CREATE OR REPLACE FUNCTION sp_add_resources(
    p_faction_id    INT,
    p_world_id      INT,       
    p_resources     JSONB      
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    r           JSONB;
    v_res_id    INT;
    v_amount    BIGINT;
BEGIN
    FOR r IN SELECT * FROM jsonb_array_elements(p_resources)
    LOOP
        SELECT id INTO v_res_id FROM resources WHERE name = r->>'name';
        IF v_res_id IS NULL THEN
            RAISE EXCEPTION 'RESOURCE_NOT_FOUND: Unknown resource %', r->>'name';
        END IF;
        v_amount := (r->>'amount')::BIGINT;

        IF p_world_id IS NOT NULL AND r->>'name' IN ('CM','EL','CS','U-CM','U-EL','U-CS','Population') THEN
            INSERT INTO world_factions (world_id, faction_id, territory)
            VALUES (p_world_id, p_faction_id, 0)
            ON CONFLICT (world_id, faction_id) DO NOTHING;

            INSERT INTO local_treasury (faction_id, world_id, resource_id, amount)
            VALUES (p_faction_id, p_world_id, v_res_id, v_amount)
            ON CONFLICT (faction_id, world_id, resource_id)
            DO UPDATE SET amount = local_treasury.amount + v_amount;
        ELSE
            INSERT INTO faction_treasury (faction_id, resource_id, amount)
            VALUES (p_faction_id, v_res_id, v_amount)
            ON CONFLICT (faction_id, resource_id)
            DO UPDATE SET amount = faction_treasury.amount + v_amount;
        END IF;
    END LOOP;
END;
$$;






CREATE OR REPLACE FUNCTION sp_upgrade_buildings(
    p_faction_id    INT,
    p_world_id      INT,
    p_building_id   INT,
    p_amount        INT,
    p_source_level  INT,
    p_target_level  INT,
    p_costs         JSONB      
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_current_amount    INT;
    v_new_source        INT;
    v_key               TEXT;
    v_cost              BIGINT;
    v_res_id            INT;
    v_current_res       BIGINT;
BEGIN
    
    SELECT amount INTO v_current_amount
    FROM faction_world_buildings
    WHERE faction_id = p_faction_id AND world_id = p_world_id
      AND building_id = p_building_id AND level = p_source_level;

    IF COALESCE(v_current_amount, 0) < p_amount THEN
        RAISE EXCEPTION 'INSUFFICIENT_BUILDINGS: Not enough level % buildings — have %, need %',
            p_source_level, COALESCE(v_current_amount, 0), p_amount;
    END IF;

    
    FOR v_key, v_cost IN SELECT key, (value::TEXT)::BIGINT FROM jsonb_each(p_costs)
    LOOP
        SELECT id INTO v_res_id FROM resources WHERE name = v_key;
        IF v_res_id IS NULL THEN
            RAISE EXCEPTION 'RESOURCE_NOT_FOUND: Unknown resource %', v_key;
        END IF;

        IF v_key IN ('CM','EL','CS','U-CM','U-EL','U-CS','Population') THEN
            SELECT COALESCE(amount, 0) INTO v_current_res
            FROM local_treasury
            WHERE faction_id = p_faction_id AND world_id = p_world_id AND resource_id = v_res_id;

            IF COALESCE(v_current_res, 0) < v_cost THEN
                RAISE EXCEPTION 'RESOURCE_INSUFFICIENT: Insufficient % — need %, have %',
                    v_key, v_cost, COALESCE(v_current_res, 0);
            END IF;

            UPDATE local_treasury SET amount = amount - v_cost
            WHERE faction_id = p_faction_id AND world_id = p_world_id AND resource_id = v_res_id;
        ELSE
            SELECT COALESCE(amount, 0) INTO v_current_res
            FROM faction_treasury
            WHERE faction_id = p_faction_id AND resource_id = v_res_id;

            IF COALESCE(v_current_res, 0) < v_cost THEN
                RAISE EXCEPTION 'RESOURCE_INSUFFICIENT: Insufficient % — need %, have %',
                    v_key, v_cost, COALESCE(v_current_res, 0);
            END IF;

            UPDATE faction_treasury SET amount = amount - v_cost
            WHERE faction_id = p_faction_id AND resource_id = v_res_id;
        END IF;
    END LOOP;

    
    v_new_source := v_current_amount - p_amount;
    IF v_new_source = 0 THEN
        DELETE FROM faction_world_buildings
        WHERE faction_id = p_faction_id AND world_id = p_world_id
          AND building_id = p_building_id AND level = p_source_level;
    ELSE
        UPDATE faction_world_buildings SET amount = v_new_source
        WHERE faction_id = p_faction_id AND world_id = p_world_id
          AND building_id = p_building_id AND level = p_source_level;
    END IF;

    INSERT INTO faction_world_buildings (faction_id, world_id, building_id, level, amount)
    VALUES (p_faction_id, p_world_id, p_building_id, p_target_level, p_amount)
    ON CONFLICT (faction_id, world_id, building_id, level)
    DO UPDATE SET amount = faction_world_buildings.amount + p_amount;
END;
$$;






CREATE OR REPLACE FUNCTION sp_create_transfer(
    p_from_faction_id   INT,
    p_to_faction_id     INT,
    p_from_world_id     INT,
    p_to_world_id       INT,
    p_resources         JSONB,
    p_start_time        TIMESTAMPTZ,
    p_arrival_time      TIMESTAMPTZ,
    p_escort_fleet_id   INT DEFAULT NULL
) RETURNS INT LANGUAGE plpgsql AS $$
DECLARE
    v_res           JSONB;
    v_res_id        INT;
    v_amount        BIGINT;
    v_current       BIGINT;
    v_transfer_id   INT;
BEGIN
    FOR v_res IN SELECT * FROM jsonb_array_elements(p_resources)
    LOOP
        v_res_id := (v_res->>'resource_id')::INT;
        v_amount := (v_res->>'amount')::BIGINT;

        SELECT COALESCE(amount, 0) INTO v_current
        FROM local_treasury
        WHERE faction_id = p_from_faction_id AND world_id = p_from_world_id AND resource_id = v_res_id;

        IF COALESCE(v_current, 0) < v_amount THEN
            RAISE EXCEPTION 'RESOURCE_INSUFFICIENT: Insufficient resources for transfer';
        END IF;

        UPDATE local_treasury
        SET amount = amount - v_amount
        WHERE faction_id = p_from_faction_id AND world_id = p_from_world_id AND resource_id = v_res_id;
    END LOOP;

    INSERT INTO resource_transfers
        (from_faction_id, to_faction_id, from_world_id, to_world_id, status_id, start_time, arrival_time, escort_fleet_id)
    VALUES
        (p_from_faction_id, p_to_faction_id, p_from_world_id, p_to_world_id,
         (SELECT id FROM transfer_statuses WHERE name = 'in_transit'), p_start_time, p_arrival_time, p_escort_fleet_id)
    RETURNING id INTO v_transfer_id;

    FOR v_res IN SELECT * FROM jsonb_array_elements(p_resources)
    LOOP
        INSERT INTO transfer_resources (transfer_id, resource_id, amount)
        VALUES (v_transfer_id, (v_res->>'resource_id')::INT, (v_res->>'amount')::BIGINT);
    END LOOP;

    RETURN v_transfer_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_deposit_transfer(
    p_transfer_id INT
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_transfer  RECORD;
    v_res       RECORD;
BEGIN
    SELECT * INTO v_transfer FROM resource_transfers WHERE id = p_transfer_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'TRANSFER_NOT_FOUND: Transfer #% does not exist', p_transfer_id;
    END IF;

    FOR v_res IN SELECT resource_id, amount FROM transfer_resources WHERE transfer_id = p_transfer_id
    LOOP
        INSERT INTO local_treasury (faction_id, world_id, resource_id, amount)
        VALUES (v_transfer.to_faction_id, v_transfer.to_world_id, v_res.resource_id, v_res.amount)
        ON CONFLICT (faction_id, world_id, resource_id)
        DO UPDATE SET amount = local_treasury.amount + v_res.amount;
    END LOOP;

    DELETE FROM transfer_resources WHERE transfer_id = p_transfer_id;
    DELETE FROM resource_transfers WHERE id = p_transfer_id;
END;
$$;






CREATE OR REPLACE FUNCTION sp_intercept_transfer(
    p_transfer_id   INT,
    p_fleet_id      INT,
    p_world_id      INT
) RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM resource_transfers rt
        JOIN transfer_statuses ts ON rt.status_id = ts.id
        WHERE rt.id = p_transfer_id AND ts.name = 'in_transit'
    ) THEN
        RAISE EXCEPTION 'TRANSFER_NOT_FOUND: Transfer #% is not in transit', p_transfer_id;
    END IF;

    UPDATE resource_transfers
    SET status_id = (SELECT id FROM transfer_statuses WHERE name = 'intercepted'),
        intercepted_by_fleet_id = p_fleet_id,
        intercepting_faction_id = (SELECT faction_id FROM fleets WHERE id = p_fleet_id),
        interception_world_id = p_world_id,
        interception_time = CURRENT_TIMESTAMP
    WHERE id = p_transfer_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_seize_transfer(
    p_transfer_id   INT,
    p_faction_id    INT,
    p_world_id      INT
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_res RECORD;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM resource_transfers rt
        JOIN transfer_statuses ts ON rt.status_id = ts.id
        WHERE rt.id = p_transfer_id AND ts.name = 'intercepted'
    ) THEN
        RAISE EXCEPTION 'TRANSFER_NOT_INTERCEPTED: Transfer #% is not intercepted', p_transfer_id;
    END IF;

    INSERT INTO world_factions (world_id, faction_id, territory)
    VALUES (p_world_id, p_faction_id, 0)
    ON CONFLICT (world_id, faction_id) DO NOTHING;

    FOR v_res IN SELECT resource_id, amount FROM transfer_resources WHERE transfer_id = p_transfer_id
    LOOP
        INSERT INTO local_treasury (faction_id, world_id, resource_id, amount)
        VALUES (p_faction_id, p_world_id, v_res.resource_id, v_res.amount)
        ON CONFLICT (faction_id, world_id, resource_id)
        DO UPDATE SET amount = local_treasury.amount + v_res.amount;
    END LOOP;

    DELETE FROM transfer_resources WHERE transfer_id = p_transfer_id;
    DELETE FROM resource_transfers WHERE id = p_transfer_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_destroy_transfer(
    p_transfer_id   INT
) RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM resource_transfers rt
        JOIN transfer_statuses ts ON rt.status_id = ts.id
        WHERE rt.id = p_transfer_id AND ts.name = 'intercepted'
    ) THEN
        RAISE EXCEPTION 'TRANSFER_NOT_INTERCEPTED: Transfer #% is not intercepted', p_transfer_id;
    END IF;

    DELETE FROM transfer_resources WHERE transfer_id = p_transfer_id;
    DELETE FROM resource_transfers WHERE id = p_transfer_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_release_transfer(
    p_transfer_id   INT,
    p_new_arrival   TIMESTAMPTZ
) RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM resource_transfers rt
        JOIN transfer_statuses ts ON rt.status_id = ts.id
        WHERE rt.id = p_transfer_id AND ts.name = 'intercepted'
    ) THEN
        RAISE EXCEPTION 'TRANSFER_NOT_INTERCEPTED: Transfer #% is not intercepted', p_transfer_id;
    END IF;

    UPDATE resource_transfers
    SET status_id = (SELECT id FROM transfer_statuses WHERE name = 'in_transit'),
        intercepted_by_fleet_id = NULL, arrival_time = p_new_arrival
    WHERE id = p_transfer_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_conquer_hexes(
    p_conqueror_faction_id  INT,
    p_target_faction_id     INT,
    p_world_id              INT,
    p_hexes                 INT,
    p_grant_resources       BOOLEAN
) RETURNS TABLE (
    population_moved    BIGINT,
    cm_granted          BIGINT,
    el_granted          BIGINT,
    cs_granted          BIGINT,
    er_granted          BIGINT,
    influence_cost      BIGINT,
    resilience_bonus    NUMERIC
) LANGUAGE plpgsql AS $$
DECLARE
    v_target_territory  INT;
    v_influence_id      INT;
    v_influence_cost    BIGINT;
    v_current_influence BIGINT;
    v_pop_id            INT;
    v_target_pop        BIGINT;
    v_pop_moved         BIGINT := 0;
    v_cm_id             INT;
    v_el_id             INT;
    v_cs_id             INT;
    v_er_id             INT;
    v_ucm_pct           NUMERIC;
    v_uel_pct           NUMERIC;
    v_ucs_pct           NUMERIC;
    v_cm_amt            BIGINT := 0;
    v_el_amt            BIGINT := 0;
    v_cs_amt            BIGINT := 0;
    v_er_amt            BIGINT := 0;
    v_resilience        NUMERIC := 0;
    v_spirit_type_id    INT;
    v_per_hex           NUMERIC;
    v_min_value         NUMERIC;
    v_max_value         NUMERIC;
BEGIN
    IF p_hexes <= 0 THEN
        RAISE EXCEPTION 'INVALID_HEXES: Hexes must be positive';
    END IF;

    SELECT territory INTO v_target_territory
    FROM world_factions WHERE world_id = p_world_id AND faction_id = p_target_faction_id;

    IF v_target_territory IS NULL OR v_target_territory < p_hexes THEN
        RAISE EXCEPTION 'TERRITORY_INSUFFICIENT: Target faction only holds % hex(es) on this world', COALESCE(v_target_territory, 0);
    END IF;

    v_influence_cost := p_hexes * 10;
    SELECT id INTO v_influence_id FROM resources WHERE name = 'Influence';
    SELECT COALESCE(amount, 0) INTO v_current_influence
    FROM faction_treasury WHERE faction_id = p_conqueror_faction_id AND resource_id = v_influence_id;

    IF v_current_influence < v_influence_cost THEN
        RAISE EXCEPTION 'RESOURCE_INSUFFICIENT: Need % Influence, have %', v_influence_cost, v_current_influence;
    END IF;

    UPDATE faction_treasury SET amount = amount - v_influence_cost
    WHERE faction_id = p_conqueror_faction_id AND resource_id = v_influence_id;

    UPDATE world_factions SET territory = territory - p_hexes
    WHERE world_id = p_world_id AND faction_id = p_target_faction_id;

    INSERT INTO world_factions (world_id, faction_id, territory) VALUES (p_world_id, p_conqueror_faction_id, p_hexes)
    ON CONFLICT (world_id, faction_id) DO UPDATE SET territory = world_factions.territory + EXCLUDED.territory;

    SELECT id INTO v_pop_id FROM resources WHERE name = 'Population';
    SELECT COALESCE(amount, 0) INTO v_target_pop
    FROM local_treasury WHERE world_id = p_world_id AND faction_id = p_target_faction_id AND resource_id = v_pop_id;

    v_pop_moved := FLOOR(v_target_pop * p_hexes / v_target_territory::NUMERIC);

    IF v_pop_moved > 0 THEN
        UPDATE local_treasury SET amount = GREATEST(0, amount - v_pop_moved)
        WHERE world_id = p_world_id AND faction_id = p_target_faction_id AND resource_id = v_pop_id;

        INSERT INTO local_treasury (world_id, faction_id, resource_id, amount)
        VALUES (p_world_id, p_conqueror_faction_id, v_pop_id, v_pop_moved)
        ON CONFLICT (world_id, faction_id, resource_id) DO UPDATE SET amount = local_treasury.amount + v_pop_moved;
    END IF;

    IF p_grant_resources THEN
        SELECT id INTO v_cm_id FROM resources WHERE name = 'CM';
        SELECT id INTO v_el_id FROM resources WHERE name = 'EL';
        SELECT id INTO v_cs_id FROM resources WHERE name = 'CS';
        SELECT id INTO v_er_id FROM resources WHERE name = 'ER';

        SELECT COALESCE(wr.percentage, 0) INTO v_ucm_pct
        FROM resources r LEFT JOIN world_resources wr ON wr.world_id = p_world_id AND wr.resource_id = r.id
        WHERE r.name = 'U-CM';
        SELECT COALESCE(wr.percentage, 0) INTO v_uel_pct
        FROM resources r LEFT JOIN world_resources wr ON wr.world_id = p_world_id AND wr.resource_id = r.id
        WHERE r.name = 'U-EL';
        SELECT COALESCE(wr.percentage, 0) INTO v_ucs_pct
        FROM resources r LEFT JOIN world_resources wr ON wr.world_id = p_world_id AND wr.resource_id = r.id
        WHERE r.name = 'U-CS';

        v_cm_amt := FLOOR(4000 * p_hexes * v_ucm_pct / 100);
        v_el_amt := FLOOR(4000 * p_hexes * v_uel_pct / 100);
        v_cs_amt := FLOOR(4000 * p_hexes * v_ucs_pct / 100);
        v_er_amt := FLOOR(500000000 * p_hexes * ((v_ucm_pct + v_uel_pct + v_ucs_pct) / 3) / 100);

        IF v_cm_amt > 0 THEN
            INSERT INTO local_treasury (world_id, faction_id, resource_id, amount) VALUES (p_world_id, p_conqueror_faction_id, v_cm_id, v_cm_amt)
            ON CONFLICT (world_id, faction_id, resource_id) DO UPDATE SET amount = local_treasury.amount + v_cm_amt;
        END IF;
        IF v_el_amt > 0 THEN
            INSERT INTO local_treasury (world_id, faction_id, resource_id, amount) VALUES (p_world_id, p_conqueror_faction_id, v_el_id, v_el_amt)
            ON CONFLICT (world_id, faction_id, resource_id) DO UPDATE SET amount = local_treasury.amount + v_el_amt;
        END IF;
        IF v_cs_amt > 0 THEN
            INSERT INTO local_treasury (world_id, faction_id, resource_id, amount) VALUES (p_world_id, p_conqueror_faction_id, v_cs_id, v_cs_amt)
            ON CONFLICT (world_id, faction_id, resource_id) DO UPDATE SET amount = local_treasury.amount + v_cs_amt;
        END IF;
        IF v_er_amt > 0 THEN
            INSERT INTO faction_treasury (faction_id, resource_id, amount) VALUES (p_conqueror_faction_id, v_er_id, v_er_amt)
            ON CONFLICT (faction_id, resource_id) DO UPDATE SET amount = faction_treasury.amount + v_er_amt;
        END IF;

        SELECT id, per_hex_value, min_value, max_value INTO v_spirit_type_id, v_per_hex, v_min_value, v_max_value
        FROM spirit_types WHERE key = 'resilience';

        v_resilience := LEAST(GREATEST(p_hexes * v_per_hex, v_min_value), v_max_value);
        INSERT INTO national_spirits (faction_id, spirit_type_id, modifier_value, expires_at)
        VALUES (p_target_faction_id, v_spirit_type_id, v_resilience, now())
        ON CONFLICT (faction_id, spirit_type_id) DO UPDATE SET modifier_value = EXCLUDED.modifier_value, granted_at = now(), expires_at = now();
    END IF;

    RETURN QUERY SELECT v_pop_moved, v_cm_amt, v_el_amt, v_cs_amt, v_er_amt, v_influence_cost, v_resilience;
END;
$$;




CREATE OR REPLACE FUNCTION sp_vesta_trade(
    p_faction_id    INT,
    p_world_id      INT,        
    p_resource_name TEXT,       
    p_unrefined_in  BIGINT,     
    p_refined_out   BIGINT,     
    p_refined_name  TEXT        
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_unrefined_id  INT;
    v_refined_id    INT;
    v_have          BIGINT;
BEGIN
    SELECT id INTO v_unrefined_id FROM resources WHERE name = p_resource_name;
    SELECT id INTO v_refined_id   FROM resources WHERE name = p_refined_name;

    IF v_unrefined_id IS NULL THEN
        RAISE EXCEPTION 'RESOURCE_NOT_FOUND: Unknown resource %', p_resource_name;
    END IF;

    SELECT COALESCE(amount, 0) INTO v_have
    FROM local_treasury
    WHERE faction_id = p_faction_id AND world_id = p_world_id AND resource_id = v_unrefined_id;

    IF v_have < p_unrefined_in THEN
        RAISE EXCEPTION 'RESOURCE_INSUFFICIENT: Insufficient % at this world for Vesta trade', p_resource_name;
    END IF;

    UPDATE local_treasury
    SET amount = amount - p_unrefined_in
    WHERE faction_id = p_faction_id AND world_id = p_world_id AND resource_id = v_unrefined_id;

    
    INSERT INTO local_treasury (faction_id, world_id, resource_id, amount)
    VALUES (p_faction_id, p_world_id, v_refined_id, p_refined_out)
    ON CONFLICT (faction_id, world_id, resource_id)
    DO UPDATE SET amount = local_treasury.amount + p_refined_out;
END;
$$;


CREATE OR REPLACE FUNCTION sp_ceres_trade(
    p_faction_id        INT,
    p_world_id          INT,
    p_source_res_name   TEXT,
    p_source_amount     BIGINT,
    p_dest_res_name     TEXT,
    p_dest_amount       BIGINT
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_src_id    INT;
    v_dst_id    INT;
    v_current   BIGINT;
BEGIN
    SELECT id INTO v_src_id FROM resources WHERE name = p_source_res_name;
    SELECT id INTO v_dst_id FROM resources WHERE name = p_dest_res_name;

    SELECT COALESCE(amount, 0) INTO v_current
    FROM local_treasury
    WHERE faction_id = p_faction_id AND world_id = p_world_id AND resource_id = v_src_id;

    IF COALESCE(v_current, 0) < p_source_amount THEN
        RAISE EXCEPTION 'RESOURCE_INSUFFICIENT: Insufficient % — need %, have %',
            p_source_res_name, p_source_amount, COALESCE(v_current, 0);
    END IF;

    UPDATE local_treasury
    SET amount = amount - p_source_amount
    WHERE faction_id = p_faction_id AND world_id = p_world_id AND resource_id = v_src_id;

    INSERT INTO local_treasury (faction_id, world_id, resource_id, amount)
    VALUES (p_faction_id, p_world_id, v_dst_id, p_dest_amount)
    ON CONFLICT (faction_id, world_id, resource_id)
    DO UPDATE SET amount = local_treasury.amount + p_dest_amount;
END;
$$;






CREATE OR REPLACE FUNCTION sp_create_fleet(
    p_faction_id    INT,
    p_name          TEXT,
    p_world_id      INT
) RETURNS TABLE(id INT, faction_fleet_number INT, status_id INT) LANGUAGE plpgsql AS $$
DECLARE
    v_idle_id       INT;
    v_next_num      INT;
    v_fleet_id      INT;
    v_status_id     INT;
BEGIN
    SELECT fs.id INTO v_idle_id FROM fleet_status fs WHERE LOWER(fs.name) = 'idle';
    IF v_idle_id IS NULL THEN
        RAISE EXCEPTION 'FLEET_STATUS_NOT_FOUND: Idle status not found in fleet_status';
    END IF;

    PERFORM pg_advisory_xact_lock(811002, p_faction_id);

    SELECT COALESCE(MIN(t.n), 1)
    INTO v_next_num
    FROM generate_series(
        1,
        (SELECT COALESCE(MAX(f.faction_fleet_number), 0) + 1 FROM fleets f WHERE f.faction_id = p_faction_id)
    ) AS t(n)
    WHERE NOT EXISTS (
        SELECT 1 FROM fleets f
        WHERE f.faction_id = p_faction_id AND f.faction_fleet_number = t.n
    );

    INSERT INTO fleets (faction_id, name, position, status_id, health, total_cs, faction_fleet_number)
    VALUES (p_faction_id, p_name, p_world_id, v_idle_id, 100, 0, v_next_num)
    RETURNING fleets.id, fleets.faction_fleet_number, fleets.status_id
    INTO v_fleet_id, v_next_num, v_status_id;

    RETURN QUERY SELECT v_fleet_id, v_next_num, v_status_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_set_fleet_status(
    p_fleet_id      INT,
    p_status_name   TEXT
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_status_id     INT;
    v_current_name  TEXT;
BEGIN
    SELECT fs.id INTO v_status_id FROM fleet_status fs WHERE LOWER(fs.name) = LOWER(p_status_name);
    IF v_status_id IS NULL THEN
        RAISE EXCEPTION 'FLEET_STATUS_NOT_FOUND: Status % not found', p_status_name;
    END IF;

    SELECT fs.name INTO v_current_name
    FROM fleets f
    JOIN fleet_status fs ON f.status_id = fs.id
    WHERE f.id = p_fleet_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'FLEET_NOT_FOUND: Fleet #% does not exist', p_fleet_id;
    END IF;

    IF LOWER(v_current_name) = 'mothballed' AND LOWER(p_status_name) != 'idle' THEN
        RAISE EXCEPTION 'FLEET_INVALID_STATUS: Mothballed fleet must be reactivated to Idle first';
    END IF;

    UPDATE fleets SET status_id = v_status_id WHERE id = p_fleet_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_move_fleet(
    p_fleet_id      INT,
    p_destination   INT,
    p_moved_since   TIMESTAMPTZ
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_travelling_id INT;
    v_idle_id       INT;
    v_current_name  TEXT;
BEGIN
    SELECT fs.id INTO v_travelling_id FROM fleet_status fs WHERE LOWER(fs.name) = 'travelling';
    SELECT fs.id INTO v_idle_id       FROM fleet_status fs WHERE LOWER(fs.name) = 'idle';

    SELECT fs.name INTO v_current_name
    FROM fleets f JOIN fleet_status fs ON f.status_id = fs.id
    WHERE f.id = p_fleet_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'FLEET_NOT_FOUND: Fleet #% does not exist', p_fleet_id;
    END IF;

    IF LOWER(v_current_name) NOT IN ('idle', 'defence', 'defence', 'patrol', 'blockading', 'ftl supply') THEN
        RAISE EXCEPTION 'FLEET_INVALID_STATUS: Fleet cannot move while status is %', v_current_name;
    END IF;

    DELETE FROM blockade_fleets WHERE fleet_id = p_fleet_id;

    
    DELETE FROM blockade_targets
    WHERE blockade_id IN (
        SELECT b.id FROM blockades b
        WHERE NOT EXISTS (SELECT 1 FROM blockade_fleets bf WHERE bf.blockade_id = b.id)
    );
    DELETE FROM blockades
    WHERE NOT EXISTS (SELECT 1 FROM blockade_fleets bf WHERE bf.blockade_id = blockades.id);

    UPDATE fleets
    SET status_id = v_travelling_id, moving_to = p_destination, moving_since = p_moved_since
    WHERE id = p_fleet_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_add_vehicle_to_fleet(
    p_fleet_id      INT,
    p_vehicle_id    INT,
    p_amount        INT
) RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO fleet_vehicles (fleet_id, vehicle_id, amount)
    VALUES (p_fleet_id, p_vehicle_id, p_amount)
    ON CONFLICT (fleet_id, vehicle_id)
    DO UPDATE SET amount = fleet_vehicles.amount + p_amount;

    UPDATE fleets
    SET total_cs = (
        SELECT COALESCE(SUM(fv.amount * vc.amount), 0)
        FROM fleet_vehicles fv
        JOIN vehicle_costs vc ON fv.vehicle_id = vc.vehicle_id
        JOIN resources r ON vc.resource_id = r.id AND r.name = 'CS'
        WHERE fv.fleet_id = p_fleet_id
    )
    WHERE id = p_fleet_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_remove_vehicle_from_fleet(
    p_fleet_id      INT,
    p_vehicle_id    INT,
    p_amount        INT
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_current INT;
BEGIN
    SELECT amount INTO v_current
    FROM fleet_vehicles
    WHERE fleet_id = p_fleet_id AND vehicle_id = p_vehicle_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'FLEET_VEHICLE_NOT_FOUND: Vehicle #% not in fleet #%', p_vehicle_id, p_fleet_id;
    END IF;

    IF v_current < p_amount THEN
        RAISE EXCEPTION 'FLEET_VEHICLE_INSUFFICIENT: Fleet has % of vehicle #%, need %',
            v_current, p_vehicle_id, p_amount;
    END IF;

    IF v_current = p_amount THEN
        DELETE FROM fleet_vehicles WHERE fleet_id = p_fleet_id AND vehicle_id = p_vehicle_id;
    ELSE
        UPDATE fleet_vehicles SET amount = amount - p_amount
        WHERE fleet_id = p_fleet_id AND vehicle_id = p_vehicle_id;
    END IF;

    UPDATE fleets
    SET total_cs = (
        SELECT COALESCE(SUM(fv.amount * vc.amount), 0)
        FROM fleet_vehicles fv
        JOIN vehicle_costs vc ON fv.vehicle_id = vc.vehicle_id
        JOIN resources r ON vc.resource_id = r.id AND r.name = 'CS'
        WHERE fv.fleet_id = p_fleet_id
    )
    WHERE id = p_fleet_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_complete_construction(
    p_order_id INT
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_order RECORD;
    v_deleted TEXT;
BEGIN
    SELECT * INTO v_order FROM vehicle_construction WHERE id = p_order_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'CONSTRUCTION_NOT_FOUND: Order #% does not exist', p_order_id;
    END IF;

    PERFORM sp_add_vehicle_to_fleet(v_order.fleet_id, v_order.vehicle_id, v_order.quantity);

    DELETE FROM vehicle_construction WHERE id = p_order_id
    RETURNING id::TEXT INTO v_deleted;

    IF v_deleted IS NULL THEN
        RAISE EXCEPTION 'CONSTRUCTION_CONCURRENT: Order #% was already processed', p_order_id;
    END IF;
END;
$$;


CREATE OR REPLACE FUNCTION sp_refund_vehicle(
    p_fleet_id          INT,
    p_vehicle_id        INT,
    p_amount            INT,
    p_refund_faction_id INT,
    p_refund_pct        NUMERIC    
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_cost      RECORD;
    v_refund    BIGINT;
    v_world_id  INT;
BEGIN
    SELECT position INTO v_world_id FROM fleets WHERE id = p_fleet_id;

    PERFORM sp_remove_vehicle_from_fleet(p_fleet_id, p_vehicle_id, p_amount);

    FOR v_cost IN
        SELECT r.name as resource_name, vc.amount as unit_cost
        FROM vehicle_costs vc
        JOIN resources r ON vc.resource_id = r.id
        WHERE vc.vehicle_id = p_vehicle_id
    LOOP
        v_refund := FLOOR(v_cost.unit_cost * p_amount * p_refund_pct);
        IF v_refund > 0 THEN
            PERFORM sp_add_resources(
                p_refund_faction_id,
                v_world_id,
                jsonb_build_array(jsonb_build_object('name', v_cost.resource_name, 'amount', v_refund))
            );
        END IF;
    END LOOP;
END;
$$;


CREATE OR REPLACE FUNCTION sp_salvage_fleet(
    p_salvager_faction_id   INT,
    p_debris_fleet_id       INT
) RETURNS JSONB LANGUAGE plpgsql AS $$
DECLARE
    v_status        TEXT;
    v_world_id      INT;
    v_salvager_id   INT;
    v_costs         JSONB := '{}';
    v_cost_row      RECORD;
BEGIN
    SELECT fs.name, f.position INTO v_status, v_world_id
    FROM fleets f
    JOIN fleet_status fs ON f.status_id = fs.id
    WHERE f.id = p_debris_fleet_id;

    IF v_status IS NULL THEN
        RAISE EXCEPTION 'FLEET_NOT_FOUND: Fleet % not found', p_debris_fleet_id;
    END IF;
    IF lower(v_status) != 'debris' THEN
        RAISE EXCEPTION 'NOT_DEBRIS: Fleet % is not debris (status: %)', p_debris_fleet_id, v_status;
    END IF;

    SELECT f.id INTO v_salvager_id
    FROM fleets f
    JOIN fleet_status fs ON f.status_id = fs.id
    WHERE f.faction_id = p_salvager_faction_id
      AND f.position = v_world_id
      AND lower(fs.name) NOT IN ('debris', 'mothballed')
    LIMIT 1;

    IF v_salvager_id IS NULL THEN
        RAISE EXCEPTION 'NO_SALVAGER: No active fleet at debris location';
    END IF;

    FOR v_cost_row IN
        SELECT r.name, SUM(vc.amount * fv.amount) AS total
        FROM fleet_vehicles fv
        JOIN vehicle_costs vc ON fv.vehicle_id = vc.vehicle_id
        JOIN resources r ON vc.resource_id = r.id
        WHERE fv.fleet_id = p_debris_fleet_id
        GROUP BY r.name
    LOOP
        v_costs := v_costs || jsonb_build_object(v_cost_row.name, v_cost_row.total);
    END LOOP;

    DELETE FROM fleet_vehicles WHERE fleet_id = p_debris_fleet_id;
    UPDATE fleets
    SET health = 100, total_cs = 0,
        status_id = (SELECT id FROM fleet_status WHERE lower(name) = 'idle')
    WHERE id = p_debris_fleet_id;

    RETURN jsonb_build_object('world_id', v_world_id, 'costs', v_costs);
END;
$$;






CREATE OR REPLACE FUNCTION sp_delete_world(
    p_world_id INT
) RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM worlds WHERE orbit_of = p_world_id) THEN
        RAISE EXCEPTION 'MAP_HAS_CHILDREN: World #% has child bodies — remove them first', p_world_id;
    END IF;

    
    DELETE FROM fleet_vehicles WHERE fleet_id IN (SELECT id FROM fleets WHERE position = p_world_id);
    DELETE FROM fleets WHERE position = p_world_id;

    
    DELETE FROM worlds WHERE id = p_world_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_claim_hex(
    p_faction_id    INT,
    p_world_id      INT,
    p_hexes         INT,
    p_influence_cost BIGINT
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_influence_id  INT;
    v_current_inf   BIGINT;
    v_max_hexes     INT;
    v_claimed       BIGINT;
BEGIN
    SELECT id INTO v_influence_id FROM resources WHERE name = 'Influence';

    SELECT COALESCE(amount, 0) INTO v_current_inf
    FROM faction_treasury
    WHERE faction_id = p_faction_id AND resource_id = v_influence_id;

    IF COALESCE(v_current_inf, 0) < p_influence_cost THEN
        RAISE EXCEPTION 'RESOURCE_INSUFFICIENT: Insufficient Influence — need %, have %',
            p_influence_cost, COALESCE(v_current_inf, 0);
    END IF;

    SELECT hex_count INTO v_max_hexes FROM worlds WHERE id = p_world_id;
    SELECT COALESCE(SUM(territory), 0) INTO v_claimed FROM world_factions WHERE world_id = p_world_id;

    IF v_claimed + p_hexes > v_max_hexes THEN
        RAISE EXCEPTION 'MAP_INSUFFICIENT_HEXES: Only % hex(es) available on this world',
            v_max_hexes - v_claimed;
    END IF;

    UPDATE faction_treasury
    SET amount = amount - p_influence_cost
    WHERE faction_id = p_faction_id AND resource_id = v_influence_id;

    INSERT INTO world_factions (world_id, faction_id, territory)
    VALUES (p_world_id, p_faction_id, p_hexes)
    ON CONFLICT (world_id, faction_id)
    DO UPDATE SET territory = world_factions.territory + p_hexes;
END;
$$;


CREATE OR REPLACE FUNCTION sp_unclaim_hex(
    p_faction_id    INT,
    p_world_id      INT,
    p_hexes         INT
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_current   INT;
    v_buildings INT;
BEGIN
    SELECT territory INTO v_current
    FROM world_factions WHERE world_id = p_world_id AND faction_id = p_faction_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'MAP_NO_TERRITORY: Faction has no hexes on this world';
    END IF;

    IF v_current < p_hexes THEN
        RAISE EXCEPTION 'MAP_INSUFFICIENT_HEXES: Cannot unclaim % — only have %', p_hexes, v_current;
    END IF;

    SELECT COALESCE(SUM(amount), 0) INTO v_buildings
    FROM faction_world_buildings
    WHERE faction_id = p_faction_id AND world_id = p_world_id;

    IF (v_current - p_hexes) < v_buildings THEN
        RAISE EXCEPTION 'MAP_BUILDINGS_BLOCK: Need at least % hexes for % building(s)',
            v_buildings, v_buildings;
    END IF;

    IF v_current = p_hexes THEN
        DELETE FROM world_factions WHERE world_id = p_world_id AND faction_id = p_faction_id;
    ELSE
        UPDATE world_factions SET territory = territory - p_hexes
        WHERE world_id = p_world_id AND faction_id = p_faction_id;
    END IF;
END;
$$;






CREATE OR REPLACE FUNCTION sp_merge_factions(
    p_source_id INT,
    p_target_id INT
) RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    IF p_source_id = p_target_id THEN
        RAISE EXCEPTION 'FACTION_INVALID: Cannot merge a faction with itself';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM factions WHERE id = p_source_id) THEN
        RAISE EXCEPTION 'FACTION_NOT_FOUND: Source faction #% does not exist', p_source_id;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM factions WHERE id = p_target_id) THEN
        RAISE EXCEPTION 'FACTION_NOT_FOUND: Target faction #% does not exist', p_target_id;
    END IF;

    
    INSERT INTO world_factions (world_id, faction_id, territory)
    SELECT world_id, p_target_id, territory
    FROM world_factions WHERE faction_id = p_source_id
    ON CONFLICT (world_id, faction_id)
    DO UPDATE SET territory = world_factions.territory + EXCLUDED.territory;

    DELETE FROM world_factions WHERE faction_id = p_source_id;

    DELETE FROM factions WHERE id = p_source_id;
END;
$$;






CREATE OR REPLACE FUNCTION sp_join_pact(
    p_faction_id    INT,
    p_pact_id       INT
) RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pacts WHERE id = p_pact_id) THEN
        RAISE EXCEPTION 'PACT_NOT_FOUND: Pact #% does not exist', p_pact_id;
    END IF;

    IF EXISTS (SELECT 1 FROM pact_members WHERE pact_id = p_pact_id AND faction_id = p_faction_id) THEN
        RAISE EXCEPTION 'PACT_ALREADY_MEMBER: Faction is already a member of pact #%', p_pact_id;
    END IF;

    INSERT INTO pact_members (pact_id, faction_id) VALUES (p_pact_id, p_faction_id);
END;
$$;


CREATE OR REPLACE FUNCTION sp_leave_pact(
    p_faction_id    INT,
    p_pact_id       INT
) RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pact_members WHERE pact_id = p_pact_id AND faction_id = p_faction_id) THEN
        RAISE EXCEPTION 'PACT_NOT_MEMBER: Faction is not a member of pact #%', p_pact_id;
    END IF;

    IF EXISTS (SELECT 1 FROM pacts WHERE id = p_pact_id AND leader_id = p_faction_id) THEN
        RAISE EXCEPTION 'PACT_LEADER_CANNOT_LEAVE: Pact leader cannot leave — dissolve the pact instead';
    END IF;

    DELETE FROM pact_members WHERE pact_id = p_pact_id AND faction_id = p_faction_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_remove_pact_member(
    p_leader_faction_id INT,
    p_target_faction_id INT,
    p_pact_id           INT
) RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pacts WHERE id = p_pact_id AND leader_id = p_leader_faction_id) THEN
        RAISE EXCEPTION 'PACT_NOT_LEADER: Only the pact leader can remove members';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pact_members WHERE pact_id = p_pact_id AND faction_id = p_target_faction_id) THEN
        RAISE EXCEPTION 'PACT_NOT_MEMBER: Target faction is not a member of pact #%', p_pact_id;
    END IF;

    DELETE FROM pact_members WHERE pact_id = p_pact_id AND faction_id = p_target_faction_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_create_pact(
    p_faction_id    INT,
    p_name          TEXT,
    p_type_name     TEXT
) RETURNS INT LANGUAGE plpgsql AS $$
DECLARE
    v_type_id   INT;
    v_pact_id   INT;
BEGIN
    SELECT id INTO v_type_id FROM pact_types WHERE name = p_type_name;
    IF v_type_id IS NULL THEN
        INSERT INTO pact_types (name) VALUES (p_type_name) RETURNING id INTO v_type_id;
    END IF;

    INSERT INTO pacts (name, pact_type_id, leader_id)
    VALUES (p_name, v_type_id, p_faction_id)
    RETURNING id INTO v_pact_id;

    INSERT INTO pact_members (pact_id, faction_id) VALUES (v_pact_id, p_faction_id);

    RETURN v_pact_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_dissolve_pact(
    p_faction_id    INT,
    p_pact_id       INT
) RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pacts WHERE id = p_pact_id AND leader_id = p_faction_id) THEN
        RAISE EXCEPTION 'PACT_NOT_LEADER: Only the pact leader can dissolve pact #%', p_pact_id;
    END IF;

    DELETE FROM pact_members WHERE pact_id = p_pact_id;
    DELETE FROM pacts WHERE id = p_pact_id;
END;
$$;






CREATE OR REPLACE FUNCTION sp_create_war(
    p_name          TEXT,
    p_faction_id    INT,
    p_side          TEXT
) RETURNS INT LANGUAGE plpgsql AS $$
DECLARE
    v_war_id INT;
BEGIN
    INSERT INTO wars (name, date_start) VALUES (p_name, CURRENT_TIMESTAMP) RETURNING id INTO v_war_id;
    INSERT INTO war_participants (war_id, faction_id, side) VALUES (v_war_id, p_faction_id, p_side);
    RETURN v_war_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_end_war(
    p_war_id        INT,
    p_faction_id    INT
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_idle_id INT;
    v_fleet   RECORD;
    v_battle  RECORD;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM wars WHERE id = p_war_id) THEN
        RAISE EXCEPTION 'WAR_NOT_FOUND: War #% does not exist', p_war_id;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM war_participants WHERE war_id = p_war_id AND faction_id = p_faction_id) THEN
        RAISE EXCEPTION 'WAR_NOT_PARTICIPANT: Your faction is not a participant in war #%', p_war_id;
    END IF;

    SELECT id INTO v_idle_id FROM fleet_status WHERE LOWER(name) = 'idle';

    FOR v_battle IN SELECT id FROM battles WHERE war_id = p_war_id
    LOOP
        FOR v_fleet IN
            SELECT f.id FROM fleets f
            JOIN battle_participants bp ON f.id = bp.fleet_id
            WHERE bp.battle_id = v_battle.id
        LOOP
            UPDATE fleets SET status_id = v_idle_id, fighting_fleet_id = NULL WHERE id = v_fleet.id;
        END LOOP;
        DELETE FROM battle_participants WHERE battle_id = v_battle.id;
    END LOOP;

    DELETE FROM battles WHERE war_id = p_war_id;
    DELETE FROM war_participants WHERE war_id = p_war_id;
    DELETE FROM wars WHERE id = p_war_id;
END;
$$;






CREATE OR REPLACE FUNCTION sp_start_battle(
    p_war_id        INT,
    p_fleet_id      INT,
    p_side          TEXT,
    p_world_id      INT
) RETURNS INT LANGUAGE plpgsql AS $$
DECLARE
    v_battle_id     INT;
    v_combat_id     INT;
BEGIN
    SELECT id INTO v_combat_id FROM fleet_status WHERE LOWER(name) = 'in combat';

    INSERT INTO battles (war_id, world_id, date_start)
    VALUES (p_war_id, p_world_id, CURRENT_TIMESTAMP)
    RETURNING id INTO v_battle_id;

    INSERT INTO battle_participants (battle_id, fleet_id, side) VALUES (v_battle_id, p_fleet_id, p_side);

    UPDATE fleets SET status_id = v_combat_id, fighting_fleet_id = NULL WHERE id = p_fleet_id;

    RETURN v_battle_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_end_battle(
    p_battle_id     INT,
    p_faction_id    INT
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_idle_id   INT;
    v_fleet     RECORD;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM battles WHERE id = p_battle_id) THEN
        RAISE EXCEPTION 'BATTLE_NOT_FOUND: Battle #% does not exist', p_battle_id;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM battle_participants bp
        JOIN fleets f ON bp.fleet_id = f.id
        WHERE bp.battle_id = p_battle_id AND f.faction_id = p_faction_id
    ) THEN
        RAISE EXCEPTION 'BATTLE_NOT_PARTICIPANT: Your faction has no fleet in battle #%', p_battle_id;
    END IF;

    SELECT id INTO v_idle_id FROM fleet_status WHERE LOWER(name) = 'idle';

    FOR v_fleet IN SELECT fleet_id FROM battle_participants WHERE battle_id = p_battle_id
    LOOP
        UPDATE fleets SET status_id = v_idle_id, fighting_fleet_id = NULL WHERE id = v_fleet.fleet_id;
    END LOOP;

    DELETE FROM battle_participants WHERE battle_id = p_battle_id;
    DELETE FROM battles WHERE id = p_battle_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_damage_fleet(
    p_fleet_id  INT,
    p_damage    INT
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_current_health    INT;
    v_new_health        INT;
    v_debris_id         INT;
BEGIN
    SELECT health INTO v_current_health FROM fleets WHERE id = p_fleet_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'FLEET_NOT_FOUND: Fleet #% does not exist', p_fleet_id;
    END IF;

    v_new_health := GREATEST(0, v_current_health - p_damage);
    UPDATE fleets SET health = v_new_health WHERE id = p_fleet_id;

    IF v_new_health = 0 THEN
        SELECT id INTO v_debris_id FROM fleet_status WHERE LOWER(name) = 'debris';
        UPDATE fleets SET status_id = v_debris_id WHERE id = p_fleet_id;
    END IF;
END;
$$;


CREATE OR REPLACE FUNCTION sp_repair_fleet(
    p_fleet_id      INT,
    p_faction_id    INT,
    p_repair_amount INT,
    p_costs         JSONB      
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_current_health    INT;
    v_new_health        INT;
    v_idle_id           INT;
    v_status_name       TEXT;
BEGIN
    SELECT f.health, fs.name INTO v_current_health, v_status_name
    FROM fleets f JOIN fleet_status fs ON f.status_id = fs.id
    WHERE f.id = p_fleet_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'FLEET_NOT_FOUND: Fleet #% does not exist', p_fleet_id;
    END IF;

    IF v_current_health >= 100 THEN
        RAISE EXCEPTION 'FLEET_FULL_HEALTH: Fleet is already at full health';
    END IF;

    v_new_health := LEAST(100, v_current_health + p_repair_amount);

    IF p_costs IS NOT NULL THEN
        PERFORM sp_deduct_resources(p_faction_id, NULL, p_costs);
    END IF;

    UPDATE fleets SET health = v_new_health WHERE id = p_fleet_id;

    IF LOWER(v_status_name) = 'debris' AND v_new_health > 0 THEN
        SELECT id INTO v_idle_id FROM fleet_status WHERE LOWER(name) = 'idle';
        UPDATE fleets SET status_id = v_idle_id WHERE id = p_fleet_id;
    END IF;
END;
$$;






CREATE OR REPLACE FUNCTION sp_start_blockade(
    p_fleet_id          INT,
    p_world_id          INT,
    p_target_faction_ids INT[]
) RETURNS INT LANGUAGE plpgsql AS $$
DECLARE
    v_blockade_id   INT;
    v_existing_id   INT;
    v_blockading_id INT;
    v_tid           INT;
BEGIN
    SELECT id INTO v_blockading_id FROM fleet_status WHERE LOWER(name) = 'blockading';

    SELECT b.id INTO v_existing_id
    FROM blockades b
    JOIN blockade_targets bt ON b.id = bt.blockade_id
    WHERE b.world_id = p_world_id AND bt.faction_id = ANY(p_target_faction_ids)
    LIMIT 1;

    IF v_existing_id IS NOT NULL THEN
        v_blockade_id := v_existing_id;
    ELSE
        INSERT INTO blockades (world_id, date_start) VALUES (p_world_id, CURRENT_TIMESTAMP)
        RETURNING id INTO v_blockade_id;

        FOREACH v_tid IN ARRAY p_target_faction_ids
        LOOP
            INSERT INTO blockade_targets (blockade_id, faction_id) VALUES (v_blockade_id, v_tid);
        END LOOP;
    END IF;

    INSERT INTO blockade_fleets (blockade_id, fleet_id) VALUES (v_blockade_id, p_fleet_id)
    ON CONFLICT DO NOTHING;

    UPDATE fleets SET status_id = v_blockading_id WHERE id = p_fleet_id;

    RETURN v_blockade_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_end_blockade(
    p_blockade_id   INT,
    p_fleet_id      INT    
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_idle_id       INT;
    v_fleet         RECORD;
    v_remaining     INT;
BEGIN
    SELECT id INTO v_idle_id FROM fleet_status WHERE LOWER(name) = 'idle';

    IF p_fleet_id IS NOT NULL THEN
        UPDATE fleets SET status_id = v_idle_id WHERE id = p_fleet_id;
        DELETE FROM blockade_fleets WHERE blockade_id = p_blockade_id AND fleet_id = p_fleet_id;

        SELECT COUNT(*) INTO v_remaining FROM blockade_fleets WHERE blockade_id = p_blockade_id;
        IF v_remaining > 0 THEN
            RETURN;
        END IF;
    ELSE
        FOR v_fleet IN SELECT fleet_id FROM blockade_fleets WHERE blockade_id = p_blockade_id
        LOOP
            UPDATE fleets SET status_id = v_idle_id WHERE id = v_fleet.fleet_id;
        END LOOP;
        DELETE FROM blockade_fleets WHERE blockade_id = p_blockade_id;
    END IF;

    DELETE FROM blockade_targets WHERE blockade_id = p_blockade_id;
    DELETE FROM blockades WHERE id = p_blockade_id;
END;
$$;






CREATE OR REPLACE FUNCTION sp_recruit_military(
    p_faction_id    INT,
    p_amount        INT,
    p_role_name     TEXT,
    p_costs         JSONB,      
    p_completion    TIMESTAMPTZ
) RETURNS INT LANGUAGE plpgsql AS $$
DECLARE
    v_key           TEXT;
    v_per_unit      BIGINT;
    v_total         BIGINT;
    v_res_id        INT;
    v_pop_id        INT;
    v_available     BIGINT;
    v_rec_id        INT;
BEGIN
    SELECT id INTO v_pop_id FROM resources WHERE name = 'Population';

    
    SELECT COALESCE(SUM(amount), 0) INTO v_available
    FROM local_treasury WHERE faction_id = p_faction_id AND resource_id = v_pop_id;

    IF v_available < p_amount THEN
        RAISE EXCEPTION 'RESOURCE_INSUFFICIENT: Insufficient Population — need %, have %', p_amount, v_available;
    END IF;

    UPDATE local_treasury lt
    SET amount = lt.amount - FLOOR(
        (lt.amount::FLOAT / v_available) * p_amount
    )
    WHERE lt.faction_id = p_faction_id AND lt.resource_id = v_pop_id AND lt.amount > 0;

    
    FOR v_key, v_per_unit IN SELECT key, (value::TEXT)::BIGINT FROM jsonb_each(p_costs)
    LOOP
        SELECT id INTO v_res_id FROM resources WHERE name = v_key;
        IF v_res_id IS NULL THEN
            RAISE EXCEPTION 'RESOURCE_NOT_FOUND: Unknown resource %', v_key;
        END IF;

        v_total := v_per_unit * p_amount;

        IF v_key IN ('CM','EL','CS','U-CM','U-EL','U-CS') THEN
            SELECT COALESCE(SUM(amount), 0) INTO v_available
            FROM local_treasury WHERE faction_id = p_faction_id AND resource_id = v_res_id;

            IF v_available < v_total THEN
                RAISE EXCEPTION 'RESOURCE_INSUFFICIENT: Insufficient % — need %, have %', v_key, v_total, v_available;
            END IF;

            UPDATE local_treasury lt
            SET amount = lt.amount - FLOOR((lt.amount::FLOAT / v_available) * v_total)
            WHERE lt.faction_id = p_faction_id AND lt.resource_id = v_res_id AND lt.amount > 0;
        ELSE
            SELECT COALESCE(amount, 0) INTO v_available
            FROM faction_treasury WHERE faction_id = p_faction_id AND resource_id = v_res_id;

            IF v_available < v_total THEN
                RAISE EXCEPTION 'RESOURCE_INSUFFICIENT: Insufficient % — need %, have %', v_key, v_total, v_available;
            END IF;

            UPDATE faction_treasury SET amount = amount - v_total
            WHERE faction_id = p_faction_id AND resource_id = v_res_id;
        END IF;
    END LOOP;

    INSERT INTO military_recruitment (faction_id, amount, role_name, start_time, completion_time, status)
    VALUES (p_faction_id, p_amount, p_role_name, CURRENT_TIMESTAMP, p_completion, 'training')
    RETURNING id INTO v_rec_id;

    RETURN v_rec_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_dismiss_military(
    p_faction_id    INT,
    p_amount        INT
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_mil_id        INT;
    v_pop_id        INT;
    v_current_mil   BIGINT;
    v_total_pop     BIGINT;
BEGIN
    SELECT id INTO v_mil_id FROM resources WHERE name = 'Military';
    SELECT id INTO v_pop_id FROM resources WHERE name = 'Population';

    SELECT COALESCE(amount, 0) INTO v_current_mil
    FROM faction_treasury WHERE faction_id = p_faction_id AND resource_id = v_mil_id;

    IF v_current_mil < p_amount THEN
        RAISE EXCEPTION 'INSUFFICIENT_MILITARY: Have % military, trying to dismiss %', v_current_mil, p_amount;
    END IF;

    UPDATE faction_treasury SET amount = amount - p_amount
    WHERE faction_id = p_faction_id AND resource_id = v_mil_id;

    
    SELECT COALESCE(SUM(amount), 0) INTO v_total_pop
    FROM local_treasury WHERE faction_id = p_faction_id AND resource_id = v_pop_id;

    IF v_total_pop > 0 THEN
        UPDATE local_treasury lt
        SET amount = lt.amount + FLOOR((lt.amount::FLOAT / v_total_pop) * p_amount)
        WHERE lt.faction_id = p_faction_id AND lt.resource_id = v_pop_id AND lt.amount > 0;
    ELSE
        
        INSERT INTO local_treasury (faction_id, world_id, resource_id, amount)
        SELECT p_faction_id, wf.world_id, v_pop_id,
               FLOOR((wf.territory::FLOAT / NULLIF(SUM(wf.territory) OVER (), 0)) * p_amount)
        FROM world_factions wf
        WHERE wf.faction_id = p_faction_id AND wf.territory > 0
        ON CONFLICT (faction_id, world_id, resource_id)
        DO UPDATE SET amount = local_treasury.amount + EXCLUDED.amount;
    END IF;
END;
$$;


CREATE OR REPLACE FUNCTION sp_complete_recruitment(
    p_recruitment_id INT
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_rec       RECORD;
    v_mil_id    INT;
BEGIN
    SELECT * INTO v_rec FROM military_recruitment WHERE id = p_recruitment_id AND status = 'training';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'RECRUITMENT_NOT_FOUND: Recruitment #% not found or not training', p_recruitment_id;
    END IF;

    SELECT id INTO v_mil_id FROM resources WHERE name = 'Military';

    INSERT INTO faction_treasury (faction_id, resource_id, amount)
    VALUES (v_rec.faction_id, v_mil_id, v_rec.amount)
    ON CONFLICT (faction_id, resource_id)
    DO UPDATE SET amount = faction_treasury.amount + v_rec.amount;

    DELETE FROM military_recruitment WHERE id = p_recruitment_id;
END;
$$;






CREATE OR REPLACE FUNCTION sp_apply_income_cycle(
    p_faction_id            INT,
    p_er_delta              BIGINT,
    p_influence_delta       BIGINT,
    p_local_deltas          JSONB,   
    p_population_deltas     JSONB,   
    p_transfers             JSONB    
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_er_id         INT;
    v_inf_id        INT;
    v_pop_id        INT;
    v_item          JSONB;
    v_world_id      INT;
    v_res_id        INT;
    v_amount        BIGINT;
    v_capacity      BIGINT;
    v_storable      BOOLEAN;
    v_transfer_id   INT;
    v_escort_id     INT;
    v_from_world    INT;
    v_to_world      INT;
    v_start_time    TIMESTAMPTZ;
    v_escort_ok     BOOLEAN;
BEGIN
    SELECT id INTO v_er_id  FROM resources WHERE name = 'ER';
    SELECT id INTO v_inf_id FROM resources WHERE name = 'Influence';
    SELECT id INTO v_pop_id FROM resources WHERE name = 'Population';

    
    IF p_er_delta != 0 THEN
        INSERT INTO faction_treasury (faction_id, resource_id, amount)
        VALUES (p_faction_id, v_er_id, p_er_delta)
        ON CONFLICT (faction_id, resource_id)
        DO UPDATE SET amount = faction_treasury.amount + p_er_delta;
    END IF;

    
    IF p_influence_delta != 0 THEN
        INSERT INTO faction_treasury (faction_id, resource_id, amount)
        VALUES (p_faction_id, v_inf_id, LEAST(10000, GREATEST(0, p_influence_delta)))
        ON CONFLICT (faction_id, resource_id)
        DO UPDATE SET amount = CASE
            WHEN p_influence_delta < 0 THEN GREATEST(0, faction_treasury.amount + p_influence_delta)
            ELSE GREATEST(faction_treasury.amount, LEAST(10000, faction_treasury.amount + p_influence_delta))
        END;
    END IF;

    
    FOR v_item IN SELECT * FROM jsonb_array_elements(p_local_deltas)
    LOOP
        v_world_id := (v_item->>'world_id')::INT;
        v_res_id   := (v_item->>'resource_id')::INT;
        v_amount   := (v_item->>'amount')::BIGINT;
        v_capacity := (v_item->>'capacity')::BIGINT;
        v_storable := (v_item->>'storable')::BOOLEAN;

        IF v_storable THEN
            INSERT INTO local_treasury (faction_id, world_id, resource_id, amount)
            VALUES (p_faction_id, v_world_id, v_res_id,
                    GREATEST(0::BIGINT, LEAST(0::BIGINT + v_amount, v_capacity)))
            ON CONFLICT (faction_id, world_id, resource_id)
            DO UPDATE SET amount = GREATEST(0::BIGINT,
                LEAST(local_treasury.amount + v_amount, v_capacity));
        ELSE
            INSERT INTO local_treasury (faction_id, world_id, resource_id, amount)
            VALUES (p_faction_id, v_world_id, v_res_id, GREATEST(0::BIGINT, v_amount))
            ON CONFLICT (faction_id, world_id, resource_id)
            DO UPDATE SET amount = GREATEST(0::BIGINT, local_treasury.amount + v_amount);
        END IF;
    END LOOP;

    
    FOR v_item IN SELECT * FROM jsonb_array_elements(p_population_deltas)
    LOOP
        v_world_id := (v_item->>'world_id')::INT;
        v_amount   := (v_item->>'amount')::BIGINT;
        v_capacity := COALESCE((v_item->>'pop_cap')::BIGINT, 0);
        IF v_amount != 0 THEN
            IF v_capacity > 0 THEN
                UPDATE local_treasury lt
                SET amount = LEAST(GREATEST(0::BIGINT, amount + v_amount), v_capacity)
                FROM resources r
                WHERE lt.faction_id = p_faction_id AND lt.world_id = v_world_id
                  AND lt.resource_id = r.id AND r.name = 'Population';
            ELSE
                UPDATE local_treasury lt
                SET amount = GREATEST(0::BIGINT, amount + v_amount)
                FROM resources r
                WHERE lt.faction_id = p_faction_id AND lt.world_id = v_world_id
                  AND lt.resource_id = r.id AND r.name = 'Population';
            END IF;
        END IF;
    END LOOP;

    
    FOR v_item IN SELECT * FROM jsonb_array_elements(p_transfers)
    LOOP
        v_from_world := (v_item->>'from_world_id')::INT;
        v_to_world   := (v_item->>'to_world_id')::INT;
        v_start_time := (v_item->>'start_time')::TIMESTAMPTZ;
        v_escort_id  := (v_item->>'escort_fleet_id')::INT;

        v_escort_ok := FALSE;
        IF v_escort_id IS NOT NULL THEN
            SELECT TRUE INTO v_escort_ok
            FROM fleets f JOIN fleet_status fs ON f.status_id = fs.id
            WHERE f.id = v_escort_id
              AND f.position = v_from_world
              AND LOWER(fs.name) IN ('idle', 'defence', 'defence', 'patrol', 'blockading', 'ftl supply');
            IF NOT FOUND THEN
                v_escort_ok := FALSE;
                v_escort_id := NULL;
            END IF;
        END IF;

        INSERT INTO resource_transfers
            (from_faction_id, to_faction_id, from_world_id, to_world_id, status_id, start_time, arrival_time, escort_fleet_id)
        VALUES (
            (v_item->>'from_faction_id')::INT,
            (v_item->>'to_faction_id')::INT,
            v_from_world,
            v_to_world,
            (SELECT id FROM transfer_statuses WHERE name = 'in_transit'),
            v_start_time,
            (v_item->>'arrival_time')::TIMESTAMPTZ,
            v_escort_id
        )
        RETURNING id INTO v_transfer_id;

        INSERT INTO transfer_resources (transfer_id, resource_id, amount)
        VALUES (v_transfer_id, (v_item->>'resource_id')::INT, (v_item->>'amount')::BIGINT);

        IF v_escort_ok THEN
            PERFORM sp_move_fleet(v_escort_id, v_to_world, v_start_time);
        END IF;
    END LOOP;

    DELETE FROM national_spirits WHERE faction_id = p_faction_id AND expires_at IS NOT NULL AND expires_at <= now();
END;
$$;










CREATE OR REPLACE FUNCTION sp_buy_building(
    p_faction_id    INT,
    p_world_id      INT,
    p_building_id   INT,
    p_amount        INT,
    p_level         INT,
    p_costs         JSONB      
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_key       TEXT;
    v_cost      BIGINT;
    v_res_id    INT;
    v_current   BIGINT;
BEGIN
    FOR v_key, v_cost IN SELECT key, (value::TEXT)::BIGINT FROM jsonb_each(p_costs)
    LOOP
        SELECT id INTO v_res_id FROM resources WHERE name = v_key;
        IF v_res_id IS NULL THEN
            RAISE EXCEPTION 'RESOURCE_NOT_FOUND: Unknown resource %', v_key;
        END IF;

        IF v_key IN ('CM','EL','CS','U-CM','U-EL','U-CS','Population') THEN
            SELECT COALESCE(amount, 0) INTO v_current
            FROM local_treasury
            WHERE faction_id = p_faction_id AND world_id = p_world_id AND resource_id = v_res_id;

            IF COALESCE(v_current, 0) < v_cost THEN
                RAISE EXCEPTION 'RESOURCE_INSUFFICIENT: Insufficient % — need %, have %',
                    v_key, v_cost, COALESCE(v_current, 0);
            END IF;

            UPDATE local_treasury SET amount = amount - v_cost
            WHERE faction_id = p_faction_id AND world_id = p_world_id AND resource_id = v_res_id;
        ELSE
            SELECT COALESCE(amount, 0) INTO v_current
            FROM faction_treasury WHERE faction_id = p_faction_id AND resource_id = v_res_id;

            IF COALESCE(v_current, 0) < v_cost THEN
                RAISE EXCEPTION 'RESOURCE_INSUFFICIENT: Insufficient % — need %, have %',
                    v_key, v_cost, COALESCE(v_current, 0);
            END IF;

            UPDATE faction_treasury SET amount = amount - v_cost
            WHERE faction_id = p_faction_id AND resource_id = v_res_id;
        END IF;
    END LOOP;

    INSERT INTO faction_world_buildings (faction_id, world_id, building_id, level, amount)
    VALUES (p_faction_id, p_world_id, p_building_id, p_level, p_amount)
    ON CONFLICT (faction_id, world_id, building_id, level)
    DO UPDATE SET amount = faction_world_buildings.amount + p_amount;
END;
$$;


CREATE OR REPLACE FUNCTION sp_refund_building(
    p_faction_id    INT,
    p_world_id      INT,
    p_building_id   INT,
    p_amount        INT,
    p_level         INT,
    p_refunds       JSONB      
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_current_amount    INT;
    v_new_amount        INT;
    v_key               TEXT;
    v_refund_amt        BIGINT;
    v_res_id            INT;
BEGIN
    SELECT amount INTO v_current_amount FROM faction_world_buildings
    WHERE faction_id = p_faction_id AND world_id = p_world_id
      AND building_id = p_building_id AND level = p_level;

    IF COALESCE(v_current_amount, 0) < p_amount THEN
        RAISE EXCEPTION 'INSUFFICIENT_BUILDINGS: Not enough level % buildings — have %, need %',
            p_level, COALESCE(v_current_amount, 0), p_amount;
    END IF;

    
    FOR v_key, v_refund_amt IN SELECT key, (value::TEXT)::BIGINT FROM jsonb_each(p_refunds)
    LOOP
        SELECT id INTO v_res_id FROM resources WHERE name = v_key;
        IF v_res_id IS NULL THEN
            RAISE EXCEPTION 'RESOURCE_NOT_FOUND: Unknown resource %', v_key;
        END IF;

        IF v_key IN ('CM','EL','CS','U-CM','U-EL','U-CS','Population') THEN
            INSERT INTO local_treasury (faction_id, world_id, resource_id, amount)
            VALUES (p_faction_id, p_world_id, v_res_id, v_refund_amt)
            ON CONFLICT (faction_id, world_id, resource_id)
            DO UPDATE SET amount = local_treasury.amount + v_refund_amt;
        ELSE
            INSERT INTO faction_treasury (faction_id, resource_id, amount)
            VALUES (p_faction_id, v_res_id, v_refund_amt)
            ON CONFLICT (faction_id, resource_id)
            DO UPDATE SET amount = faction_treasury.amount + v_refund_amt;
        END IF;
    END LOOP;

    v_new_amount := v_current_amount - p_amount;
    IF v_new_amount = 0 THEN
        DELETE FROM faction_world_buildings
        WHERE faction_id = p_faction_id AND world_id = p_world_id
          AND building_id = p_building_id AND level = p_level;
    ELSE
        UPDATE faction_world_buildings SET amount = v_new_amount
        WHERE faction_id = p_faction_id AND world_id = p_world_id
          AND building_id = p_building_id AND level = p_level;
    END IF;
END;
$$;


CREATE OR REPLACE FUNCTION sp_destroy_building(
    p_faction_id    INT,
    p_world_id      INT,
    p_building_id   INT,
    p_amount        INT,
    p_level         INT
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_current   INT;
    v_new       INT;
BEGIN
    SELECT amount INTO v_current FROM faction_world_buildings
    WHERE faction_id = p_faction_id AND world_id = p_world_id
      AND building_id = p_building_id AND level = p_level;

    IF COALESCE(v_current, 0) < p_amount THEN
        RAISE EXCEPTION 'INSUFFICIENT_BUILDINGS: Not enough level % buildings — have %, need %',
            p_level, COALESCE(v_current, 0), p_amount;
    END IF;

    v_new := v_current - p_amount;
    IF v_new = 0 THEN
        DELETE FROM faction_world_buildings
        WHERE faction_id = p_faction_id AND world_id = p_world_id
          AND building_id = p_building_id AND level = p_level;
    ELSE
        UPDATE faction_world_buildings SET amount = v_new
        WHERE faction_id = p_faction_id AND world_id = p_world_id
          AND building_id = p_building_id AND level = p_level;
    END IF;
END;
$$;


CREATE OR REPLACE FUNCTION sp_transfer_building(
    p_from_faction  INT,
    p_to_faction    INT,
    p_world_id      INT,
    p_building_id   INT,
    p_amount        INT,
    p_level         INT
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_current   INT;
    v_new       INT;
BEGIN
    SELECT amount INTO v_current FROM faction_world_buildings
    WHERE faction_id = p_from_faction AND world_id = p_world_id
      AND building_id = p_building_id AND level = p_level;

    IF COALESCE(v_current, 0) < p_amount THEN
        RAISE EXCEPTION 'INSUFFICIENT_BUILDINGS: Not enough level % buildings — have %, need %',
            p_level, COALESCE(v_current, 0), p_amount;
    END IF;

    v_new := v_current - p_amount;
    IF v_new = 0 THEN
        DELETE FROM faction_world_buildings
        WHERE faction_id = p_from_faction AND world_id = p_world_id
          AND building_id = p_building_id AND level = p_level;
    ELSE
        UPDATE faction_world_buildings SET amount = v_new
        WHERE faction_id = p_from_faction AND world_id = p_world_id
          AND building_id = p_building_id AND level = p_level;
    END IF;

    INSERT INTO faction_world_buildings (faction_id, world_id, building_id, level, amount)
    VALUES (p_to_faction, p_world_id, p_building_id, p_level, p_amount)
    ON CONFLICT (faction_id, world_id, building_id, level)
    DO UPDATE SET amount = faction_world_buildings.amount + p_amount;
END;
$$;


CREATE OR REPLACE FUNCTION sp_buy_vehicle(
    p_faction_id        INT,
    p_world_id          INT,
    p_fleet_id          INT,
    p_vehicle_id        INT,
    p_amount            INT,
    p_factory_space     BIGINT,
    p_completion        TIMESTAMPTZ,
    p_costs             JSONB      
) RETURNS INT LANGUAGE plpgsql AS $$
DECLARE
    v_order_id  INT;
    r           JSONB;
    v_res_id    INT;
    v_total     BIGINT;
    v_current   BIGINT;
    LOCAL_RES   CONSTANT TEXT[] := ARRAY['CM','EL','CS','U-CM','U-EL','U-CS','Population'];
BEGIN
    FOR r IN SELECT * FROM jsonb_array_elements(p_costs)
    LOOP
        SELECT id INTO v_res_id FROM resources WHERE name = r->>'name';
        IF v_res_id IS NULL THEN
            RAISE EXCEPTION 'RESOURCE_NOT_FOUND: Unknown resource %', r->>'name';
        END IF;

        v_total := (r->>'amount')::BIGINT * p_amount;

        IF r->>'name' = ANY(LOCAL_RES) THEN
            SELECT COALESCE(amount, 0) INTO v_current
            FROM local_treasury
            WHERE faction_id = p_faction_id AND world_id = p_world_id AND resource_id = v_res_id;

            IF COALESCE(v_current, 0) < v_total THEN
                RAISE EXCEPTION 'RESOURCE_INSUFFICIENT: Insufficient % — need %, have %',
                    r->>'name', v_total, COALESCE(v_current, 0);
            END IF;

            UPDATE local_treasury SET amount = amount - v_total
            WHERE faction_id = p_faction_id AND world_id = p_world_id AND resource_id = v_res_id;
        ELSE
            SELECT COALESCE(amount, 0) INTO v_current
            FROM faction_treasury
            WHERE faction_id = p_faction_id AND resource_id = v_res_id;

            IF COALESCE(v_current, 0) < v_total THEN
                RAISE EXCEPTION 'RESOURCE_INSUFFICIENT: Insufficient % — need %, have %',
                    r->>'name', v_total, COALESCE(v_current, 0);
            END IF;

            UPDATE faction_treasury SET amount = amount - v_total
            WHERE faction_id = p_faction_id AND resource_id = v_res_id;
        END IF;
    END LOOP;

    INSERT INTO vehicle_construction (world_id, fleet_id, vehicle_id, quantity, factory_space_used, completion_date)
    VALUES (p_world_id, p_fleet_id, p_vehicle_id, p_amount, p_factory_space, p_completion)
    RETURNING id INTO v_order_id;

    RETURN v_order_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_refit_vehicle(
    p_faction_id        INT,
    p_fleet_id          INT,
    p_vehicle_id        INT,
    p_amount            INT,
    p_world_id          INT,
    p_factory_space     BIGINT,
    p_completion        TIMESTAMPTZ,
    p_cost_deltas       JSONB
) RETURNS INT LANGUAGE plpgsql AS $$
DECLARE
    v_order_id  INT;
    r           JSONB;
    v_res_id    INT;
    v_name      TEXT;
    v_total     BIGINT;
    v_current   BIGINT;
    LOCAL_RES   CONSTANT TEXT[] := ARRAY['CM','EL','CS','U-CM','U-EL','U-CS','Population'];
BEGIN
    PERFORM sp_remove_vehicle_from_fleet(p_fleet_id, p_vehicle_id, p_amount);

    FOR r IN SELECT * FROM jsonb_array_elements(p_cost_deltas)
    LOOP
        v_name := r->>'name';
        v_total := (r->>'amount')::BIGINT * p_amount;
        IF v_total = 0 THEN
            CONTINUE;
        END IF;

        SELECT id INTO v_res_id FROM resources WHERE name = v_name;
        IF v_res_id IS NULL THEN
            RAISE EXCEPTION 'RESOURCE_NOT_FOUND: Unknown resource %', v_name;
        END IF;

        IF v_total > 0 THEN
            IF v_name = ANY(LOCAL_RES) THEN
                SELECT COALESCE(amount, 0) INTO v_current
                FROM local_treasury
                WHERE faction_id = p_faction_id AND world_id = p_world_id AND resource_id = v_res_id;
                IF COALESCE(v_current, 0) < v_total THEN
                    RAISE EXCEPTION 'RESOURCE_INSUFFICIENT: Insufficient % — need %, have %',
                        v_name, v_total, COALESCE(v_current, 0);
                END IF;
                UPDATE local_treasury SET amount = amount - v_total
                WHERE faction_id = p_faction_id AND world_id = p_world_id AND resource_id = v_res_id;
            ELSE
                SELECT COALESCE(amount, 0) INTO v_current
                FROM faction_treasury WHERE faction_id = p_faction_id AND resource_id = v_res_id;
                IF COALESCE(v_current, 0) < v_total THEN
                    RAISE EXCEPTION 'RESOURCE_INSUFFICIENT: Insufficient % — need %, have %',
                        v_name, v_total, COALESCE(v_current, 0);
                END IF;
                UPDATE faction_treasury SET amount = amount - v_total
                WHERE faction_id = p_faction_id AND resource_id = v_res_id;
            END IF;
        ELSE
            PERFORM sp_add_resources(
                p_faction_id, p_world_id,
                jsonb_build_array(jsonb_build_object('name', v_name, 'amount', -v_total))
            );
        END IF;
    END LOOP;

    INSERT INTO vehicle_construction (world_id, fleet_id, vehicle_id, quantity, factory_space_used, completion_date)
    VALUES (p_world_id, p_fleet_id, p_vehicle_id, p_amount, p_factory_space, p_completion)
    RETURNING id INTO v_order_id;

    RETURN v_order_id;
END;
$$;


CREATE OR REPLACE FUNCTION sp_reactivate_fleet(
    p_fleet_id      INT,
    p_completion    TIMESTAMPTZ
) RETURNS JSONB LANGUAGE plpgsql AS $$
DECLARE
    v_world_id          INT;
    v_vehicle           RECORD;
    v_total_space       BIGINT := 0;
    v_vehicle_list      JSONB  := '[]'::JSONB;
    v_space             BIGINT;
BEGIN
    SELECT position INTO v_world_id FROM fleets WHERE id = p_fleet_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'FLEET_NOT_FOUND: Fleet #% does not exist', p_fleet_id;
    END IF;

    FOR v_vehicle IN
        SELECT fv.vehicle_id, fv.amount, v.name,
               COALESCE((
                   SELECT (elem->>'length')::INT
                   FROM unnest(v.vehicle_data) elem
                   WHERE elem->>'length' IS NOT NULL
                   LIMIT 1
               ), 0) as length
        FROM fleet_vehicles fv
        JOIN vehicles v ON fv.vehicle_id = v.id
        WHERE fv.fleet_id = p_fleet_id
    LOOP
        v_space := GREATEST(v_vehicle.length, 1) * v_vehicle.amount;
        v_total_space := v_total_space + v_space;

        INSERT INTO vehicle_construction
            (world_id, fleet_id, vehicle_id, quantity, factory_space_used, completion_date)
        VALUES (v_world_id, p_fleet_id, v_vehicle.vehicle_id, v_vehicle.amount, v_space, p_completion);

        v_vehicle_list := v_vehicle_list || jsonb_build_array(
            jsonb_build_object('name', v_vehicle.name, 'amount', v_vehicle.amount)
        );
    END LOOP;

    DELETE FROM fleet_vehicles WHERE fleet_id = p_fleet_id;
    UPDATE fleets SET status_id = (SELECT id FROM fleet_status WHERE LOWER(name) = 'idle'), total_cs = 0
    WHERE id = p_fleet_id;

    RETURN jsonb_build_object('total_space', v_total_space, 'vehicles', v_vehicle_list);
END;
$$;


CREATE OR REPLACE FUNCTION sp_transfer_vehicle(
    p_from_fleet_id INT,
    p_to_fleet_id   INT,
    p_vehicle_id    INT,
    p_amount        INT
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_available INT;
BEGIN
    SELECT amount INTO v_available FROM fleet_vehicles
    WHERE fleet_id = p_from_fleet_id AND vehicle_id = p_vehicle_id;

    IF NOT FOUND OR v_available < p_amount THEN
        RAISE EXCEPTION 'VEHICLE_INSUFFICIENT: Source fleet has only % units, cannot transfer %',
            COALESCE(v_available, 0), p_amount;
    END IF;

    IF v_available = p_amount THEN
        DELETE FROM fleet_vehicles WHERE fleet_id = p_from_fleet_id AND vehicle_id = p_vehicle_id;
    ELSE
        UPDATE fleet_vehicles SET amount = amount - p_amount
        WHERE fleet_id = p_from_fleet_id AND vehicle_id = p_vehicle_id;
    END IF;

    INSERT INTO fleet_vehicles (fleet_id, vehicle_id, amount)
    VALUES (p_to_fleet_id, p_vehicle_id, p_amount)
    ON CONFLICT (fleet_id, vehicle_id)
    DO UPDATE SET amount = fleet_vehicles.amount + EXCLUDED.amount;

    UPDATE fleets SET total_cs = (
        SELECT COALESCE(SUM(fv.amount * vc.amount), 0)
        FROM fleet_vehicles fv
        JOIN vehicle_costs vc ON fv.vehicle_id = vc.vehicle_id
        JOIN resources r ON vc.resource_id = r.id AND r.name = 'CS'
        WHERE fv.fleet_id = fleets.id
    )
    WHERE id = ANY(ARRAY[p_from_fleet_id, p_to_fleet_id]);
END;


$$;

CREATE TABLE IF NOT EXISTS comets (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        TEXT NOT NULL,
    message     TEXT NOT NULL,
    discoverer  BIGINT NOT NULL REFERENCES users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

