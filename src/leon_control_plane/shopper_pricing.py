"""Owner's opening strategy: discount the wanted quantity, then negotiate."""
import re


def ram_bundle(title: str) -> tuple[int, int] | None:
    # Titles often put the brand between quantity and capacity: 5x SK hynix 16GB.
    match = re.search(r'\b(\d{1,2})\s*[x×]\s*[^,\n]{0,48}?(\d{1,3})\s*gb\b', title, re.I)
    if not match:
        return None
    count, size = int(match[1]), int(match[2])
    return (count, size) if count > 0 and size > 0 else None


def opening_offer(watch: dict, match: dict) -> int:
    budget = watch['max_total_cents']
    asking = match.get('asking_price_cents')
    bundle = ram_bundle(match['title'])
    if type(asking) is int and asking > 0:
        base = asking
        if bundle and watch.get('max_ram_sticks'):
            base = asking * min(bundle[0], watch['max_ram_sticks']) // bundle[0]
        discounted = base * 80 // 100
    else:
        base = budget
        discounted = budget * 60 // 100
    step = 500 if base >= 2000 else 100
    rounded = (discounted + step // 2) // step * step
    return max(1, min(rounded, budget, base - 1 if base > 1 else 1))
