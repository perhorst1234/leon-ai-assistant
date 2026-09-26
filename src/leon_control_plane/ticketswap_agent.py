"""Read-only TicketSwap search planning for personal ticket use."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable


@dataclass(frozen=True)
class TicketListing:
    listing_id: str
    event: str
    venue: str
    event_at: datetime
    url: str
    total_cents: int
    quantity: int = 1
    seller_verified: bool | None = None


@dataclass(frozen=True)
class TicketSearch:
    event_query: str
    max_total_cents: int | None = None
    quantity: int = 1
    before: datetime | None = None


@dataclass(frozen=True)
class TicketResult:
    listing: TicketListing
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class TicketWatch:
    watch_id: str
    search: TicketSearch
    next_run_at: datetime
    enabled: bool = True


def rank_ticket_listings(listings: Iterable[TicketListing], search: TicketSearch) -> tuple[TicketResult, ...]:
    query = search.event_query.casefold().strip()
    results: list[TicketResult] = []
    for listing in listings:
        if listing.quantity < search.quantity or listing.total_cents < 0:
            continue
        if query and query not in listing.event.casefold():
            continue
        if search.max_total_cents is not None and listing.total_cents > search.max_total_cents:
            continue
        if search.before and listing.event_at > search.before:
            continue
        reasons = [f"€{listing.total_cents / 100:.2f}".replace(".", ",")]
        score = 100.0 - listing.total_cents / 100_000
        if listing.seller_verified:
            score += 5
            reasons.append("geverifieerde verkoper")
        results.append(TicketResult(listing, round(score, 3), tuple(reasons)))
    return tuple(sorted(results, key=lambda item: (-item.score, item.listing.total_cents, item.listing.listing_id)))


def make_ticket_watch(watch_id: str, search: TicketSearch, *, now: datetime | None = None) -> TicketWatch:
    if not watch_id or search.quantity < 1:
        raise ValueError("watch_id and quantity are invalid")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return TicketWatch(watch_id, search, current + timedelta(days=7))

