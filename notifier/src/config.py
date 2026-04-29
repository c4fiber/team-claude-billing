"""중앙 설정.

환경변수에서 모든 비밀값을 읽습니다. GitHub Actions Secrets에 등록.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # Discord
    bot_token: str
    channel_id: str

    # Cloudflare Workers KV (입금 현황 조회용)
    cf_account_id: str
    cf_kv_namespace_id: str
    cf_api_token: str

    # 한국수출입은행 환율 API
    koreaexim_api_key: str

    # 결제 파라미터
    members_count: int = 5
    usd_per_seat: float = 25.0  # Team Standard 월간 ($25)
    vat_rate: float = 0.10       # 한국 부가세 10%
    safety_margin: float = 0.05  # 5% 안전 마진
    billing_day: int = 15        # 매월 결제일

    @classmethod
    def from_env(cls) -> Config:
        def req(name: str) -> str:
            v = os.environ.get(name)
            if not v:
                raise RuntimeError(f"환경변수 {name}이 설정되지 않았습니다.")
            return v

        return cls(
            bot_token=req("DISCORD_BOT_TOKEN"),
            channel_id=req("DISCORD_CHANNEL_ID"),
            cf_account_id=req("CF_ACCOUNT_ID"),
            cf_kv_namespace_id=req("CF_KV_NAMESPACE_ID"),
            cf_api_token=req("CF_API_TOKEN"),
            koreaexim_api_key=req("KOREAEXIM_API_KEY"),
            members_count=int(os.environ.get("MEMBERS_COUNT", "5")),
            usd_per_seat=float(os.environ.get("USD_PER_SEAT", "25.0")),
            vat_rate=float(os.environ.get("VAT_RATE", "0.10")),
            safety_margin=float(os.environ.get("SAFETY_MARGIN", "0.05")),
            billing_day=int(os.environ.get("BILLING_DAY", "15")),
        )

    @property
    def total_usd(self) -> float:
        """부가세 포함 전체 USD 청구액."""
        return self.usd_per_seat * self.members_count * (1 + self.vat_rate)
