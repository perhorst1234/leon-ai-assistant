import json
from types import SimpleNamespace

import pytest

from leon_control_plane.shopper_runtime import contact_decision, contact_message, send_first_contact
from leon_control_plane.local_model import LocalModelConfig


def test_message_respects_four_slots_and_total_budget():
    watch = {"min_ram_gb": 64, "max_ram_sticks": 4, "max_total_cents": 4999}
    message = contact_message(watch, {"title": "5x16GB DDR3 ECC"}, 4000)
    assert "4 modules van 16 GB" in message and "€40,00 inclusief verzending" in message
    with pytest.raises(ValueError):
        contact_message(watch, {"title": "5x16GB DDR3 ECC"}, 5000)


def test_unopened_conversation_never_sends():
    class Browser:
        def run(self, *args):
            if args == ("tab", "list"):
                return "[t1] Listing - https://www.marktplaats.nl/v/ram/m1"
            if args == ("snapshot", "-i"):
                return '- button "Bericht" [ref=e1]'
            return ""
        def current(self, platform):
            return "https://www.marktplaats.nl/v/ram/m1"
        def send(self, *args):
            raise AssertionError("Must never send without a conversation")
    assert send_first_contact(Browser(), "https://www.marktplaats.nl/v/ram/m1", "Hoi")["status"] == "needs_owner"


@pytest.mark.parametrize("decision", [
    {"candidate_index": 9, "offer_cents": 4000, "reason": "unknown listing"},
    {"candidate_index": 0, "offer_cents": 5000, "reason": "over budget"},
])
def test_local_model_cannot_invent_destination_or_exceed_budget(monkeypatch, decision):
    monkeypatch.setattr("leon_control_plane.shopper_runtime.LocalModelConfig.from_env", lambda **kwargs: LocalModelConfig(enabled=True))
    monkeypatch.setattr("leon_control_plane.shopper_runtime.subprocess.run", lambda *args, **kwargs: SimpleNamespace(stdout="35\n"))
    monkeypatch.setattr("leon_control_plane.shopper_runtime.send_response", lambda payload, config: {
        "model": payload["model"], "done": True, "response": json.dumps(decision), "done_reason": "stop",
    })
    watch = {"max_total_cents": 4999, "min_ram_gb": 64, "preferred_ram_gb": 128, "max_ram_sticks": 4}
    matches = [{"title": "4x16GB DDR3", "asking_price_cents": 4000, "capacity_gb": 64, "usable_capacity_gb": 64, "notes": []}]
    with pytest.raises(ValueError):
        contact_decision(watch, matches)


def test_delayed_listing_dialog_sends_once_without_claiming_delivery():
    class Browser:
        snapshots = 0
        sends = 0
        def run(self, *args):
            if args == ("tab", "list"):
                return "[t1] Listing - https://www.marktplaats.nl/v/ram/m1"
            if args == ("snapshot", "-i"):
                self.snapshots += 1
                if self.snapshots <= 2:
                    return '- button "Bericht" [ref=e1]'
                return '- dialog "Bericht" [ref=e2]\n- textbox "Bericht" [required, ref=e3]\n- button "Stuur bericht" [ref=e4]'
            return ""
        def current(self, platform):
            return "https://www.marktplaats.nl/v/ram/m1"
        def send(self, platform, textbox, button, message, expected):
            self.sends += 1
            assert textbox == "@e3" and button == "@e4"
            return {"status": "clicked", "delivery_confirmed": False}
    browser = Browser()
    result = send_first_contact(browser, "https://www.marktplaats.nl/v/ram/m1", "Hoi")
    assert browser.sends == 1 and result["status"] == "clicked" and not result["delivery_confirmed"]


def test_read_only_confirmation_requires_exact_owner_message():
    import hashlib
    from leon_control_plane.shopper_runtime import confirm_delivery
    class Browser:
        def run(self, *args):
            if args[0] == 'eval':
                return json.dumps(json.dumps(['https://www.marktplaats.nl/messages/123']))
            return ''
        def current(self, platform):
            return 'https://www.marktplaats.nl/messages/123'
        def own_messages(self, limit):
            return {'messages': ['Hoi, €40 inclusief verzending?']}
        def send(self, *args):
            raise AssertionError('Confirmation must never send')
    browser = Browser()
    exact = hashlib.sha256('Hoi, €40 inclusief verzending?'.encode()).hexdigest()
    assert confirm_delivery(browser, 'RAM', exact)['status'] == 'confirmed'
    different = hashlib.sha256('Different message'.encode()).hexdigest()
    assert confirm_delivery(browser, 'RAM', different)['status'] == 'clicked'
