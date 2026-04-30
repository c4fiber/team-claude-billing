"""KRW 입금액 계산 (시트 tier별 차등 분담).

핵심 공식:
    각 tier 인당 KRW = (tier 가격 USD) × 환율 × (1 + 안전 마진) × (1 + VAT)
    100원 단위 올림으로 입금 친화적 금액

이월 잉여금은 전체 모금액에서 차감 — tier 무관하게 비례 적용 가능하지만
단순화를 위해 Standard 인당에서만 차감.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class TierBreakdown:
    """각 시트 tier의 계산 결과."""
    tier_name: str
    seat_count: int
    price_usd: int
    per_person_krw: int  # 100원 단위 올림 후


@dataclass(frozen=True)
class BillingCalculation:
    fx_rate: float
    safety_margin: float
    vat_rate: float
    carryover_krw: int

    standard: TierBreakdown
    premium: TierBreakdown

    total_krw_needed: int  # 안전 마진 + VAT 포함 필요 총액
    total_collected_krw: int  # 5명 × per_person 합계

    @property
    def total_seats(self) -> int:
        return self.standard.seat_count + self.premium.seat_count

    @property
    def total_usd(self) -> float:
        """VAT 포함 전체 USD."""
        subtotal = (
            self.standard.seat_count * self.standard.price_usd
            + self.premium.seat_count * self.premium.price_usd
        )
        return subtotal * (1 + self.vat_rate)

    @property
    def expected_surplus_krw(self) -> int:
        """예상 잉여금 (모금액 + 이월 − 필요액)."""
        return self.total_collected_krw + self.carryover_krw - self.total_krw_needed


def calculate_billing(
    fx_rate: float,
    standard_seats: int,
    premium_seats: int,
    standard_price_usd: int,
    premium_price_usd: int,
    vat_rate: float = 0.10,
    safety_margin: float = 0.05,
    carryover_krw: int = 0,
) -> BillingCalculation:
    # 각 tier별 인당 KRW 계산
    # 인당 USD × 환율 × (1 + VAT) × (1 + 마진)
    multiplier = (1 + vat_rate) * (1 + safety_margin)

    standard_per_raw = standard_price_usd * fx_rate * multiplier
    premium_per_raw = premium_price_usd * fx_rate * multiplier

    # 이월 잉여금은 standard 인당에서만 차감 (단순화)
    # 만약 standard가 0명이면 premium에서 차감
    if standard_seats > 0:
        standard_per_after_carryover = max(
            0,
            standard_per_raw - (carryover_krw / standard_seats),
        )
        premium_per_after_carryover = premium_per_raw
    elif premium_seats > 0:
        standard_per_after_carryover = standard_per_raw
        premium_per_after_carryover = max(
            0,
            premium_per_raw - (carryover_krw / premium_seats),
        )
    else:
        standard_per_after_carryover = standard_per_raw
        premium_per_after_carryover = premium_per_raw

    # 100원 단위 올림
    standard_per_krw = (
        math.ceil(standard_per_after_carryover / 100) * 100 if standard_seats > 0 else 0
    )
    premium_per_krw = (
        math.ceil(premium_per_after_carryover / 100) * 100 if premium_seats > 0 else 0
    )

    # 총 모금액
    total_collected = (
        standard_per_krw * standard_seats + premium_per_krw * premium_seats
    )

    # 필요 KRW (마진 포함)
    subtotal_usd = (
        standard_seats * standard_price_usd + premium_seats * premium_price_usd
    )
    total_krw_needed = math.ceil(subtotal_usd * fx_rate * multiplier)

    return BillingCalculation(
        fx_rate=fx_rate,
        safety_margin=safety_margin,
        vat_rate=vat_rate,
        carryover_krw=carryover_krw,
        standard=TierBreakdown(
            tier_name="Standard",
            seat_count=standard_seats,
            price_usd=standard_price_usd,
            per_person_krw=standard_per_krw,
        ),
        premium=TierBreakdown(
            tier_name="Premium",
            seat_count=premium_seats,
            price_usd=premium_price_usd,
            per_person_krw=premium_per_krw,
        ),
        total_krw_needed=total_krw_needed,
        total_collected_krw=total_collected,
    )
