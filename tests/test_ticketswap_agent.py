from datetime import datetime, timezone

from leon_control_plane.ticketswap_agent import TicketListing, TicketSearch, make_ticket_watch, rank_ticket_listings


def test_ticket_search_is_personal_use_read_only_and_ranked():
    event_at = datetime(2027, 2, 1, tzinfo=timezone.utc)
    listings = [
        TicketListing("b", "Concert X", "Hall", event_at, "https://ticketswap.nl/b", 8500, seller_verified=True),
        TicketListing("a", "Concert X", "Hall", event_at, "https://ticketswap.nl/a", 7000),
        TicketListing("c", "Other", "Hall", event_at, "https://ticketswap.nl/c", 1000),
    ]
    result = rank_ticket_listings(listings, TicketSearch("concert x", max_total_cents=9000))
    assert [item.listing.listing_id for item in result] == ["b", "a"]
    watch = make_ticket_watch("concert-x", TicketSearch("concert x"), now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert watch.next_run_at.isoformat() == "2026-01-08T00:00:00+00:00"

