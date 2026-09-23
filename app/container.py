"""
Manual dependency wiring. Kept as one small factory function rather than a DI
framework — this app is small enough that a framework would add ceremony
without adding value. `build_container()` is called once by main.py for the
live app, and fresh by every test that needs an isolated in-memory world.
"""
from dataclasses import dataclass
from typing import Optional

from app.coupons.service import CouponService
from app.matching.strategy import MatchingStrategy, NearestDriverStrategy
from app.pricing.registry import PricingRegistry
from app.pricing.surge import NoSurgeStrategy, SurgeStrategy
from app.repositories import (
    CabRepository,
    CouponRepository,
    DriverRepository,
    RideRepository,
    UserRepository,
)
from app.services.driver_service import DriverService
from app.services.ride_service import CancellationPolicy, RideService
from app.services.user_service import UserService


@dataclass
class Container:
    user_repo: UserRepository
    driver_repo: DriverRepository
    cab_repo: CabRepository
    ride_repo: RideRepository
    coupon_repo: CouponRepository
    user_service: UserService
    driver_service: DriverService
    coupon_service: CouponService
    pricing_registry: PricingRegistry
    ride_service: RideService


def build_container(
    matching_strategy: Optional[MatchingStrategy] = None,
    surge_strategy: Optional[SurgeStrategy] = None,
    cancellation_policy: Optional[CancellationPolicy] = None,
) -> Container:
    user_repo = UserRepository()
    driver_repo = DriverRepository()
    cab_repo = CabRepository()
    ride_repo = RideRepository()
    coupon_repo = CouponRepository()

    user_service = UserService(user_repo)
    driver_service = DriverService(driver_repo, cab_repo)
    coupon_service = CouponService(coupon_repo)
    pricing_registry = PricingRegistry()

    ride_service = RideService(
        user_repo,
        driver_repo,
        cab_repo,
        ride_repo,
        pricing_registry,
        coupon_service,
        matching_strategy=matching_strategy or NearestDriverStrategy(),
        surge_strategy=surge_strategy or NoSurgeStrategy(),
        cancellation_policy=cancellation_policy or CancellationPolicy(),
    )

    return Container(
        user_repo=user_repo,
        driver_repo=driver_repo,
        cab_repo=cab_repo,
        ride_repo=ride_repo,
        coupon_repo=coupon_repo,
        user_service=user_service,
        driver_service=driver_service,
        coupon_service=coupon_service,
        pricing_registry=pricing_registry,
        ride_service=ride_service,
    )
