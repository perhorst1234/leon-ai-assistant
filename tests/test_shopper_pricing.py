from leon_control_plane.shopper_pricing import opening_offer, ram_bundle
from leon_control_plane.shopper_runtime import contact_message

WATCH = {'min_ram_gb': 64, 'max_ram_sticks': 4, 'max_total_cents': 4999}


def test_owner_example_thirty_euros_for_four_of_five_modules():
    listing = {'title': '5x SK hynix 16GB DDR3 ECC Registered RAM – 64GB totaal', 'asking_price_cents': 4500}
    assert ram_bundle(listing['title']) == (5, 16)
    assert opening_offer(WATCH, listing) == 3000
    message = contact_message(WATCH, listing, 3000)
    assert '€30 incl. verzenden voor 4 modules van 16 GB' in message
    assert 'overwegen' not in message and 'Alvast bedankt' not in message


def test_full_set_starts_at_thirty_five_not_asking_price():
    assert opening_offer(WATCH, {'title': '4x16GB DDR3', 'asking_price_cents': 4500}) == 3500


def test_unknown_price_and_small_prices_remain_within_total_budget():
    assert opening_offer(WATCH, {'title': '4x16GB DDR3', 'asking_price_cents': None}) == 3000
    assert 1 <= opening_offer({**WATCH, 'max_total_cents': 100}, {'title': '4x16GB', 'asking_price_cents': 4500}) <= 100


def test_model_cannot_turn_opening_into_sellers_asking_price(monkeypatch):
    from leon_control_plane.shopper_runtime import contact_decision
    monkeypatch.setattr('leon_control_plane.shopper_runtime.model_json', lambda prompt: (
        {'candidate_index': 0, 'offer_cents': 4500, 'reason': 'Model proposed asking price'}, 'test-local'))
    listing = {'title': '5x SK hynix 16GB DDR3 ECC', 'asking_price_cents': 4500,
               'capacity_gb': 80, 'usable_capacity_gb': 64, 'notes': []}
    result = contact_decision({**WATCH, 'preferred_ram_gb': 128}, [listing])
    assert result['offer_cents'] == 3000
