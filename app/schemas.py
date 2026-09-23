"""
Pydantic models for the HTTP edge only. Deliberately kept out of app/models.py
so the domain layer has no dependency on the web framework.
"""
from typing import Optional

from pydantic import BaseModel

from app.enums import CarType, DiscountType, RideStatus


class RegisterUserRequest(BaseModel):
    name: str
    phone: str


class UserOut(BaseModel):
    id: str
    name: str
    phone: str

    @classmethod
    def from_model(cls, user):
        return cls(id=user.id, name=user.name, phone=user.phone)


class RegisterDriverRequest(BaseModel):
    name: str
    phone: str
    car_type: CarType
    lat: float
    lon: float
    rating: float = 5.0


class DriverOut(BaseModel):
    id: str
    name: str
    phone: str
    car_type: CarType
    rating: float
    cab_id: str

    @classmethod
    def from_model(cls, driver, cab):
        return cls(
            id=driver.id,
            name=driver.name,
            phone=driver.phone,
            car_type=driver.car_type,
            rating=driver.rating,
            cab_id=cab.id,
        )


class LocationUpdate(BaseModel):
    lat: float
    lon: float


class BookRideRequest(BaseModel):
    user_id: str
    pickup_lat: float
    pickup_lon: float
    car_type: CarType
    radius_km: float = 5.0
    coupon_code: Optional[str] = None


class EndRideRequest(BaseModel):
    drop_lat: float
    drop_lon: float


class RideOut(BaseModel):
    id: str
    user_id: str
    driver_id: str
    cab_id: str
    car_type_requested: CarType
    car_type_assigned: CarType
    status: RideStatus
    distance_km: Optional[float] = None
    base_fare: Optional[float] = None
    surge_multiplier: float
    coupon_code: Optional[str] = None
    discount_amount: float
    final_fare: Optional[float] = None
    cancellation_fee: Optional[float] = None

    @classmethod
    def from_model(cls, ride):
        return cls(
            id=ride.id,
            user_id=ride.user_id,
            driver_id=ride.driver_id,
            cab_id=ride.cab_id,
            car_type_requested=ride.car_type_requested,
            car_type_assigned=ride.car_type_assigned,
            status=ride.status,
            distance_km=ride.distance_km,
            base_fare=ride.base_fare,
            surge_multiplier=ride.surge_multiplier,
            coupon_code=ride.coupon_code,
            discount_amount=ride.discount_amount,
            final_fare=ride.final_fare,
            cancellation_fee=ride.cancellation_fee,
        )


class RideHistoryOut(BaseModel):
    ongoing: list[RideOut]
    completed: list[RideOut]


class AddCouponRequest(BaseModel):
    code: str
    discount_type: DiscountType
    value: float
    max_discount: Optional[float] = None


class CouponOut(BaseModel):
    code: str
    discount_type: DiscountType
    value: float
    max_discount: Optional[float] = None

    @classmethod
    def from_model(cls, coupon):
        return cls(
            code=coupon.code,
            discount_type=coupon.discount_type,
            value=coupon.value,
            max_discount=coupon.max_discount,
        )
