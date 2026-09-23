"""
Bonus: configurable driver-matching strategy. A MatchingStrategy only ranks
already-radius-filtered, already-car-type-filtered candidate cabs; it never
touches availability or claims a cab (that's RideService's job, under lock —
see services/ride_service.py). This keeps matching swappable without any risk
to the concurrency-safety of booking.
"""
from abc import ABC, abstractmethod
from typing import List

from app.models import Cab, Location


class MatchingStrategy(ABC):
    @abstractmethod
    def order_candidates(self, cabs: List[Cab], pickup: Location) -> List[Cab]:
        """Return cabs ordered best-match-first. RideService tries to claim
        them in this order until one succeeds."""
        ...


class NearestDriverStrategy(MatchingStrategy):
    def order_candidates(self, cabs: List[Cab], pickup: Location) -> List[Cab]:
        return sorted(cabs, key=lambda cab: pickup.distance_km(cab.location))


class HighestRatedDriverStrategy(MatchingStrategy):
    """Prefers the highest-rated driver; distance to pickup is only a
    tie-breaker. Needs the driver repo to look up ratings."""

    def __init__(self, driver_repo):
        self._driver_repo = driver_repo

    def order_candidates(self, cabs: List[Cab], pickup: Location) -> List[Cab]:
        def sort_key(cab: Cab):
            driver = self._driver_repo.get(cab.driver_id)
            rating = driver.rating if driver else 0.0
            return (-rating, pickup.distance_km(cab.location))

        return sorted(cabs, key=sort_key)
