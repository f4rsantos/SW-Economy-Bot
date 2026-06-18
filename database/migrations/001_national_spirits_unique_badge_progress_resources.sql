-- Dedupe existing national_spirits rows per (faction_id, spirit_type_id), keeping latest grant
DELETE FROM national_spirits ns
WHERE ns.id NOT IN (
    SELECT MAX(id) FROM national_spirits GROUP BY faction_id, spirit_type_id
);

ALTER TABLE national_spirits
    ADD CONSTRAINT uq_national_spirits_faction_type UNIQUE (faction_id, spirit_type_id);

-- Replace single-resource badge_progress with per-resource tracking
CREATE TABLE IF NOT EXISTS badge_progress_resources (
    user_id bigint NOT NULL,
    badge_id integer NOT NULL,
    resource_id integer NOT NULL,
    current_amount bigint NOT NULL DEFAULT 0 CHECK (current_amount >= 0),
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT badge_progress_resources_pkey PRIMARY KEY (user_id, badge_id, resource_id),
    CONSTRAINT badge_progress_resources_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT badge_progress_resources_badge_id_fkey FOREIGN KEY (badge_id) REFERENCES badges(id),
    CONSTRAINT badge_progress_resources_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES resources(id)
);

-- Migrate existing single-resource progress rows (each badge's first/only cost resource)
INSERT INTO badge_progress_resources (user_id, badge_id, resource_id, current_amount, updated_at)
SELECT bp.user_id, bp.badge_id, bc.resource_id, bp.current_amount, bp.updated_at
FROM badge_progress bp
JOIN LATERAL (
    SELECT resource_id FROM badge_costs WHERE badge_id = bp.badge_id ORDER BY resource_id LIMIT 1
) bc ON true
ON CONFLICT (user_id, badge_id, resource_id) DO NOTHING;

DROP TABLE badge_progress;

-- Remove continuity system columns
ALTER TABLE settings DROP COLUMN IF EXISTS continuity_triggered_at;
ALTER TABLE operators DROP COLUMN IF EXISTS continuity_confirmed;
