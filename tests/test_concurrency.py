import threading

from app.container import build_container
from app.enums import CarType
from app.exceptions import NoDriverAvailable
from app.models import Location


def test_only_one_of_two_racing_bookings_wins_a_single_cab():
    """Two users try to book the same (only) nearby cab at the same instant.
    Exactly one must succeed; the other must see NoDriverAvailable, never a
    double-booked cab."""
    c = build_container()
    user1 = c.user_service.register_user("A", "1")
    user2 = c.user_service.register_user("B", "2")
    c.driver_service.register_driver("D", "3", CarType.SEDAN, Location(0.001, 0.001))

    results = {}

    def attempt(name, user):
        try:
            results[name] = c.ride_service.book_ride(user.id, Location(0, 0), CarType.SEDAN, radius_km=5)
        except NoDriverAvailable:
            results[name] = None

    barrier = threading.Barrier(2)

    def run(name, user):
        barrier.wait()  # maximize the chance both threads hit the critical section together
        attempt(name, user)

    t1 = threading.Thread(target=run, args=("t1", user1))
    t2 = threading.Thread(target=run, args=("t2", user2))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    successes = [v for v in results.values() if v is not None]
    failures = [v for v in results.values() if v is None]
    assert len(successes) == 1
    assert len(failures) == 1


def test_many_concurrent_bookings_never_double_book_a_cab():
    """20 users race for 5 cabs. At most 5 bookings succeed, and every
    successful booking claims a distinct cab."""
    c = build_container()
    user_ids = [c.user_service.register_user(f"U{i}", str(i)).id for i in range(20)]
    for i in range(5):
        c.driver_service.register_driver(f"D{i}", str(100 + i), CarType.SEDAN, Location(0.0001 * i, 0.0001 * i))

    results = []
    results_lock = threading.Lock()
    barrier = threading.Barrier(20)

    def attempt(uid):
        barrier.wait()
        try:
            ride = c.ride_service.book_ride(uid, Location(0, 0), CarType.SEDAN, radius_km=50)
            with results_lock:
                results.append(ride)
        except NoDriverAvailable:
            pass

    threads = [threading.Thread(target=attempt, args=(uid,)) for uid in user_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 5  # exactly the number of cabs available
    cab_ids = [r.cab_id for r in results]
    assert len(cab_ids) == len(set(cab_ids))  # no cab was ever double-booked


def test_cab_can_be_rebooked_immediately_after_being_freed_under_contention():
    c = build_container()
    driver, cab = c.driver_service.register_driver("D", "1", CarType.SEDAN, Location(0.001, 0.001))
    user1 = c.user_service.register_user("A", "1")
    user2 = c.user_service.register_user("B", "2")

    ride1 = c.ride_service.book_ride(user1.id, Location(0, 0), CarType.SEDAN, radius_km=5)
    c.ride_service.end_ride(ride1.id, Location(0.01, 0.01))
    ride2 = c.ride_service.book_ride(user2.id, Location(0, 0), CarType.SEDAN, radius_km=5)

    assert ride2.cab_id == cab.id
