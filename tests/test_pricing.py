import pytest

from app.enums import CarType
from app.pricing.registry import PricingRegistry, default_pricing_registry
from app.pricing.strategy import PricingTier, TieredPricingStrategy


def test_minimum_fare_enforced_for_short_ride():
    strategy = TieredPricingStrategy(
        minimum_fare=50,
        tiers=[
            PricingTier(upto_km=2, rate_per_km=10),
            PricingTier(upto_km=5, rate_per_km=8),
            PricingTier(upto_km=None, rate_per_km=5),
        ],
    )
    # 1km * 10/km = 10, well below the 50 minimum fare.
    assert strategy.calculate_fare(1) == 50


def test_sedan_tier_boundaries_match_spec_example():
    sedan = default_pricing_registry()[CarType.SEDAN]
    # 2km: 2*10 = 20 -> below minimum fare -> 50
    assert sedan.calculate_fare(2) == 50
    # 5km: 2*10 + 3*8 = 44 -> still below minimum fare -> 50
    assert sedan.calculate_fare(5) == 50
    # 10km: 2*10 + 3*8 + 5*5 = 20 + 24 + 25 = 69
    assert sedan.calculate_fare(10) == 69
    # 20km: 20 + 24 + 15*5 = 20 + 24 + 75 = 119
    assert sedan.calculate_fare(20) == 119


def test_zero_distance_charges_minimum_fare():
    sedan = default_pricing_registry()[CarType.SEDAN]
    assert sedan.calculate_fare(0) == 50


def test_hatchback_is_cheaper_than_sedan_at_every_distance():
    registry = default_pricing_registry()
    sedan = registry[CarType.SEDAN]
    hatchback = registry[CarType.HATCHBACK]
    for distance in [0.5, 1, 2, 3, 5, 7.5, 10, 25]:
        assert hatchback.calculate_fare(distance) <= sedan.calculate_fare(distance)
    # And strictly cheaper once we're clear of both minimum fares.
    assert hatchback.calculate_fare(10) < sedan.calculate_fare(10)


def test_negative_distance_rejected():
    sedan = default_pricing_registry()[CarType.SEDAN]
    with pytest.raises(ValueError):
        sedan.calculate_fare(-1)


def test_pricing_registry_lookup_by_car_type():
    registry = PricingRegistry()
    sedan_strategy = registry.get(CarType.SEDAN)
    hatchback_strategy = registry.get(CarType.HATCHBACK)
    assert sedan_strategy is not hatchback_strategy


def test_pricing_registry_register_new_strategy():
    registry = PricingRegistry()
    custom = TieredPricingStrategy(minimum_fare=999, tiers=[PricingTier(upto_km=None, rate_per_km=1)])
    registry.register(CarType.SEDAN, custom)
    assert registry.get(CarType.SEDAN) is custom
    assert registry.get(CarType.SEDAN).calculate_fare(1) == 999


def test_strategy_rejects_tiers_without_open_ended_last_tier():
    with pytest.raises(ValueError):
        TieredPricingStrategy(minimum_fare=10, tiers=[PricingTier(upto_km=5, rate_per_km=10)])


def test_strategy_rejects_empty_tiers():
    with pytest.raises(ValueError):
        TieredPricingStrategy(minimum_fare=10, tiers=[])
