from datetime import datetime, timezone

from leon_control_plane.shopper_agent import (
    Listing,
    ShopperPreferences,
    build_offer_proposal,
    learn_tone,
    make_weekly_watch,
    rank_listings,
)


def _listing(item_id: str, title: str, price: int, **kwargs) -> Listing:
    return Listing("marktplaats", item_id, title, f"https://www.marktplaats.nl/v/{item_id}", price, **kwargs)


def test_rank_listings_filters_and_scores_deterministically():
    preferences = ShopperPreferences(
        query="sony camera", max_total_cents=50000, required_terms=("sony",), excluded_terms=("defect",),
        preferred_conditions=("zo goed als nieuw",), target_total_cents=40000,
    )
    listings = [
        _listing("b", "Sony camera zo goed als nieuw", 39000, condition="Zo goed als nieuw", seller_rating=4.8),
        _listing("a", "Sony camera defect", 10000, condition="Gebruikt"),
        _listing("c", "Andere camera", 30000),
    ]
    result = rank_listings(listings, preferences)
    assert [item.listing.listing_id for item in result] == ["b"]
    assert "voorkeursstaat" in result[0].reasons


def test_offer_is_reviewable_and_never_implicitly_executed():
    listing = _listing("x", "Sony camera", 10000, shipping_cents=500)
    proposal = build_offer_proposal(listing, ShopperPreferences("sony", opening_discount_percent=20))
    assert proposal.suggested_offer_cents == 8400
    assert proposal.approval_required is True
    assert proposal.action == "send_message"
    assert "€84,00" in proposal.message


def test_weekly_watch_and_tone_learning_are_bounded():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    watch = make_weekly_watch("camera-watch", ShopperPreferences("camera"), now=now)
    assert watch.next_run_at.isoformat() == "2026-01-08T00:00:00+00:00"
    tone = learn_tone(["Hoi, bedankt voor je reactie!", "Hoi, is 50 euro mogelijk?"])
    assert tone.greeting == "Hoi"
    assert tone.signoff == "Bedankt!"

