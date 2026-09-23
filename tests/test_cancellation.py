import pytest

from app.container import build_container
from app.enums import CabStatus, CarType, RideStatus
from app.exceptions import InvalidRideState
from app.models import Location
from app.services.ride_service import CancellationPolicy


def _setup(cancellation_policy):
    c = build_container(cancellation_policy=cancellation_policy)
    user = c.user_service.register_user("A", "1")
    driver, cab = c.driver_service.register_driver("D", "1", CarType.SEDAN, Location(0.001, 0.001))
    ride = c.ride_service.book_ride(user.id, Location(0, 0), CarType.SEDAN, radius_km=5)
    return c, ride, cab


def test_free_cancellation_within_grace_period():
    c, ride, cab = _setup(CancellationPolicy(grace_period_seconds=300, cancellation_fee=20))
    cancelled = c.ride_service.cancel_ride(ride.id)
    assert cancelled.cancellation_fee == 0.0
    assert cancelled.status == RideStatus.CANCELLED


def test_flat_fee_charged_after_grace_period():
    # grace_period_seconds=0 means "any cancellation is already past the grace window"
    c, ride, cab = _setup(CancellationPolicy(grace_period_seconds=0, cancellation_fee=25))
    cancelled = c.ride_service.cancel_ride(ride.id)
    assert cancelled.cancellation_fee == 25


def test_cab_is_freed_after_cancellation():
    c, ride, cab = _setup(CancellationPolicy(grace_period_seconds=300))
    assert cab.status == CabStatus.BUSY
    c.ride_service.cancel_ride(ride.id)
    assert cab.status == CabStatus.AVAILABLE


def test_cannot_cancel_a_ride_twice():
    c, ride, cab = _setup(CancellationPolicy())
    c.ride_service.cancel_ride(ride.id)
    with pytest.raises(InvalidRideState):
        c.ride_service.cancel_ride(ride.id)


def test_cannot_cancel_a_completed_ride():
    c, ride, cab = _setup(CancellationPolicy())
    c.ride_service.end_ride(ride.id, Location(0.05, 0.05))
    with pytest.raises(InvalidRideState):
        c.ride_service.cancel_ride(ride.id)
