import pytest

from app.coupons.service import CouponService
from app.enums import DiscountType
from app.exceptions import CouponNotFound, InvalidCoupon
from app.repositories import CouponRepository


@pytest.fixture
def coupon_service():
    return CouponService(CouponRepository())


def test_add_and_apply_flat_coupon(coupon_service):
    coupon_service.add_coupon("FLAT50", DiscountType.FLAT, 50)
    assert coupon_service.compute_discount("FLAT50", fare=200) == 50


def test_flat_coupon_never_exceeds_the_fare(coupon_service):
    coupon_service.add_coupon("FLAT500", DiscountType.FLAT, 500)
    assert coupon_service.compute_discount("FLAT500", fare=100) == 100


def test_percentage_coupon_applies_correctly(coupon_service):
    coupon_service.add_coupon("PCT10", DiscountType.PERCENTAGE, 10)
    assert coupon_service.compute_discount("PCT10", fare=500) == 50


def test_percentage_coupon_respects_max_discount_cap(coupon_service):
    coupon_service.add_coupon("PCT20", DiscountType.PERCENTAGE, 20, max_discount=30)
    # 20% of 1000 = 200, capped at 30
    assert coupon_service.compute_discount("PCT20", fare=1000) == 30


def test_applying_unknown_coupon_raises(coupon_service):
    with pytest.raises(InvalidCoupon):
        coupon_service.compute_discount("DOES_NOT_EXIST", fare=100)


def test_delete_coupon_makes_it_unusable(coupon_service):
    coupon_service.add_coupon("TEMP10", DiscountType.FLAT, 10)
    coupon_service.delete_coupon("TEMP10")
    with pytest.raises(InvalidCoupon):
        coupon_service.compute_discount("TEMP10", fare=100)


def test_deleting_nonexistent_coupon_raises_not_found(coupon_service):
    with pytest.raises(CouponNotFound):
        coupon_service.delete_coupon("GHOST")


def test_percentage_discount_over_100_is_rejected_at_creation(coupon_service):
    with pytest.raises(InvalidCoupon):
        coupon_service.add_coupon("BAD", DiscountType.PERCENTAGE, 150)


def test_non_positive_discount_value_is_rejected(coupon_service):
    with pytest.raises(InvalidCoupon):
        coupon_service.add_coupon("ZERO", DiscountType.FLAT, 0)
    with pytest.raises(InvalidCoupon):
        coupon_service.add_coupon("NEG", DiscountType.FLAT, -5)
