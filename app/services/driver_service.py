from app.enums import CarType
from app.models import Cab, Driver, Location
from app.repositories import CabRepository, DriverRepository


class DriverService:
    """
    Assumption: one driver <-> one cab, created together at registration time.
    The spec talks about "the location of a cab" as if a cab might be a
    separate concept from a driver (e.g. a driver could switch vehicles), but
    nothing in the mandatory requirements needs that distinction, so we keep
    it simple: registering a driver also creates their single cab, and
    "updating a cab's location" is exposed as updating *the driver's* cab.
    See README "Assumptions" for the trade-off.
    """

    def __init__(self, driver_repo: DriverRepository, cab_repo: CabRepository):
        self._drivers = driver_repo
        self._cabs = cab_repo

    def register_driver(
        self,
        name: str,
        phone: str,
        car_type: CarType,
        location: Location,
        rating: float = 5.0,
    ):
        driver = Driver(name=name, phone=phone, car_type=car_type, rating=rating)
        self._drivers.add(driver)
        cab = Cab(driver_id=driver.id, car_type=car_type, location=location)
        self._cabs.add(cab)
        return driver, cab
