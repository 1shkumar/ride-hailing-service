"""
Domain models. Plain dataclasses on purpose — the domain layer stays free of
any web-framework or persistence concern. Pydantic only shows up at the API
edge (app/schemas.py), never here.
"""
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.enums import CarType, CabStatus, RideStatus, DiscountType

EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class Location:
    lat: float
    lon: float

    def distance_km(self, other: "Location") -> float:
        """Great-circle (haversine) distance. Straight-line, not road distance —
        see README assumptions."""
        lat1, lon1, lat2, lon2 = map(math.radians, [self.lat, self.lon, other.lat, other.lon])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(min(1.0, math.sqrt(a)))
        return EARTH_RADIUS_KM * c


@dataclass
class User:
    name: str
    phone: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Driver:
    name: str
    phone: str
    car_type: CarType
    rating: float = 5.0
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Cab:
    """A driver's vehicle. One driver <-> one cab (see README assumptions)."""
    driver_id: str
    car_type: CarType
    location: Location
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: CabStatus = CabStatus.AVAILABLE


@dataclass
class Coupon:
    code: str
    discount_type: DiscountType
    value: float
    max_discount: Optional[float] = None
    active: bool = True


@dataclass
class Ride:
    user_id: str
    driver_id: str
    cab_id: str
    car_type_requested: CarType
    car_type_assigned: CarType
    pickup_location: Location
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    drop_location: Optional[Location] = None
    status: RideStatus = RideStatus.ONGOING
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    distance_km: Optional[float] = None
    base_fare: Optional[float] = None
    surge_multiplier: float = 1.0
    coupon_code: Optional[str] = None
    discount_amount: float = 0.0
    final_fare: Optional[float] = None
    cancellation_fee: Optional[float] = None