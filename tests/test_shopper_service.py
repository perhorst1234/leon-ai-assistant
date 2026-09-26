import uuid

import pytest

from leon_control_plane.shopper_service import ShopperService, ram_capacity, shortlist


def spec(**kwargs):
    return {"request_id": str(uuid.uuid4()), "platform": "marktplaats", "query": "ddr3",
            "max_total_cents": 5000, "min_ram_gb": 64, "preferred_ram_gb": 128,
            "required_terms": ["ddr3"], "excluded_terms": ["ddr4"], **kwargs}


def test_capacity_does_not_multiply_single_stick_price():
    assert ram_capacity("4x16GB DDR3 ECC") == 64
    watch = spec()
    items = [
        {"url": "https://www.marktplaats.nl/v/ram/m1", "title": "128GB 8x16GB DDR3 ECC", "text": "DDR3 € 45,00"},
        {"url": "https://www.marktplaats.nl/v/ram/m2", "title": "16GB DDR3 ECC", "text": "16GB DDR3 € 5,00 per stuk"},
        {"url": "https://www.marktplaats.nl/v/ram/m3", "title": "7x8GB DDR3", "text": "15x8GB DDR3, 8 verkocht"},
        {"url": "https://www.marktplaats.nl/v/ram/m4", "title": "128GB DDR4", "text": "€ 40,00"},
    ]
    result = shortlist(items, watch)
    assert len(result) == 1 and result[0]["capacity_gb"] == 128
    assert result[0]["asking_price_cents"] == 4500
    assert not result[0]["total_price_confirmed"]


def test_watch_request_id_binding_and_pause(tmp_path):
    service = ShopperService(tmp_path / "shopper.sqlite")
    body = spec()
    created = service.create(body)
    assert service.create(body)["id"] == created["id"]
    with pytest.raises(ValueError):
        service.create({**body, "max_total_cents": 10000})
    service.set_enabled(created["id"], False)
    with pytest.raises(ValueError):
        service.start(created["id"])


def test_slot_limit_rejects_eight_small_sticks_and_limits_five_large_sticks():
    items = [
        {"url": "https://www.marktplaats.nl/v/ram/m1", "title": "8x8GB DDR3 ECC", "text": "€ 40,00"},
        {"url": "https://www.marktplaats.nl/v/ram/m2", "title": "5x16GB DDR3 ECC", "text": "Bieden"},
    ]
    result = shortlist(items, spec(max_ram_sticks=4))
    assert len(result) == 1
    assert result[0]["capacity_gb"] == 80 and result[0]["usable_capacity_gb"] == 64


def test_weekly_run_is_durable_and_failed_browser_retries_hourly(tmp_path):
    now = [1000.0]
    class FakeBrowser:
        def search(self, platform, query):
            return {"items": [{"url": "https://www.marktplaats.nl/v/ram/m1", "title": "4x16GB DDR3", "text": "4x16GB DDR3 € 40,00"}], "empty": False, "challenge": False}
    service = ShopperService(tmp_path / "shopper.sqlite", bridge_factory=FakeBrowser, clock=lambda: now[0])
    watch = service.create(spec())
    service.start(watch["id"], background=False)
    with service.connect() as connection:
        assert connection.execute("SELECT status FROM runs").fetchone()[0] == "complete"
        assert connection.execute("SELECT next_run FROM watches").fetchone()[0] == now[0] + 7 * 86400
    assert service.start(watch["id"], due_only=True)["status"] == "not_due"
    now[0] += 7 * 86400
    service.bridge_factory = lambda: (_ for _ in ()).throw(RuntimeError("private failure"))
    service.start(watch["id"], background=False)
    with service.connect() as connection:
        assert connection.execute("SELECT next_run FROM watches").fetchone()[0] == now[0] + 3600
        assert "private failure" not in connection.execute("SELECT result FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()[0]


def test_challenge_is_not_retried_or_treated_as_no_deals(tmp_path):
    class Challenge:
        def search(self, platform, query):
            return {"items": [], "empty": False, "challenge": True}
    service = ShopperService(tmp_path / "shopper.sqlite", bridge_factory=Challenge)
    watch = service.create(spec())
    service.start(watch["id"], background=False)
    with service.connect() as connection:
        assert connection.execute("SELECT status FROM runs").fetchone()[0] == "needs_owner"


def test_reply_delay_survives_restart_and_never_repeats_unknown_send(tmp_path, monkeypatch):
    import json
    from datetime import datetime
    from leon_control_plane.shopper_schedule import AMSTERDAM
    now = [datetime(2026, 9, 26, 14, tzinfo=AMSTERDAM).timestamp()]
    rows = [{'own': True, 'text': 'Hoi, €40 inclusief verzending?'}, {'own': False, 'text': 'Kan voor €45 inclusief verzenden.'}]
    monkeypatch.setattr('leon_control_plane.shopper_runtime.read_conversation', lambda *args: rows)
    calls = []
    monkeypatch.setattr('leon_control_plane.shopper_runtime.reply_decision', lambda *args: {'action': 'counter', 'message': 'Dank je, €40 inclusief?', 'model': 'test-local'})
    def uncertain(*args):
        calls.append(args)
        raise RuntimeError('Ambiguous external click')
    monkeypatch.setattr('leon_control_plane.shopper_runtime.send_reply', uncertain)
    path = tmp_path / 'shopper.sqlite'
    service = ShopperService(path, bridge_factory=lambda: object(), clock=lambda: now[0])
    watch = service.create(spec(automatic_messages=True))
    with service.connect() as c:
        c.execute('INSERT INTO contacts VALUES(?,?,?,?,?)', ('https://www.marktplaats.nl/v/ram/m1', watch['id'], now[0], 'confirmed', json.dumps({'conversation_url': 'https://www.marktplaats.nl/messages/123'})))
    service.follow_up()
    assert not calls
    with service.connect() as c:
        due = c.execute('SELECT due_at FROM replies').fetchone()[0]
    now[0] = due + 1
    service = ShopperService(path, bridge_factory=lambda: object(), clock=lambda: now[0])
    service.follow_up()
    service.follow_up()
    assert len(calls) == 1
    with service.connect() as c:
        assert c.execute('SELECT status FROM replies').fetchone()[0] == 'attempted'


def test_owner_reply_cancels_pending_automatic_reply(tmp_path, monkeypatch):
    import json
    rows = [{'own': True, 'text': 'Hoi'}, {'own': False, 'text': 'Ja'}]
    monkeypatch.setattr('leon_control_plane.shopper_runtime.read_conversation', lambda *args: rows)
    service = ShopperService(tmp_path / 'shopper.sqlite', bridge_factory=lambda: object(), clock=lambda: 1790420000)
    watch = service.create(spec(automatic_messages=True))
    with service.connect() as c:
        c.execute('INSERT INTO contacts VALUES(?,?,?,?,?)', ('https://www.marktplaats.nl/v/ram/m1', watch['id'], 1790420000, 'confirmed', json.dumps({'conversation_url': 'https://www.marktplaats.nl/messages/123'})))
    service.follow_up()
    rows.append({'own': True, 'text': 'Ik antwoord zelf'})
    service.follow_up()
    with service.connect() as c:
        assert c.execute('SELECT status FROM replies').fetchone()[0] == 'superseded'


def test_128gb_priority_excludes_fallback_until_three_weeks(tmp_path):
    import json
    now = [1790424000.0]
    class Browser:
        def search(self, platform, query):
            return {'items': [{'url': 'https://www.marktplaats.nl/v/ram/m1', 'title': '4x16GB DDR3', 'text': '€45'}], 'empty': False, 'challenge': False}
    service = ShopperService(tmp_path / 'shopper.sqlite', bridge_factory=Browser, clock=lambda: now[0])
    watch = service.create(spec(min_ram_gb=128, max_ram_sticks=4))
    with service.connect() as c:
        saved = json.loads(c.execute('SELECT spec FROM watches WHERE id=?', (watch['id'],)).fetchone()[0])
        saved.update(fallback_min_ram_gb=64, fallback_after=now[0] + 21 * 86400)
        c.execute('UPDATE watches SET spec=? WHERE id=?', (json.dumps(saved), watch['id']))
    service.start(watch['id'], background=False)
    assert not service.state()['watches'][0]['latest_run']['result']['matches']
    now[0] += 21 * 86400
    service.start(watch['id'], background=False)
    assert service.state()['watches'][0]['latest_run']['result']['matches'][0]['capacity_gb'] == 64


def test_held_conversation_cannot_trigger_a_reply(tmp_path, monkeypatch):
    import json
    def unexpected(*args):
        raise AssertionError('Held conversations must not be read or answered')
    monkeypatch.setattr('leon_control_plane.shopper_runtime.read_conversation', unexpected)
    service = ShopperService(tmp_path / 'shopper.sqlite', bridge_factory=lambda: object())
    watch = service.create(spec(automatic_messages=True))
    with service.connect() as c:
        c.execute('INSERT INTO contacts VALUES(?,?,?,?,?)', ('https://www.marktplaats.nl/v/ram/m1', watch['id'], 1790420000, 'on_hold', json.dumps({'conversation_url': 'https://www.marktplaats.nl/messages/123'})))
    service.follow_up()
    assert service.state()['watches'][0]['held_contacts'] == 1
    with service.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM replies').fetchone()[0] == 0


def test_combined_sources_preserve_platform_and_continue_on_partial_failure(tmp_path):
    class Browser:
        def search(self, platform, query):
            if platform == 'vinted':
                return {'items': [], 'empty': False, 'challenge': True}
            return {'items': [{'url':'https://www.marktplaats.nl/v/ram/m1','title':'4x32GB DDR3 ECC','text':'€ 40,00'}],'empty':False,'challenge':False}
    service = ShopperService(tmp_path/'shopper.sqlite', bridge_factory=Browser)
    watch=service.create(spec(platform='both',min_ram_gb=128,max_ram_sticks=4))
    service.start(watch['id'],background=False)
    result=service.state()['watches'][0]['latest_run']
    assert result['status']=='partial'
    assert result['result']['matches'][0]['platform']=='marktplaats'
    assert result['result']['sources'][1]['status']=='needs_owner'


def test_edit_query_replaces_old_hardware_filters_without_resuming_contact(tmp_path):
    service=ShopperService(tmp_path/'shopper.sqlite')
    watch=service.create(spec())
    service.edit(watch['id'],{'query':'concert ticket','platform':'both'})
    result=service.state()['watches'][0]
    assert result['platform']=='both' and result['required_terms']==[] and result['excluded_terms']==[]
