class DomainError(Exception):
    """Base class for all domain-level errors. Caught centrally at the API edge
    (see main.py) and mapped to HTTP status codes there — services never know
    about HTTP."""


class UserNotFound(DomainError):
    pass


class DriverNotFound(DomainError):
    pass


class NoDriverAvailable(DomainError):
    pass


class RideNotFound(DomainError):
    pass


class InvalidRideState(DomainError):
    pass


class CouponNotFound(DomainError):
    pass


class InvalidCoupon(DomainError):
    pass
