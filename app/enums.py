from enum import Enum


class CarType(str, Enum):
    HATCHBACK = "HATCHBACK"
    SEDAN = "SEDAN"


class CabStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"


class RideStatus(str, Enum):
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class DiscountType(str, Enum):
    FLAT = "FLAT"
    PERCENTAGE = "PERCENTAGE"
