-- Apply in Supabase alongside the matching code deploy.
-- Adds the Alloys resource: a global (faction_treasury) resource, transferable,
-- not hard-limited (the black market's 10-held cap is enforced in application code,
-- not a database constraint, since other future sources of Alloys will exist).

INSERT INTO public.resources (id, name, refined_from, is_limited, hard_limit, is_transferable)
SELECT COALESCE(MAX(id), 0) + 1, 'Alloys', NULL, false, NULL, true
FROM public.resources
WHERE NOT EXISTS (SELECT 1 FROM public.resources WHERE name = 'Alloys');
