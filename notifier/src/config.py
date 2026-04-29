"""중앙 설정.

환경변수에서 비밀값과 운영 파라미터를 읽고,
도메인 설정(members_count 등)은 KV에서 읽습니다 (Workers와 SSoT 공유).
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

    # 결제 파라미터
    # members_count는 KV (config:members_count)에서 읽습니다 — Workers와 SSoT
    members_count: int = 5
    usd_per_seat: float = 25.0  # Team Standard 월간 ($25)
    vat_rate: float = 0.10       # 한국 부가세 10%
    safety_margin: float = 0.05  # 5% 안전 마진
    billing_day: int = 15        # 매월 결제일

    @classmethod
    def from_env(cls) -> Config:
        """환경변수와 KV에서 설정을 로드합니다.

        - 비밀값/운영 파라미터: 환경변수
        - 도메인 핵심 값(members_count): KV의 config:* 키
        """
        def req(name: str) -> str:
            v = os.environ.get(name)
            if not v:
                raise RuntimeError(f"환경변수 {name}이 설정되지 않았습니다.")
            return v

        cf_account_id = req("CF_ACCOUNT_ID")
        cf_kv_namespace_id = req("CF_KV_NAMESPACE_ID")
        cf_api_token = req("CF_API_TOKEN")

        # KV에서 members_count 조회. 키가 없거나 에러면 fallback=5.
        # 운영 시 변경: npx wrangler kv key put --namespace-id=<KV_ID> "config:members_count" "6"
        members_count = fetch_config_int(
            account_id=cf_account_id,
            namespace_id=cf_kv_namespace_id,
            api_token=cf_api_token,
            config_key="members_count",
            fallback=5,
        )

        return cls(
            bot_token=req("DISCORD_BOT_TOKEN"),
            channel_id=req("DISCORD_CHANNEL_ID"),
            cf_account_id=cf_account_id,
            cf_kv_namespace_id=cf_kv_namespace_id,
            cf_api_token=cf_api_token,
            koreaexim_api_key=req("KOREAEXIM_API_KEY"),
            members_count=members_count,
            usd_per_seat=float(os.environ.get("USD_PER_SEAT", "25.0")),
            vat_rate=float(os.environ.get("VAT_RATE", "0.10")),
            safety_margin=float(os.environ.get("SAFETY_MARGIN", "0.05")),
            billing_day=int(os.environ.get("BILLING_DAY", "15")),
        )

    @property
    def total_usd(self) -> float:
        """부가세 포함 전체 USD 청구액."""
        return self.usd_per_seat * self.members_count * (1 + self.vat_rate)
