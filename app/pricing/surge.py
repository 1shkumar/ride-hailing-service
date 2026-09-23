"""
Bonus: pluggable surge multiplier based on demand/supply in an area.

SurgeStrategy is the seam: RideService only ever calls get_multiplier(area_id)
and multiplies it into the base fare. Swapping NoSurgeStrategy for
DemandSupplySurgeStrategy (or any other implementation) requires no change to
booking or pricing logic.
"""
import threading
from abc import ABC, abstractmethod
from typing import Dict

from app.models import Location


class SurgeStrategy(ABC):
    @abstractmethod
    def get_multiplier(self, area_id: str) -> float:
        ...


class NoSurgeStrategy(SurgeStrategy):
    """Default: surge disabled, multiplier is always 1.0."""

    def get_multiplier(self, area_id: str) -> float:
        return 1.0


class DemandSupplySurgeStrategy(SurgeStrategy):
    """
    Tracks active demand (ride requests) and supply (available drivers) per
    area and derives a multiplier from the ratio. Intentionally simple:

        multiplier = base + max(0, demand/supply - 1) * step, capped at max

    `record_demand` is called by RideService on every booking attempt.
    `record_supply` is expected to be called by whatever keeps cab counts
    fresh (e.g. on driver registration/location update in a fuller build) —
    kept as an explicit call rather than scanning all cabs on every fare
    calculation, to keep this strategy self-contained and cheap to call.
    """

    def __init__(self, base_multiplier: float = 1.0, max_multiplier: float = 3.0, step: float = 0.2):
        self._lock = threading.Lock()
        self._demand: Dict[str, int] = {}
        self._supply: Dict[str, int] = {}
        self.base_multiplier = base_multiplier
        self.max_multiplier = max_multiplier
        self.step = step

    def record_demand(self, area_id: str, delta: int = 1) -> None:
        with self._lock:
            self._demand[area_id] = self._demand.get(area_id, 0) + delta

    def record_supply(self, area_id: str, count: int) -> None:
        with self._lock:
            self._supply[area_id] = count

    def get_multiplier(self, area_id: str) -> float:
        demand = self._demand.get(area_id, 0)
        supply = max(self._supply.get(area_id, 0), 1)  # avoid div-by-zero
        ratio = demand / supply
        multiplier = self.base_multiplier + max(0.0, ratio - 1) * self.step
        return round(min(multiplier, self.max_multiplier), 2)


def area_id_for(location: Location, cell_size_deg: float = 0.05) -> str:
    """Coarse lat/lon grid cell used as an area id for surge purposes.
    Good enough for a demand/supply proxy; a real system would use a proper
    geo-index (geohash, S2, quad-tree) — see README 'what I'd do differently'."""
    lat_cell = int(location.lat / cell_size_deg)
    lon_cell = int(location.lon / cell_size_deg)
    return f"{lat_cell}:{lon_cell}"
