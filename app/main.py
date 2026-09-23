"""
FastAPI application. This file only does HTTP <-> service translation: parse
request, call a service method, map the domain result (or domain exception)
to a response. No business logic lives here.

Matching/surge strategy selection is done here, by environment variable, and
handed to RideService through its public setters — this is what "switchable
without touching booking logic" means in practice (see bonus requirement 2).
"""
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app import schemas
from app.container import build_container
from app.exceptions import (
    CouponNotFound,
    DomainError,
    DriverNotFound,
    InvalidCoupon,
    InvalidRideState,
    NoDriverAvailable,
    RideNotFound,
    UserNotFound,
)
from app.matching.strategy import HighestRatedDriverStrategy, NearestDriverStrategy
from app.models import Location
from app.pricing.surge import DemandSupplySurgeStrategy, NoSurgeStrategy

app = FastAPI(title="Ride Hailing Backend", version="1.0.0")

container = build_container()

# --- runtime strategy selection (env-configurable, no code change needed) --
_matching_choice = os.environ.get("MATCHING_STRATEGY", "NEAREST").upper()
if _matching_choice == "HIGHEST_RATED":
    container.ride_service.set_matching_strategy(HighestRatedDriverStrategy(container.driver_repo))
elif _matching_choice == "NEAREST":
    container.ride_service.set_matching_strategy(NearestDriverStrategy())

_surge_choice = os.environ.get("SURGE_STRATEGY", "NONE").upper()
if _surge_choice == "DEMAND_SUPPLY":
    container.ride_service.set_surge_strategy(DemandSupplySurgeStrategy())
else:
    container.ride_service.set_surge_strategy(NoSurgeStrategy())


ERROR_STATUS = {
    UserNotFound: 404,
    DriverNotFound: 404,
    RideNotFound: 404,
    CouponNotFound: 404,
    NoDriverAvailable: 409,
    InvalidRideState: 409,
    InvalidCoupon: 400,
}


@app.exception_handler(DomainError)
async def domain_error_handler(request, exc: DomainError):
    status_code = ERROR_STATUS.get(type(exc), 400)
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


@app.get("/")
def root():
    return {"service": "ride-hailing-backend", "docs": "/docs"}


# -- users --------------------------------------------------------------
@app.post("/users", response_model=schemas.UserOut)
def register_user(payload: schemas.RegisterUserRequest):
    user = container.user_service.register_user(payload.name, payload.phone)
    return schemas.UserOut.from_model(user)


@app.get("/users/{user_id}/rides", response_model=schemas.RideHistoryOut)
def user_rides(user_id: str):
    history = container.ride_service.user_ride_history(user_id)
    return schemas.RideHistoryOut(
        ongoing=[schemas.RideOut.from_model(r) for r in history["ongoing"]],
        completed=[schemas.RideOut.from_model(r) for r in history["completed"]],
    )


# -- drivers / cabs -------------------------------------------------------
@app.post("/drivers", response_model=schemas.DriverOut)
def register_driver(payload: schemas.RegisterDriverRequest):
    driver, cab = container.driver_service.register_driver(
        payload.name,
        payload.phone,
        payload.car_type,
        Location(lat=payload.lat, lon=payload.lon),
        payload.rating,
    )
    return schemas.DriverOut.from_model(driver, cab)


@app.put("/drivers/{driver_id}/location")
def update_cab_location(driver_id: str, payload: schemas.LocationUpdate):
    cab = container.ride_service.update_cab_location(driver_id, Location(lat=payload.lat, lon=payload.lon))
    return {"cab_id": cab.id, "lat": cab.location.lat, "lon": cab.location.lon}


@app.get("/drivers/{driver_id}/rides", response_model=schemas.RideHistoryOut)
def driver_rides(driver_id: str):
    history = container.ride_service.driver_ride_history(driver_id)
    return schemas.RideHistoryOut(
        ongoing=[schemas.RideOut.from_model(r) for r in history["ongoing"]],
        completed=[schemas.RideOut.from_model(r) for r in history["completed"]],
    )


# -- rides ----------------------------------------------------------------
@app.post("/rides/book", response_model=schemas.RideOut)
def book_ride(payload: schemas.BookRideRequest):
    ride = container.ride_service.book_ride(
        payload.user_id,
        Location(lat=payload.pickup_lat, lon=payload.pickup_lon),
        payload.car_type,
        payload.radius_km,
        payload.coupon_code,
    )
    return schemas.RideOut.from_model(ride)


@app.post("/rides/{ride_id}/end", response_model=schemas.RideOut)
def end_ride(ride_id: str, payload: schemas.EndRideRequest):
    ride = container.ride_service.end_ride(ride_id, Location(lat=payload.drop_lat, lon=payload.drop_lon))
    return schemas.RideOut.from_model(ride)


@app.post("/rides/{ride_id}/cancel", response_model=schemas.RideOut)
def cancel_ride(ride_id: str):
    ride = container.ride_service.cancel_ride(ride_id)
    return schemas.RideOut.from_model(ride)


# -- coupons --------------------------------------------------------------
@app.post("/coupons", response_model=schemas.CouponOut)
def add_coupon(payload: schemas.AddCouponRequest):
    coupon = container.coupon_service.add_coupon(
        payload.code, payload.discount_type, payload.value, payload.max_discount
    )
    return schemas.CouponOut.from_model(coupon)


@app.delete("/coupons/{code}")
def delete_coupon(code: str):
    container.coupon_service.delete_coupon(code)
    return {"deleted": code}
