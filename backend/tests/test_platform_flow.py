def create_account_and_server(client):
    registered = client.post('/api/v1/auth/register', json={
        'email': 'owner@example.com', 'password': 'CorrectHorseBattery!2026'
    })
    assert registered.status_code == 201, registered.text
    token = registered.json()['access_token']
    created = client.post('/api/v1/servers', headers={'Authorization': f'Bearer {token}'}, json={
        'name': 'Test Bedrock', 'slug': 'test-bedrock', 'description': 'Integration tests'
    })
    assert created.status_code == 201, created.text
    code = created.json()['activation_code']
    activated = client.post('/api/v1/registration/activate', json={'code': code})
    assert activated.status_code == 200, activated.text
    return token, activated.json()['server_secret'], code


def test_registration_activation_pairing_and_isolation(client):
    owner_token, server_secret, _activation_code = create_account_and_server(client)

    pairing = client.post('/api/v1/pairing/codes', headers={'X-Tenant-Slug': 'test-bedrock'})
    assert pairing.status_code == 201, pairing.text
    code = pairing.json()['pairing_code']
    assert len(code) == 6 and code.isdigit()

    claim = client.post('/api/v1/pairing/claim', headers={'X-Server-Key': server_secret}, json={
        'code': code, 'identity_key': 'bds-session-123', 'display_name': 'Steve',
        'dimension': 'minecraft:overworld', 'x': 0, 'y': 64, 'z': 0,
    })
    assert claim.status_code == 200, claim.text
    assert claim.json()['paired'] is True

    status = client.get('/api/v1/pairing/status')
    assert status.status_code == 200, status.text
    assert status.json()['paired'] is True
    assert status.json()['player']['name'] == 'Steve'

    positions = client.post('/api/v1/players/positions', headers={'X-Server-Key': server_secret}, json={
        'players': [
            {'identity_key': 'bds-session-123', 'display_name': 'Steve', 'dimension': 'minecraft:overworld', 'x': 0, 'y': 64, 'z': 0},
            {'identity_key': 'bds-session-456', 'display_name': 'Alex', 'dimension': 'minecraft:overworld', 'x': 10, 'y': 64, 'z': 0},
            {'identity_key': 'bds-session-789', 'display_name': 'Ender', 'dimension': 'minecraft:the_end', 'x': 1, 'y': 64, 'z': 1},
        ]
    })
    assert positions.status_code == 200, positions.text
    nearby = positions.json()['nearby']
    assert 'bds-session-456' in nearby['bds-session-123']
    assert 'bds-session-789' not in nearby['bds-session-123']

    # Fail closed when LiveKit credentials are not configured in this test environment.
    voice_token = client.post('/api/v1/voice/token')
    assert voice_token.status_code == 503

    # A second tenant cannot consume the first tenant's activation code or player state.
    other = client.post('/api/v1/servers', headers={'Authorization': f'Bearer {owner_token}'}, json={
        'name': 'Other Server', 'slug': 'other-server'
    })
    assert other.status_code == 201
    invalid = client.post('/api/v1/pairing/claim', headers={'X-Server-Key': 'not-a-server-key'}, json={
        'code': code, 'identity_key': 'attacker', 'display_name': 'Attacker',
        'dimension': 'minecraft:overworld', 'x': 0, 'y': 0, 'z': 0,
    })
    assert invalid.status_code == 401


def test_private_group_requires_password_and_enforces_membership(client):
    _, server_secret, _activation_code = create_account_and_server(client)
    pairing = client.post('/api/v1/pairing/codes', headers={'X-Tenant-Slug': 'test-bedrock'})
    code = pairing.json()['pairing_code']
    claim = client.post('/api/v1/pairing/claim', headers={'X-Server-Key': server_secret}, json={
        'code': code, 'identity_key': 'player-a', 'display_name': 'PlayerA',
        'dimension': 'minecraft:overworld', 'x': 0, 'y': 64, 'z': 0,
    })
    assert claim.status_code == 200

    created = client.post('/api/v1/groups', json={
        'name': 'Equipe', 'is_private': True, 'password': 'safe-group-password', 'max_members': 5
    })
    assert created.status_code == 201, created.text
    assert created.json()['is_private'] is True

    wrong = client.post('/api/v1/groups/join', json={'code': created.json()['code'], 'password': 'wrong-password'})
    assert wrong.status_code == 403
    joined = client.post('/api/v1/groups/join', json={'code': created.json()['code'], 'password': 'safe-group-password'})
    assert joined.status_code == 200


def test_activation_code_is_single_use(client):
    token, server_secret, activation_code = create_account_and_server(client)
    replay = client.post('/api/v1/registration/activate', json={'code': activation_code})
    assert replay.status_code == 400
    assert server_secret.startswith('hvs_')
    assert token


def test_pairing_generation_rate_limit(client):
    _, _server_secret, _activation_code = create_account_and_server(client)
    for _ in range(5):
        created = client.post('/api/v1/pairing/codes', headers={'X-Tenant-Slug': 'test-bedrock'})
        assert created.status_code == 201, created.text
    blocked = client.post('/api/v1/pairing/codes', headers={'X-Tenant-Slug': 'test-bedrock'})
    assert blocked.status_code == 429
    assert int(blocked.headers['Retry-After']) >= 1


def test_non_finite_position_is_rejected():
    import pytest
    from pydantic import ValidationError
    from app.main import PositionItem

    with pytest.raises(ValidationError):
        PositionItem(
            identity_key='bad-position', display_name='Bad',
            dimension='minecraft:overworld', x=float('nan'), y=0, z=0,
        )


def test_group_mode_is_exclusive_and_groups_cross_dimensions():
    from types import SimpleNamespace
    from app.voice_media import can_hear

    def player(identity, *, dimension='minecraft:overworld', x=0, active_group=None, deafened=False):
        return SimpleNamespace(
            id=identity, online=True, dimension=dimension, x=x, y=64.0, z=0.0,
            self_muted=False, moderation_muted=False, deafened=deafened,
            active_group_id=active_group,
        )

    # Default proximity mode can hear only the same dimension and range.
    listener = player('listener')
    nearby = player('nearby', x=12)
    other_dimension = player('end', dimension='minecraft:the_end', x=1)
    assert can_hear(listener, nearby, 30, set(), set(), False)
    assert not can_hear(listener, other_dimension, 30, set(), set(), False)

    # Selecting a group pauses proximity; a group member remains audible at any distance.
    listener_group = player('listener', active_group='group-1')
    close_non_member = player('close', x=2)
    far_member = player('far', dimension='minecraft:the_end', x=900, active_group='group-1')
    assert not can_hear(listener_group, close_non_member, 30, {'group-1'}, set(), False)
    assert can_hear(listener_group, far_member, 30, {'group-1'}, {'group-1'}, False)
    assert not can_hear(listener_group, far_member, 30, {'group-1'}, {'group-1'}, True)


def test_private_group_switches_player_to_exclusive_group_mode(client):
    _, server_secret, _ = create_account_and_server(client)
    pairing = client.post('/api/v1/pairing/codes', headers={'X-Tenant-Slug': 'test-bedrock'})
    claim = client.post('/api/v1/pairing/claim', headers={'X-Server-Key': server_secret}, json={
        'code': pairing.json()['pairing_code'], 'identity_key': 'group-player', 'display_name': 'GroupPlayer',
        'dimension': 'minecraft:overworld', 'x': 0, 'y': 64, 'z': 0,
    })
    assert claim.status_code == 200

    group = client.post('/api/v1/groups', json={
        'name': 'Private team', 'is_private': True, 'password': 'private-password', 'max_members': 5,
    })
    assert group.status_code == 201, group.text

    players = client.get('/api/v1/voice/nearby')
    assert players.status_code == 200, players.text
    assert players.json()['active_group_id'] == group.json()['id']

    left = client.post('/api/v1/groups/leave')
    assert left.status_code == 200
    players = client.get('/api/v1/voice/nearby')
    assert players.json()['active_group_id'] is None


def test_player_leave_immediately_expires_pairing_and_presence(client):
    _, server_secret, _ = create_account_and_server(client)
    pairing = client.post('/api/v1/pairing/codes', headers={'X-Tenant-Slug': 'test-bedrock'})
    claim = client.post('/api/v1/pairing/claim', headers={'X-Server-Key': server_secret}, json={
        'code': pairing.json()['pairing_code'], 'identity_key': 'leaving-player', 'display_name': 'LeavingPlayer',
        'dimension': 'minecraft:overworld', 'x': 0, 'y': 64, 'z': 0,
    })
    assert claim.status_code == 200
    assert client.get('/api/v1/pairing/status').json()['paired'] is True

    left = client.post('/api/v1/players/leave', headers={'X-Server-Key': server_secret}, json={
        'identity_key': 'leaving-player',
    })
    assert left.status_code == 200 and left.json()['left'] is True
    assert client.get('/api/v1/pairing/status').json()['paired'] is False



def test_voice_token_endpoint_fails_closed_when_livekit_is_down(client):
    _, server_secret, _ = create_account_and_server(client)
    pairing = client.post('/api/v1/pairing/codes', headers={'X-Tenant-Slug': 'test-bedrock'})
    claim = client.post('/api/v1/pairing/claim', headers={'X-Server-Key': server_secret}, json={
        'code': pairing.json()['pairing_code'], 'identity_key': 'voice-player', 'display_name': 'VoicePlayer',
        'dimension': 'minecraft:overworld', 'x': 0, 'y': 64, 'z': 0,
    })
    assert claim.status_code == 200
    for _ in range(12):
        result = client.post('/api/v1/voice/token')
        assert result.status_code == 503
    limited = client.post('/api/v1/voice/token')
    assert limited.status_code == 429


def test_bds_group_forms_create_and_join_private_group(client):
    _, server_secret, _ = create_account_and_server(client)
    headers = {'X-Server-Key': server_secret}
    positions = client.post('/api/v1/players/positions', headers=headers, json={'players': [
        {'identity_key': 'bds-group-owner', 'display_name': 'Owner', 'dimension': 'minecraft:overworld', 'x': 0, 'y': 64, 'z': 0},
        {'identity_key': 'bds-group-member', 'display_name': 'Member', 'dimension': 'minecraft:the_end', 'x': 500, 'y': 64, 'z': 0},
    ]})
    assert positions.status_code == 200

    created = client.post('/api/v1/players/groups/create', headers=headers, json={
        'identity_key': 'bds-group-owner', 'name': 'Equipe BDS', 'is_private': True,
        'password': 'strong-private-password', 'max_members': 6,
    })
    assert created.status_code == 201, created.text
    assert created.json()['code']

    groups = client.get('/api/v1/players/groups?identity_key=bds-group-owner', headers=headers)
    assert groups.status_code == 200, groups.text
    assert groups.json()['active_group_id'] == created.json()['id']
    assert groups.json()['groups'][0]['is_private'] is True

    wrong = client.post('/api/v1/players/groups/join', headers=headers, json={
        'identity_key': 'bds-group-member', 'code': created.json()['code'], 'password': 'incorrect-password',
    })
    assert wrong.status_code == 403
    joined = client.post('/api/v1/players/groups/join', headers=headers, json={
        'identity_key': 'bds-group-member', 'code': created.json()['code'], 'password': 'strong-private-password',
    })
    assert joined.status_code == 200, joined.text
    left = client.post('/api/v1/players/groups/leave', headers=headers, json={'identity_key': 'bds-group-member'})
    assert left.status_code == 200 and left.json()['mode'] == 'proximity'


def test_group_owner_can_delete_group_but_other_player_cannot(client):
    _, server_secret, _ = create_account_and_server(client)
    headers = {'X-Server-Key': server_secret}
    owner_pairing = client.post('/api/v1/pairing/codes', headers={'X-Tenant-Slug': 'test-bedrock'})
    owner_claim = client.post('/api/v1/pairing/claim', headers=headers, json={
        'code': owner_pairing.json()['pairing_code'], 'identity_key': 'owner-player', 'display_name': 'Owner',
        'dimension': 'minecraft:overworld', 'x': 0, 'y': 64, 'z': 0,
    })
    assert owner_claim.status_code == 200
    owner_cookie = client.cookies.get('hv_session')
    created = client.post('/api/v1/groups', json={'name': 'My group', 'is_private': False})
    assert created.status_code == 201

    member_pairing = client.post('/api/v1/pairing/codes', headers={'X-Tenant-Slug': 'test-bedrock'})
    member_claim = client.post('/api/v1/pairing/claim', headers=headers, json={
        'code': member_pairing.json()['pairing_code'], 'identity_key': 'member-player', 'display_name': 'Member',
        'dimension': 'minecraft:overworld', 'x': 1, 'y': 64, 'z': 0,
    })
    assert member_claim.status_code == 200
    denied = client.delete(f"/api/v1/groups/{created.json()['id']}")
    assert denied.status_code == 403

    deleted = client.delete(f"/api/v1/groups/{created.json()['id']}", headers={'Cookie': f'hv_session={owner_cookie}'})
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()['deleted'] is True


def test_media_sync_is_only_scheduled_from_async_endpoints():
    """schedule_media_sync creates tasks and therefore needs a running event loop."""
    import ast
    from pathlib import Path

    source = Path(__file__).parents[1] / "app" / "main.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    route_functions = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(isinstance(dec, ast.Call) and getattr(dec.func, "attr", "") in {"get", "post", "patch", "delete"}
                   for dec in node.decorator_list):
                route_functions[node.name] = node
    offenders = []
    for name, node in route_functions.items():
        calls_sync = any(isinstance(part, ast.Call) and getattr(part.func, "id", "") == "schedule_media_sync"
                         for part in ast.walk(node))
        if calls_sync and not isinstance(node, ast.AsyncFunctionDef):
            offenders.append(name)
    assert offenders == [], f"Rotas agendando tarefas fora do event loop: {offenders}"
