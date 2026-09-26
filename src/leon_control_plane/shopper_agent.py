"""Bounded marketplace shopper planning primitives.

This module deliberately has no network or account access.  It turns approved
listing data into a ranked shortlist and a reviewable offer proposal.  Sending
messages, bidding, liking or buying remains an explicit approval action in the
control plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import re
from typing import Iterable, Mapping


PLATFORMS = frozenset({"marktplaats", "vinted"})


@dataclass(frozen=True)
class Listing:
    platform: str
    listing_id: str
    title: str
    url: str
    price_cents: int
    shipping_cents: int = 0
    condition: str = "unknown"
    seller_rating: float | None = None
    seller_reviews: int | None = None
    published_at: datetime | None = None
    description: str = ""

    @property
    def total_cents(self) -> int:
        return self.price_cents + self.shipping_cents


@dataclass(frozen=True)
class ShopperPreferences:
    query: str
    max_total_cents: int | None = None
    preferred_conditions: tuple[str, ...] = ()
    required_terms: tuple[str, ...] = ()
    excluded_terms: tuple[str, ...] = ()
    target_total_cents: int | None = None
    opening_discount_percent: int = 10
    cadence_days: int = 7


@dataclass(frozen=True)
class ToneProfile:
    """A small, explainable style profile derived from user supplied examples."""

    greeting: str = "Hoi"
    signoff: str = "Bedankt!"
    concise: bool = True
    friendly_decline: str = "Hoi, bedankt voor je reactie. Ik sla deze even over, succes met de verkoop!"
    offer_template: str = "Hoi, ik heb interesse. Zou je {amount} inclusief verzending willen overwegen? Geen probleem als dat niet uitkomt."


@dataclass(frozen=True)
class DealScore:
    listing: Listing
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class DealProposal:
    listing: Listing
    suggested_offer_cents: int
    message: str
    action: str = "send_message"
    approval_required: bool = True
    approval_reason: str = "Extern bericht of bod op een marktplaatsaccount"


@dataclass(frozen=True)
class WeeklyWatch:
    watch_id: str
    preferences: ShopperPreferences
    next_run_at: datetime
    enabled: bool = True


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _money(cents: int) -> str:
    return f"€{cents / 100:.2f}".replace(".", ",")


def rank_listings(listings: Iterable[Listing], preferences: ShopperPreferences) -> tuple[DealScore, ...]:
    """Rank listings deterministically, filtering hard constraints first."""
    query_terms = tuple(term for term in _normalise(preferences.query).split() if term)
    required = tuple(_normalise(term) for term in preferences.required_terms)
    excluded = tuple(_normalise(term) for term in preferences.excluded_terms)
    conditions = {_normalise(item) for item in preferences.preferred_conditions}
    ranked: list[DealScore] = []
    for listing in listings:
        if listing.platform not in PLATFORMS or listing.price_cents < 0 or listing.shipping_cents < 0:
            continue
        haystack = _normalise(f"{listing.title} {listing.description}")
        if any(term not in haystack for term in required) or any(term in haystack for term in excluded):
            continue
        if preferences.max_total_cents is not None and listing.total_cents > preferences.max_total_cents:
            continue
        score = 0.0
        reasons: list[str] = []
        matched = sum(term in haystack for term in query_terms)
        score += matched * 25
        if matched == len(query_terms) and query_terms:
            reasons.append("alle zoektermen gevonden")
        if conditions and _normalise(listing.condition) in conditions:
            score += 12
            reasons.append("voorkeursstaat")
        if preferences.target_total_cents:
            delta = abs(listing.total_cents - preferences.target_total_cents)
            score += max(0.0, 20.0 - (delta / max(preferences.target_total_cents, 1) * 20.0))
        if listing.seller_rating is not None:
            score += min(max(listing.seller_rating, 0.0), 5.0) * 3
            reasons.append(f"verkoperscore {listing.seller_rating:.1f}")
        score -= listing.total_cents / 100_000
        reasons.append(f"totaal {_money(listing.total_cents)}")
        ranked.append(DealScore(listing, round(score, 3), tuple(reasons)))
    return tuple(sorted(ranked, key=lambda item: (-item.score, item.listing.total_cents, item.listing.listing_id)))


def build_offer_proposal(listing: Listing, preferences: ShopperPreferences, tone: ToneProfile = ToneProfile()) -> DealProposal:
    discount = min(max(preferences.opening_discount_percent, 0), 50)
    offer = round(listing.total_cents * (100 - discount) / 100)
    if preferences.target_total_cents is not None:
        offer = min(offer, preferences.target_total_cents)
    offer = max(0, offer)
    message = tone.offer_template.format(amount=_money(offer))
    return DealProposal(listing=listing, suggested_offer_cents=offer, message=message)


def make_weekly_watch(watch_id: str, preferences: ShopperPreferences, *, now: datetime | None = None) -> WeeklyWatch:
    if not watch_id or preferences.cadence_days < 1 or preferences.cadence_days > 31:
        raise ValueError("watch_id and cadence_days are invalid")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return WeeklyWatch(watch_id, preferences, current + timedelta(days=preferences.cadence_days))


def learn_tone(examples: Iterable[str]) -> ToneProfile:
    """Extract only coarse style signals from bounded, user-provided examples."""
    samples = [example.strip() for example in examples if isinstance(example, str) and example.strip()]
    if not samples:
        return ToneProfile()
    joined = " ".join(samples)
    greeting = "Hoi" if re.search(r"\bhoi\b", joined, re.I) else "Hallo"
    signoff = "Bedankt!" if re.search(r"bedankt|dank", joined, re.I) else "Groet!"
    concise = sum(len(item.split()) for item in samples) / len(samples) <= 45
    return ToneProfile(greeting=greeting, signoff=signoff, concise=concise)

