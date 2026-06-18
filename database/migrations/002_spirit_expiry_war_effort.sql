-- Add expires_at to support persistent spirits (NULL = persistent, timestamp = removed once passed)
ALTER TABLE national_spirits ADD COLUMN expires_at timestamp with time zone;

-- Existing spirits keep current one-shot-per-cycle behavior
UPDATE national_spirits SET expires_at = now();

-- Allow a factory-only efficiency channel for war_mobilization
ALTER TABLE spirit_types DROP CONSTRAINT spirit_types_effect_type_check;
ALTER TABLE spirit_types ADD CONSTRAINT spirit_types_effect_type_check
    CHECK (effect_type IN ('efficiency', 'efficiency_factory'));

INSERT INTO spirit_types (key, display_name, effect_type, fixed_value) VALUES
    ('war_effort', 'War Effort', 'efficiency', 0.05),
    ('war_mobilization', 'War Mobilization', 'efficiency_factory', 0.15)
ON CONFLICT (key) DO NOTHING;
