"""
Pricing strategies. A PricingStrategy takes a distance and returns a fare —
that's the entire seam. Tiered, per-km-bracket pricing is the only
implementation the spec asks for, but a flat-rate or per-minute strategy could
be added here without touching anything else (RideService only ever calls
`strategy.calculate_fare(distance_km)`).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class PricingTier:
    """A bracket [previous_boundary, upto_km) billed at rate_per_km.
    upto_km=None means "and beyond" — must be the last tier."""
    upto_km: Optional[float]
    rate_per_km: float


class PricingStrategy(ABC):
    @abstractmethod
    def calculate_fare(self, distance_km: float) -> float:
        ...


class TieredPricingStrategy(PricingStrategy):
    """
    Bracketed pricing, like income-tax slabs: each tier only charges its own
    rate for the portion of distance that falls in it, not the whole trip.

    Example from the spec (minimum ₹50; first 2km @ ₹10/km; 3-5km @ ₹8/km;
    6km+ @ ₹5/km) is expressed as tiers with boundaries at 2 and 5:
        [0-2km] @ 10, [2-5km] @ 8 (i.e. 3km width), [5km+] @ 5
    A flat `minimum_fare` is then applied as a floor over the computed amount.
    """

    def __init__(self, minimum_fare: float, tiers: List[PricingTier]):
        if not tiers:
            raise ValueError("At least one pricing tier is required")
        if tiers[-1].upto_km is not None:
            raise ValueError("Last pricing tier must be open-ended (upto_km=None)")
        self.minimum_fare = minimum_fare
        self.tiers = tiers

    def calculate_fare(self, distance_km: float) -> float:
        if distance_km < 0:
            raise ValueError("distance_km cannot be negative")

        remaining = distance_km
        prev_boundary = 0.0
        fare = 0.0

        for tier in self.tiers:
            if remaining <= 0:
                break
            if tier.upto_km is None:
                tier_km = remaining
            else:
                tier_width = tier.upto_km - prev_boundary
                tier_km = min(remaining, tier_width)
                prev_boundary = tier.upto_km

            fare += tier_km * tier.rate_per_km
            remaining -= tier_km

        return max(fare, self.minimum_fare)
