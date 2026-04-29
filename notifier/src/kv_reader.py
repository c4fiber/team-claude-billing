"""Cloudflare Workers KV에 저장된 입금 현황 조회.

Notifier(GitHub Actions)는 Workers KV에 직접 쓰지 않습니다.
대신 알림 메시지에 현재 입금 현황을 포함하기 위해 KV를 읽기만 합니다.

Cloudflare API 토큰 발급:
    https://dash.cloudflare.com/profile/api-tokens
    → "Edit Cloudflare Workers" 템플릿 사용
    → 권한: Workers KV Storage:Read
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class DepositSnapshot:
    month_key: str
    paid_users: list[str]
    unpaid_users: list[str]

    @property
    def paid_count(self) -> int:
        return len(self.paid_users)

    @property
    def unpaid_count(self) -> int:
        return len(self.unpaid_users)


def fetch_current_deposits(
    account_id: str,
    namespace_id: str,
    api_token: str,
) -> DepositSnapshot:
    """이번 달 입금 현황 조회. 키가 없으면 빈 스냅샷 반환."""
    month_key = _current_month_key()
    kv_key = f"deposits:{month_key}"

    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
        f"/storage/kv/namespaces/{namespace_id}/values/{kv_key}"
    )
    headers = {"Authorization": f"Bearer {api_token}"}

    try:
        resp = httpx.get(url, headers=headers, timeout=10.0)
    except httpx.HTTPError as e:
        logger.warning("KV 조회 실패: %s. 빈 스냅샷으로 대체.", e)
        return DepositSnapshot(month_key=month_key, paid_users=[], unpaid_users=[])

    if resp.status_code == 404:
        # 아직 아무도 입금 체크하지 않음
        return DepositSnapshot(month_key=month_key, paid_users=[], unpaid_users=[])

    if resp.status_code != 200:
        logger.warning("KV 응답 비정상 (%d): %s", resp.status_code, resp.text)
        return DepositSnapshot(month_key=month_key, paid_users=[], unpaid_users=[])

    try:
        data = resp.json()
    except Exception as e:
        logger.warning("KV 응답 파싱 실패: %s", e)
        return DepositSnapshot(month_key=month_key, paid_users=[], unpaid_users=[])

    paid = [d["username"] for d in data.values() if d.get("paid")]
    unpaid = [d["username"] for d in data.values() if not d.get("paid")]
    return DepositSnapshot(month_key=month_key, paid_users=paid, unpaid_users=unpaid)


def _current_month_key() -> str:
    now = datetime.now(KST)
    return f"{now.year}-{now.month:02d}"
