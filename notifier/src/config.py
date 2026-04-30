"""중앙 설정.

환경변수에서 비밀값과 운영 파라미터를 읽고,
도메인 설정(시트 구성, 시트별 가격)은 KV에서 읽습니다 (Workers와 SSoT 공유).

KV 키 구조:
    config:standard_seats     — Standard 시트 수 (예: "3")
    config:premium_seats      — Premium 시트 수 (예: "2")
    config:standard_price_usd — Standard 시트 월 가격 USD (예: "25")
    config:premium_price_usd  — Premium 시트 월 가격 USD (예: "125")
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .kv_reader import fetch_config_int


@dataclass(frozen=True)
class Config:
    # Discord
    bot_token: str
    channel_id: str

    # Cloudflare Workers KV (입금 현황 + 도메인 설정)
    cf_account_id: str
    cf_kv_namespace_id: str
    cf_api_token: str

    # 한국수출입은행 환율 API
    koreaexim_api_key: str

    # 시트 구성 — KV의 config:* 키에서 읽음 (Workers와 SSoT)
    standard_seats: int = 5
    premium_seats: int = 0
    standard_price_usd: int = 25
    premium_price_usd: int = 125

    # 운영 파라미터 (환경변수)
    vat_rate: float = 0.10       # 한국 부가세 10%
    safety_margin: float = 0.05  # 5% 안전 마진
    billing_day: int = 15        # 매월 결제일

    @classmethod
    def from_env(cls) -> Config:
        """환경변수와 KV에서 설정을 로드합니다.

        - 비밀값/운영 파라미터: 환경변수
        - 시트 구성/가격: KV의 config:* 키
        """
        def req(name: str) -> str:
            v = os.environ.get(name)
            if not v:
                raise RuntimeError(f"환경변수 {name}이 설정되지 않았습니다.")
            return v

        cf_account_id = req("CF_ACCOUNT_ID")
        cf_kv_namespace_id = req("CF_KV_NAMESPACE_ID")
        cf_api_token = req("CF_API_TOKEN")

        # KV에서 시트 구성과 가격을 일괄 조회
        # 운영 시 변경: docs/OPERATIONS.md 참고
        standard_seats = fetch_config_int(
            cf_account_id, cf_kv_namespace_id, cf_api_token,
            "standard_seats", fallback=5,
        )
        premium_seats = fetch_config_int(
            cf_account_id, cf_kv_namespace_id, cf_api_token,
            "premium_seats", fallback=0,
        )
        standard_price = fetch_config_int(
            cf_account_id, cf_kv_namespace_id, cf_api_token,
            "standard_price_usd", fallback=25,
        )
        premium_price = fetch_config_int(
            cf_account_id, cf_kv_namespace_id, cf_api_token,
            "premium_price_usd", fallback=125,
        )

        return cls(
            bot_token=req("DISCORD_BOT_TOKEN"),
            channel_id=req("DISCORD_CHANNEL_ID"),
            cf_account_id=cf_account_id,
            cf_kv_namespace_id=cf_kv_namespace_id,
            cf_api_token=cf_api_token,
            koreaexim_api_key=req("KOREAEXIM_API_KEY"),
            standard_seats=standard_seats,
            premium_seats=premium_seats,
            standard_price_usd=standard_price,
            premium_price_usd=premium_price,
            vat_rate=float(os.environ.get("VAT_RATE", "0.10")),
            safety_margin=float(os.environ.get("SAFETY_MARGIN", "0.05")),
            billing_day=int(os.environ.get("BILLING_DAY", "15")),
        )

    @property
    def total_seats(self) -> int:
        """전체 시트 수."""
        return self.standard_seats + self.premium_seats

    @property
    def total_usd(self) -> float:
        """부가세 포함 전체 USD 청구액."""
        subtotal = (
            self.standard_seats * self.standard_price_usd
            + self.premium_seats * self.premium_price_usd
        )
        return subtotal * (1 + self.vat_rate)
