"""
Maps a CarType to the PricingStrategy that prices it. This is the single seam
for "add a new car type's pricing" — register a strategy here, nothing in
RideService changes. Adding a wholly new *kind* of pricing (e.g. per-minute)
means adding a new PricingStrategy subclass in strategy.py and registering an
instance of it here; still a two-file change, still zero changes to booking
logic.
"""
from typing import Dict, Optional

from app.enums import CarType
from app.pricing.strategy import PricingStrategy, TieredPricingStrategy, PricingTier


def default_pricing_registry() -> Dict[CarType, PricingStrategy]:
    return {
        # Sedan rates are exactly the example given in the spec.
        CarType.SEDAN: TieredPricingStrategy(
            minimum_fare=50,
            tiers=[
                PricingTier(upto_km=2, rate_per_km=10),
                PricingTier(upto_km=5, rate_per_km=8),
                PricingTier(upto_km=None, rate_per_km=5),
            ],
        ),
        # Hatchback rates are our own assumption (not given in the spec):
        # cheaper than Sedan at every tier, mirroring real-world ride-hailing
        # pricing where Hatchback < Sedan. See README "Assumptions".
        CarType.HATCHBACK: TieredPricingStrategy(
            minimum_fare=40,
            tiers=[
                PricingTier(upto_km=2, rate_per_km=8),
                PricingTier(upto_km=5, rate_per_km=6),
                PricingTier(upto_km=None, rate_per_km=4),
            ],
        ),
    }


class PricingRegistry:
    def __init__(self, strategies: Optional[Dict[CarType, PricingStrategy]] = None):
        self._strategies = strategies if strategies is not None else default_pricing_registry()

    def get(self, car_type: CarType) -> PricingStrategy:
        try:
            return self._strategies[car_type]
        except KeyError:
            raise ValueError(f"No pricing strategy registered for car type {car_type!r}")

    def register(self, car_type: CarType, strategy: PricingStrategy) -> None:
        self._strategies[car_type] = strategy
