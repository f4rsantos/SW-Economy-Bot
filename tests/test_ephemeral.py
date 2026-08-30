import types

import pytest

import utils.checks as checks
import utils.faction_utils as faction_utils


class FakeInteraction:
    def __init__(self, user_id, namespace_kwargs, extras=None):
        self.user = types.SimpleNamespace(id=user_id)
        self.namespace = types.SimpleNamespace(**namespace_kwargs)
        self.extras = extras if extras is not None else {}


@pytest.fixture
def patched(monkeypatch):
    state = {'ephemeral': {}, 'factions': {}, 'levels': {}}

    async def fake_get_user_ephemeral(user_id):
        return state['ephemeral'].get(user_id, False)

    async def fake_leads_faction_named(user_id, faction_name):
        if not faction_name:
            return False
        faction = state['factions'].get(faction_name)
        return bool(faction) and faction.get('leader_id') == user_id

    async def fake_get_user_access_level(user_id):
        return state['levels'].get(user_id, 0)

    monkeypatch.setattr(checks, 'get_user_ephemeral', fake_get_user_ephemeral)
    monkeypatch.setattr(faction_utils, 'leads_faction_named', fake_leads_faction_named)
    monkeypatch.setattr('services.user_service.get_user_access_level', fake_get_user_access_level)
    return state


@pytest.mark.asyncio
async def test_leader_with_setting_on_gets_ephemeral(patched):
    patched['ephemeral'][1] = True
    patched['factions']['Kestrel'] = {'leader_id': 1}

    interaction = FakeInteraction(1, {'faction': 'Kestrel'}, {'ephemeral_param': 'faction'})
    assert await checks.resolve_ephemeral(interaction) is True


@pytest.mark.asyncio
async def test_leader_with_setting_off_stays_public(patched):
    patched['ephemeral'][1] = False
    patched['factions']['Kestrel'] = {'leader_id': 1}

    interaction = FakeInteraction(1, {'faction': 'Kestrel'}, {'ephemeral_param': 'faction'})
    assert await checks.resolve_ephemeral(interaction) is False


@pytest.mark.asyncio
async def test_non_leader_stays_public(patched):
    patched['ephemeral'][2] = True
    patched['factions']['Kestrel'] = {'leader_id': 1}

    interaction = FakeInteraction(2, {'faction': 'Kestrel'}, {'ephemeral_param': 'faction'})
    assert await checks.resolve_ephemeral(interaction) is False


@pytest.mark.asyncio
async def test_staff_does_not_get_ephemeral_on_other_faction(patched):
    patched['ephemeral'][9] = True
    patched['levels'][9] = 9
    patched['factions']['Kestrel'] = {'leader_id': 1}

    interaction = FakeInteraction(9, {'faction': 'Kestrel'}, {'ephemeral_param': 'faction'})
    assert await checks.resolve_ephemeral(interaction) is False


@pytest.mark.asyncio
async def test_command_without_decorator_is_public(patched):
    patched['ephemeral'][1] = True
    patched['factions']['Kestrel'] = {'leader_id': 1}

    interaction = FakeInteraction(1, {'faction': 'Kestrel'}, {})
    assert await checks.resolve_ephemeral(interaction) is False


@pytest.mark.asyncio
async def test_missing_faction_argument_is_public(patched):
    patched['ephemeral'][1] = True

    interaction = FakeInteraction(1, {'faction': None}, {'ephemeral_param': 'faction'})
    assert await checks.resolve_ephemeral(interaction) is False


@pytest.mark.asyncio
async def test_unknown_faction_is_public(patched):
    patched['ephemeral'][1] = True

    interaction = FakeInteraction(1, {'faction': 'Nowhere'}, {'ephemeral_param': 'faction'})
    assert await checks.resolve_ephemeral(interaction) is False


@pytest.mark.asyncio
async def test_leader_of_other_faction_is_public_here(patched):
    patched['ephemeral'][1] = True
    patched['factions']['Kestrel'] = {'leader_id': 1}
    patched['factions']['Vault Combine'] = {'leader_id': 7}

    interaction = FakeInteraction(1, {'faction': 'Vault Combine'}, {'ephemeral_param': 'faction'})
    assert await checks.resolve_ephemeral(interaction) is False


@pytest.mark.asyncio
async def test_result_is_cached_on_extras(patched):
    patched['ephemeral'][1] = True
    patched['factions']['Kestrel'] = {'leader_id': 1}

    interaction = FakeInteraction(1, {'faction': 'Kestrel'}, {'ephemeral_param': 'faction'})
    assert await checks.resolve_ephemeral(interaction) is True

    patched['factions']['Kestrel'] = {'leader_id': 999}
    assert await checks.resolve_ephemeral(interaction) is True
