from app.enums import CarType
from app.matching.strategy import HighestRatedDriverStrategy
from app.models import Location


def test_nearest_driver_strategy_is_the_default(container):
    c = container
    user = c.user_service.register_user("A", "1")
    _, near_cab = c.driver_service.register_driver("Near", "1", CarType.SEDAN, Location(0.001, 0.001))
    _, far_cab = c.driver_service.register_driver("Far", "2", CarType.SEDAN, Location(0.05, 0.05))
    ride = c.ride_service.book_ride(user.id, Location(0, 0), CarType.SEDAN, radius_km=10)
    assert ride.cab_id == near_cab.id


def test_highest_rated_strategy_overrides_default_without_touching_booking_code(container):
    c = container
    c.ride_service.set_matching_strategy(HighestRatedDriverStrategy(c.driver_repo))

    user = c.user_service.register_user("A", "1")
    _, near_cab = c.driver_service.register_driver("Near", "1", CarType.SEDAN, Location(0.001, 0.001), rating=3.0)
    _, far_cab = c.driver_service.register_driver("Far", "2", CarType.SEDAN, Location(0.05, 0.05), rating=4.9)

    ride = c.ride_service.book_ride(user.id, Location(0, 0), CarType.SEDAN, radius_km=10)

    assert ride.cab_id == far_cab.id  # picked for rating despite being farther


def test_highest_rated_strategy_falls_back_to_distance_on_tie(container):
    c = container
    c.ride_service.set_matching_strategy(HighestRatedDriverStrategy(c.driver_repo))

    user = c.user_service.register_user("A", "1")
    _, near_cab = c.driver_service.register_driver("Near", "1", CarType.SEDAN, Location(0.001, 0.001), rating=4.5)
    _, far_cab = c.driver_service.register_driver("Far", "2", CarType.SEDAN, Location(0.05, 0.05), rating=4.5)

    ride = c.ride_service.book_ride(user.id, Location(0, 0), CarType.SEDAN, radius_km=10)

    assert ride.cab_id == near_cab.id
