import pytest

from app.enums import CabStatus, CarType, DiscountType
from app.exceptions import InvalidRideState, NoDriverAvailable
from app.models import Location


def _register_user(c, name="Alice"):
    return c.user_service.register_user(name, "9999999999")


def _register_driver(c, car_type, lat, lon, rating=5.0):
    return c.driver_service.register_driver("Bob", "8888888888", car_type, Location(lat, lon), rating)


class TestBookingRadius:
    def test_no_driver_within_radius_raises(self, container):
        c = container
        user = _register_user(c)
        _register_driver(c, CarType.SEDAN, lat=10.0, lon=10.0)  # far away
        with pytest.raises(NoDriverAvailable):
            c.ride_service.book_ride(user.id, Location(0, 0), CarType.SEDAN, radius_km=5)

    def test_driver_within_radius_is_booked(self, container):
        c = container
        user = _register_user(c)
        driver, cab = _register_driver(c, CarType.SEDAN, lat=0.01, lon=0.01)
        ride = c.ride_service.book_ride(user.id, Location(0, 0), CarType.SEDAN, radius_km=5)
        assert ride.driver_id == driver.id
        assert ride.cab_id == cab.id
        assert ride.car_type_assigned == CarType.SEDAN

    def test_booking_for_unknown_user_raises(self, container):
        c = container
        _register_driver(c, CarType.SEDAN, lat=0.001, lon=0.001)
        from app.exceptions import UserNotFound

        with pytest.raises(UserNotFound):
            c.ride_service.book_ride("no-such-user", Location(0, 0), CarType.SEDAN, radius_km=5)


class TestFreeUpgrade:
    def test_hatchback_upgrades_to_sedan_when_none_available(self, container):
        c = container
        user = _register_user(c)
        _register_driver(c, CarType.SEDAN, lat=0.01, lon=0.01)  # only a sedan nearby
        ride = c.ride_service.book_ride(user.id, Location(0, 0), CarType.HATCHBACK, radius_km=5)
        assert ride.car_type_requested == CarType.HATCHBACK
        assert ride.car_type_assigned == CarType.SEDAN

    def test_upgrade_is_charged_at_the_originally_requested_hatchback_rate(self, container):
        c = container
        user = _register_user(c)
        _register_driver(c, CarType.SEDAN, lat=0.001, lon=0.001)
        ride = c.ride_service.book_ride(user.id, Location(0, 0), CarType.HATCHBACK, radius_km=5)
        ended = c.ride_service.end_ride(ride.id, Location(0.05, 0.05))

        expected_fare = c.pricing_registry.get(CarType.HATCHBACK).calculate_fare(ended.distance_km)
        assert ended.base_fare == round(expected_fare, 2)
        # Sanity: this must differ from what a Sedan would have cost for the same trip.
        sedan_fare = c.pricing_registry.get(CarType.SEDAN).calculate_fare(ended.distance_km)
        assert ended.base_fare != round(sedan_fare, 2)

    def test_no_upgrade_offered_for_sedan_requests(self, container):
        c = container
        user = _register_user(c)
        _register_driver(c, CarType.HATCHBACK, lat=0.001, lon=0.001)  # only a hatchback nearby
        with pytest.raises(NoDriverAvailable):
            c.ride_service.book_ride(user.id, Location(0, 0), CarType.SEDAN, radius_km=5)


class TestEndRide:
    def test_end_ride_computes_distance_and_fare(self, container):
        c = container
        user = _register_user(c)
        _register_driver(c, CarType.SEDAN, lat=0.001, lon=0.001)
        ride = c.ride_service.book_ride(user.id, Location(0, 0), CarType.SEDAN, radius_km=5)
        ended = c.ride_service.end_ride(ride.id, Location(0.1, 0.1))
        assert ended.distance_km > 0
        assert ended.final_fare == ended.base_fare  # no coupon, no surge -> unchanged
        assert ended.status.value == "COMPLETED"

    def test_ending_a_ride_twice_raises(self, container):
        c = container
        user = _register_user(c)
        _register_driver(c, CarType.SEDAN, lat=0.001, lon=0.001)
        ride = c.ride_service.book_ride(user.id, Location(0, 0), CarType.SEDAN, radius_km=5)
        c.ride_service.end_ride(ride.id, Location(0.02, 0.02))
        with pytest.raises(InvalidRideState):
            c.ride_service.end_ride(ride.id, Location(0.02, 0.02))

    def test_cab_becomes_available_again_after_ride_ends(self, container):
        c = container
        user = _register_user(c)
        driver, cab = _register_driver(c, CarType.SEDAN, lat=0.001, lon=0.001)
        ride = c.ride_service.book_ride(user.id, Location(0, 0), CarType.SEDAN, radius_km=5)
        assert cab.status == CabStatus.BUSY
        c.ride_service.end_ride(ride.id, Location(0.02, 0.02))
        assert cab.status == CabStatus.AVAILABLE

    def test_freed_cab_can_be_rebooked(self, container):
        c = container
        user1 = _register_user(c, "Alice")
        user2 = _register_user(c, "Carol")
        _register_driver(c, CarType.SEDAN, lat=0.001, lon=0.001)
        ride1 = c.ride_service.book_ride(user1.id, Location(0, 0), CarType.SEDAN, radius_km=5)
        c.ride_service.end_ride(ride1.id, Location(0.01, 0.01))
        ride2 = c.ride_service.book_ride(user2.id, Location(0, 0), CarType.SEDAN, radius_km=5)
        assert ride2.cab_id == ride1.cab_id


class TestCouponOnRide:
    def test_flat_coupon_discount_applied_at_ride_end(self, container):
        c = container
        user = _register_user(c)
        _register_driver(c, CarType.SEDAN, lat=0.001, lon=0.001)
        c.coupon_service.add_coupon("SAVE10", DiscountType.FLAT, 10)
        ride = c.ride_service.book_ride(user.id, Location(0, 0), CarType.SEDAN, radius_km=5, coupon_code="SAVE10")
        ended = c.ride_service.end_ride(ride.id, Location(0.1, 0.1))
        assert ended.discount_amount == 10
        assert ended.final_fare == round(ended.base_fare - 10, 2)

    def test_invalid_coupon_at_booking_time_raises(self, container):
        from app.exceptions import InvalidCoupon

        c = container
        user = _register_user(c)
        _register_driver(c, CarType.SEDAN, lat=0.001, lon=0.001)
        with pytest.raises(InvalidCoupon):
            c.ride_service.book_ride(user.id, Location(0, 0), CarType.SEDAN, radius_km=5, coupon_code="NOPE")


class TestRideHistory:
    def test_history_splits_ongoing_and_completed(self, container):
        c = container
        user = _register_user(c)
        _register_driver(c, CarType.SEDAN, lat=0.001, lon=0.001)
        _register_driver(c, CarType.SEDAN, lat=0.002, lon=0.002)
        ride1 = c.ride_service.book_ride(user.id, Location(0, 0), CarType.SEDAN, radius_km=5)
        ride2 = c.ride_service.book_ride(user.id, Location(0, 0), CarType.SEDAN, radius_km=5)
        c.ride_service.end_ride(ride1.id, Location(0.01, 0.01))

        history = c.ride_service.user_ride_history(user.id)
        assert [r.id for r in history["ongoing"]] == [ride2.id]
        assert [r.id for r in history["completed"]] == [ride1.id]

    def test_driver_history_reflects_their_rides(self, container):
        c = container
        user = _register_user(c)
        driver, _ = _register_driver(c, CarType.SEDAN, lat=0.001, lon=0.001)
        ride = c.ride_service.book_ride(user.id, Location(0, 0), CarType.SEDAN, radius_km=5)
        history = c.ride_service.driver_ride_history(driver.id)
        assert [r.id for r in history["ongoing"]] == [ride.id]
