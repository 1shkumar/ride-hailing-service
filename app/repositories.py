"""
In-memory storage. Deliberately simple: a dict keyed by id, guarded by a lock
for mutation. This is NOT the lock that makes booking race-safe (that lives in
RideService, per-cab) — this one just protects the dict itself from concurrent
add/delete, which is a much smaller and separate concern.

Swapping this for a real database later means implementing the same methods
against SQLAlchemy/Postgres; nothing above this layer (services) would change.
"""
import threading
from typing import Dict, List, Optional

from app.enums import CabStatus, CarType
from app.models import Coupon, Location


class InMemoryRepository:
    def __init__(self):
        self._lock = threading.Lock()
        self._store: Dict[str, object] = {}

    def add(self, entity):
        with self._lock:
            self._store[entity.id] = entity
        return entity

    def get(self, entity_id: str):
        return self._store.get(entity_id)

    def all(self) -> List:
        return list(self._store.values())

    def delete(self, entity_id: str):
        with self._lock:
            self._store.pop(entity_id, None)


class UserRepository(InMemoryRepository):
    pass


class DriverRepository(InMemoryRepository):
    pass


class CabRepository(InMemoryRepository):
    def find_available_in_radius(self, location: Location, radius_km: float, car_type: Optional[CarType] = None):
        results = []
        for cab in self.all():
            if cab.status != CabStatus.AVAILABLE:
                continue
            if car_type is not None and cab.car_type != car_type:
                continue
            if location.distance_km(cab.location) <= radius_km:
                results.append(cab)
        return results


class RideRepository(InMemoryRepository):
    def for_user(self, user_id: str):
        return [r for r in self.all() if r.user_id == user_id]

    def for_driver(self, driver_id: str):
        return [r for r in self.all() if r.driver_id == driver_id]


class CouponRepository:
    """Keyed by coupon code rather than a generated id — codes are the natural key."""

    def __init__(self):
        self._lock = threading.Lock()
        self._store: Dict[str, Coupon] = {}

    def add(self, coupon: Coupon) -> Coupon:
        with self._lock:
            self._store[coupon.code] = coupon
        return coupon

    def get(self, code: str) -> Optional[Coupon]:
        return self._store.get(code)

    def delete(self, code: str):
        with self._lock:
            self._store.pop(code, None)
