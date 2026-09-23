import pytest

from app.enums import CarType
from app.models import Location
from app.pricing.surge import DemandSupplySurgeStrategy, NoSurgeStrategy, area_id_for


def test_no_surge_strategy_is_always_1x():
    assert NoSurgeStrategy().get_multiplier("any-area") == 1.0


def test_demand_supply_surge_increases_with_demand_pressure():
    surge = DemandSupplySurgeStrategy(base_multiplier=1.0, step=0.5, max_multiplier=3.0)
    area = area_id_for(Location(0, 0))
    surge.record_supply(area, 2)
    surge.record_demand(area, 5)
    assert surge.get_multiplier(area) > 1.0


def test_surge_multiplier_caps_at_configured_max():
    surge = DemandSupplySurgeStrategy(base_multiplier=1.0, step=1.0, max_multiplier=2.5)
    area = area_id_for(Location(0, 0))
    surge.record_supply(area, 1)
    surge.record_demand(area, 100)
    assert surge.get_multiplier(area) == 2.5


def test_surge_with_no_demand_recorded_is_base_multiplier():
    surge = DemandSupplySurgeStrategy(base_multiplier=1.0)
    area = area_id_for(Location(0, 0))
    surge.record_supply(area, 5)
    assert surge.get_multiplier(area) == 1.0


def test_surge_multiplier_flows_into_final_fare(container):
    c = container
    surge = DemandSupplySurgeStrategy(base_multiplier=2.0, step=0.0)  # fixed 2x for a clean assertion
    c.ride_service.set_surge_strategy(surge)

    user = c.user_service.register_user("A", "1")
    c.driver_service.register_driver("D", "1", CarType.SEDAN, Location(0.001, 0.001))

    ride = c.ride_service.book_ride(user.id, Location(0, 0), CarType.SEDAN, radius_km=5)
    assert ride.surge_multiplier == 2.0

    ended = c.ride_service.end_ride(ride.id, Location(0.1, 0.1))
    # base_fare/final_fare are independently rounded from the unrounded
    # intermediate fare, so allow a one-cent tolerance for rounding.
    assert ended.final_fare == pytest.approx(ended.base_fare * 2.0, abs=0.02)
