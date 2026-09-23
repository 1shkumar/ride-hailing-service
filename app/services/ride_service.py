"""
RideService orchestrates booking, ending and cancelling rides. It is the one
place that knows about matching, pricing, surge and coupons together — but it
only ever talks to each of them through their narrow interface
(order_candidates / calculate_fare / get_multiplier / compute_discount), so
swapping any one of them out doesn't change this file.

Concurrency: booking two users onto the same single available cab is the
classic race in this problem. We give every cab its own threading.Lock
(created lazily, guarded by a small dict lock) and only mark a cab BUSY while
holding *that cab's* lock, after re-checking it's still AVAILABLE. This is
fine-grained: two bookings for two different cabs never block each other,
only two bookings racing for the *same* cab do. See README for how this would
change with a real database (row-level locks / optimistic concurrency
instead of in-process locks, since there could be multiple server processes).
"""
import threading
from datetime import datetime, timezone
from typing import Dict, Optional

from app.coupons.service import CouponService
from app.enums import CabStatus, CarType, RideStatus
from app.exceptions import (
    DriverNotFound,
    InvalidRideState,
    NoDriverAvailable,
    RideNotFound,
    UserNotFound,
)
from app.matching.strategy import MatchingStrategy, NearestDriverStrategy
from app.models import Location, Ride
from app.pricing.registry import PricingRegistry
from app.pricing.surge import NoSurgeStrategy, SurgeStrategy, area_id_for


class CancellationPolicy:
    """
    Bonus: cancellation-fee policy, pluggable so a different policy can be
    swapped in without touching RideService.cancel_ride.

    Chosen policy (documented assumption, spec doesn't specify one): free
    cancellation within `grace_period_seconds` of booking (the driver hasn't
    had time to travel far), a flat `cancellation_fee` after that.
    """

    def __init__(self, grace_period_seconds: int = 60, cancellation_fee: float = 20.0):
        self.grace_period_seconds = grace_period_seconds
        self.cancellation_fee = cancellation_fee

    def compute_fee(self, ride: Ride, cancel_time: datetime) -> float:
        elapsed = (cancel_time - ride.start_time).total_seconds()
        # Strictly less-than: grace_period_seconds=0 must mean "no free
        # window at all", even if cancel happens in the same instant as
        # booking (elapsed == 0.0 on a fast machine). <= would incorrectly
        # treat that as still within a zero-length window.
        if elapsed < self.grace_period_seconds:
            return 0.0
        return self.cancellation_fee


class RideService:
    def __init__(
        self,
        user_repo,
        driver_repo,
        cab_repo,
        ride_repo,
        pricing_registry: PricingRegistry,
        coupon_service: CouponService,
        matching_strategy: Optional[MatchingStrategy] = None,
        surge_strategy: Optional[SurgeStrategy] = None,
        cancellation_policy: Optional[CancellationPolicy] = None,
    ):
        self._users = user_repo
        self._drivers = driver_repo
        self._cabs = cab_repo
        self._rides = ride_repo
        self._pricing = pricing_registry
        self._coupons = coupon_service
        self._matching = matching_strategy or NearestDriverStrategy()
        self._surge = surge_strategy or NoSurgeStrategy()
        self._cancellation_policy = cancellation_policy or CancellationPolicy()

        self._cab_locks: Dict[str, threading.Lock] = {}
        self._cab_locks_guard = threading.Lock()

    # -- configuration seams (bonus requirement: switchable without touching
    # booking logic) --------------------------------------------------------
    def set_matching_strategy(self, strategy: MatchingStrategy) -> None:
        self._matching = strategy

    def set_surge_strategy(self, strategy: SurgeStrategy) -> None:
        self._surge = strategy

    # -- internal helpers -----------------------------------------------
    def _lock_for(self, cab_id: str) -> threading.Lock:
        with self._cab_locks_guard:
            if cab_id not in self._cab_locks:
                self._cab_locks[cab_id] = threading.Lock()
            return self._cab_locks[cab_id]

    def _find_cab_for_driver(self, driver_id: str):
        for cab in self._cabs.all():
            if cab.driver_id == driver_id:
                return cab
        return None

    def _find_and_claim_cab(self, pickup: Location, car_type: CarType, radius_km: float):
        """Finds a cab and atomically flips it to BUSY, or raises
        NoDriverAvailable. Tries the requested car type first; if it's a
        Hatchback request with none available, falls back to Sedan (the
        "free upgrade" case) — fare is still charged at Hatchback rates,
        enforced later in end_ride via car_type_requested."""
        search_order = [car_type]
        if car_type == CarType.HATCHBACK:
            search_order.append(CarType.SEDAN)

        for candidate_type in search_order:
            cabs = self._cabs.find_available_in_radius(pickup, radius_km, car_type=candidate_type)
            ordered = self._matching.order_candidates(cabs, pickup)
            for cab in ordered:
                lock = self._lock_for(cab.id)
                with lock:
                    if cab.status == CabStatus.AVAILABLE:
                        cab.status = CabStatus.BUSY
                        return candidate_type, cab
                # else: someone else claimed it between the radius scan and
                # the lock; move on to the next candidate.

        raise NoDriverAvailable(
            f"No {car_type.value} (or eligible upgrade) available within {radius_km}km"
        )

    # -- driver/cab -------------------------------------------------------
    def update_cab_location(self, driver_id: str, location: Location):
        driver = self._drivers.get(driver_id)
        if not driver:
            raise DriverNotFound(driver_id)
        cab = self._find_cab_for_driver(driver_id)
        if not cab:
            raise DriverNotFound(f"No cab registered for driver {driver_id}")
        cab.location = location
        return cab

    # -- booking ------------------------------------------------------------
    def book_ride(
        self,
        user_id: str,
        pickup: Location,
        car_type: CarType,
        radius_km: float,
        coupon_code: Optional[str] = None,
    ) -> Ride:
        user = self._users.get(user_id)
        if not user:
            raise UserNotFound(user_id)

        car_type_assigned, cab = self._find_and_claim_cab(pickup, car_type, radius_km)
        driver = self._drivers.get(cab.driver_id)

        area_id = area_id_for(pickup)
        if hasattr(self._surge, "record_demand"):
            self._surge.record_demand(area_id)
        surge_multiplier = self._surge.get_multiplier(area_id)

        if coupon_code:
            # Validate eagerly (fail fast) against the minimum fare for the
            # requested car type. The *actual* discount amount is computed
            # against the real final fare in end_ride, once distance is known.
            self._coupons.compute_discount(coupon_code, fare=self._pricing.get(car_type).minimum_fare)

        ride = Ride(
            user_id=user_id,
            driver_id=driver.id,
            cab_id=cab.id,
            car_type_requested=car_type,
            car_type_assigned=car_type_assigned,
            pickup_location=pickup,
            surge_multiplier=surge_multiplier,
            coupon_code=coupon_code,
        )
        self._rides.add(ride)
        return ride

    # -- ending ---------------------------------------------------------
    def end_ride(self, ride_id: str, drop_location: Location) -> Ride:
        ride = self._rides.get(ride_id)
        if not ride:
            raise RideNotFound(ride_id)
        if ride.status != RideStatus.ONGOING:
            raise InvalidRideState(f"Ride {ride_id} is not ongoing (status={ride.status.value})")

        distance = ride.pickup_location.distance_km(drop_location)

        # Priced off car_type_requested (not car_type_assigned): this is what
        # makes a Hatchback-upgraded-to-Sedan ride "free" — the rider always
        # pays what they originally asked for.
        strategy = self._pricing.get(ride.car_type_requested)
        base_fare = strategy.calculate_fare(distance)
        surged_fare = base_fare * ride.surge_multiplier

        discount = 0.0
        if ride.coupon_code:
            discount = self._coupons.compute_discount(ride.coupon_code, surged_fare)

        final_fare = round(max(surged_fare - discount, 0), 2)

        ride.drop_location = drop_location
        ride.end_time = datetime.now(timezone.utc)
        ride.distance_km = round(distance, 3)
        ride.base_fare = round(base_fare, 2)
        ride.discount_amount = round(discount, 2)
        ride.final_fare = final_fare
        ride.status = RideStatus.COMPLETED

        self._release_cab(ride.cab_id)
        return ride

    # -- cancellation (bonus) -----------------------------------------------
    def cancel_ride(self, ride_id: str) -> Ride:
        ride = self._rides.get(ride_id)
        if not ride:
            raise RideNotFound(ride_id)
        if ride.status != RideStatus.ONGOING:
            raise InvalidRideState(f"Ride {ride_id} is not ongoing (status={ride.status.value})")

        cancel_time = datetime.now(timezone.utc)
        fee = self._cancellation_policy.compute_fee(ride, cancel_time)

        ride.status = RideStatus.CANCELLED
        ride.end_time = cancel_time
        ride.cancellation_fee = fee

        self._release_cab(ride.cab_id)
        return ride

    def _release_cab(self, cab_id: str) -> None:
        cab = self._cabs.get(cab_id)
        if cab:
            with self._lock_for(cab.id):
                cab.status = CabStatus.AVAILABLE

    # -- history --------------------------------------------------------
    def user_ride_history(self, user_id: str):
        if not self._users.get(user_id):
            raise UserNotFound(user_id)
        rides = self._rides.for_user(user_id)
        return self._split_history(rides)

    def driver_ride_history(self, driver_id: str):
        if not self._drivers.get(driver_id):
            raise DriverNotFound(driver_id)
        rides = self._rides.for_driver(driver_id)
        return self._split_history(rides)

    @staticmethod
    def _split_history(rides):
        return {
            "ongoing": [r for r in rides if r.status == RideStatus.ONGOING],
            "completed": [r for r in rides if r.status in (RideStatus.COMPLETED, RideStatus.CANCELLED)],
        }
