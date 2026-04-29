"""KRW 입금액 계산.

핵심 공식:
    필요 KRW = USD 청구액 × 환율 × (1 + 안전 마진)
    인당 KRW = (필요 KRW − 이월 잉여금) ÷ 인원
    입금 요청액 = ceil(인당 KRW / 100) × 100  (100원 단위 올림)
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class BillingCalculation:
    total_usd: float          # 청구 USD (부가세 포함)
    fx_rate: float            # USD/KRW 매매기준율
    safety_margin: float      # 안전 마진율 (0.05 = 5%)
    members_count: int
    carryover_krw: int        # 지난 달에서 이월된 잉여금
    total_krw_needed: int     # 안전 마진 포함 필요 총액
    per_person_krw: int       # 인당 입금 요청액 (100원 단위 올림)
    total_collected_krw: int  # 5명 × per_person_krw

    @property
    def expected_surplus_krw(self) -> int:
        """예상 잉여금 (총 모금액 + 이월 − 필요액)."""
        return self.total_collected_krw + self.carryover_krw - self.total_krw_needed


def calculate_billing(
    total_usd: float,
    fx_rate: float,
    members_count: int,
    safety_margin: float = 0.05,
    carryover_krw: int = 0,
) -> BillingCalculation:
    raw_krw = total_usd * fx_rate * (1 + safety_margin)
    total_krw_needed = math.ceil(raw_krw)

    net_needed = max(0, total_krw_needed - carryover_krw)
    per_person_raw = net_needed / members_count
    per_person_krw = math.ceil(per_person_raw / 100) * 100

    total_collected_krw = per_person_krw * members_count

    return BillingCalculation(
        total_usd=total_usd,
        fx_rate=fx_rate,
        safety_margin=safety_margin,
        members_count=members_count,
        carryover_krw=carryover_krw,
        total_krw_needed=total_krw_needed,
        per_person_krw=per_person_krw,
        total_collected_krw=total_collected_krw,
    )
