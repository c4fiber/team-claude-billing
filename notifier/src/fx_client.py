"""한국수출입은행 환율 API 클라이언트.

API 키 발급: https://www.koreaexim.go.kr/ir/HPHKIR020M01?apino=2&viewtype=C
무료, 발급 즉시 사용 가능.

매매기준율(deal_bas_r)은 한국 카드 결제의 환산 기준이 되는 환율과 가장 가깝습니다.
다만 카드사별 전신환매도율은 매매기준율 + 약 1% 이므로,
실제 청구 환율을 보수적으로 추정하려면 매매기준율 × 1.01 정도를 적용해도 됩니다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
EXIM_URL = "https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON"


class ExchangeRateError(Exception):
    """환율 조회 실패."""


def fetch_usd_krw_rate(api_key: str) -> float:
    """USD/KRW 매매기준율을 반환.

    한국수출입은행 API는 영업일 11시 이후에만 당일 데이터를 제공.
    11시 이전이거나 휴일이면 최근 영업일 데이터로 폴백.
    """
    today = datetime.now(KST).date()
    for offset in range(7):  # 최대 일주일 전까지 폴백
        target_date = today - timedelta(days=offset)
        rate = _try_fetch(api_key, target_date)
        if rate is not None:
            if offset > 0:
                logger.warning(
                    "당일 환율을 가져올 수 없어 %d일 전 환율을 사용합니다 (%s)",
                    offset, target_date,
                )
            return rate

    raise ExchangeRateError(
        "최근 7일간 환율 데이터를 가져올 수 없습니다. API 키 상태를 확인하세요."
    )


def _try_fetch(api_key: str, date) -> float | None:
    params = {
        "authkey": api_key,
        "searchdate": date.strftime("%Y%m%d"),
        "data": "AP01",
    }
    try:
        resp = httpx.get(EXIM_URL, params=params, timeout=10.0)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.error("환율 API 요청 실패: %s", e)
        return None

    data = resp.json()
    if not isinstance(data, list) or len(data) == 0:
        return None

    for item in data:
        if item.get("cur_unit") == "USD":
            raw = item.get("deal_bas_r", "").replace(",", "")
            try:
                return float(raw)
            except ValueError:
                return None
    return None
