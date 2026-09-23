from typing import Optional

from app.enums import DiscountType
from app.exceptions import CouponNotFound, InvalidCoupon
from app.models import Coupon
from app.repositories import CouponRepository


class CouponService:
    def __init__(self, repo: CouponRepository):
        self._repo = repo

    def add_coupon(
        self,
        code: str,
        discount_type: DiscountType,
        value: float,
        max_discount: Optional[float] = None,
    ) -> Coupon:
        if not code:
            raise InvalidCoupon("Coupon code cannot be empty")
        if value <= 0:
            raise InvalidCoupon("Discount value must be positive")
        if discount_type == DiscountType.PERCENTAGE and value > 100:
            raise InvalidCoupon("Percentage discount cannot exceed 100")
        coupon = Coupon(code=code, discount_type=discount_type, value=value, max_discount=max_discount)
        return self._repo.add(coupon)

    def delete_coupon(self, code: str) -> None:
        if not self._repo.get(code):
            raise CouponNotFound(f"Coupon '{code}' not found")
        self._repo.delete(code)

    def compute_discount(self, code: str, fare: float) -> float:
        """Validates the coupon and returns the discount amount for `fare`.
        Never returns a discount larger than the fare itself (no negative
        final fares)."""
        coupon = self._repo.get(code)
        if not coupon or not coupon.active:
            raise InvalidCoupon(f"Coupon '{code}' is invalid or inactive")

        if coupon.discount_type == DiscountType.FLAT:
            discount = coupon.value
        else:  # PERCENTAGE
            discount = fare * coupon.value / 100
            if coupon.max_discount is not None:
                discount = min(discount, coupon.max_discount)

        return round(min(discount, fare), 2)
