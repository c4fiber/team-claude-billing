"""Cloudflare Workers KV 조회 (입금 현황 + 도메인 설정).

Notifier(GitHub Actions)는 Workers KV에 직접 쓰지 않습니다.
대신 알림 메시지에 현재 입금 현황과 모임 인원수 같은 설정을 포함하기 위해
KV를 읽기만 합니다.

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

    raw = _fetch_kv_value(account_id, namespace_id, api_token, kv_key)
    if raw is None:
        return DepositSnapshot(month_key=month_key, paid_users=[], unpaid_users=[])

    try:
        data = _parse_json(raw)
    except ValueError as e:
        logger.warning("KV 응답 파싱 실패: %s", e)
        return DepositSnapshot(month_key=month_key, paid_users=[], unpaid_users=[])

    paid = [d["username"] for d in data.values() if d.get("paid")]
    unpaid = [d["username"] for d in data.values() if not d.get("paid")]
    return DepositSnapshot(month_key=month_key, paid_users=paid, unpaid_users=unpaid)


def fetch_config_int(
    account_id: str,
    namespace_id: str,
    api_token: str,
    config_key: str,
    fallback: int,
) -> int:
    """KV에서 도메인 설정값을 정수로 가져옵니다. 키가 없거나 파싱 실패 시 fallback.

    Workers의 ConfigStore와 동일한 키 prefix("config:")를 사용하므로 SSoT가 보장됩니다.
    """
    kv_key = f"config:{config_key}"
    raw = _fetch_kv_value(account_id, namespace_id, api_token, kv_key)
    if raw is None:
        logger.warning("KV에 config:%s 키가 없습니다. fallback=%d 사용.", config_key, fallback)
        return fallback

    try:
        return int(raw.strip())
    except (ValueError, AttributeError) as e:
        logger.error("config:%s 정수 파싱 실패 (값=%r): %s. fallback=%d.", config_key, raw, e, fallback)
        return fallback


def _fetch_kv_value(
    account_id: str,
    namespace_id: str,
    api_token: str,
    kv_key: str,
) -> str | None:
    """KV에서 raw 문자열 값을 가져옵니다. 키가 없거나 에러면 None."""
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
        f"/storage/kv/namespaces/{namespace_id}/values/{kv_key}"
    )
    headers = {"Authorization": f"Bearer {api_token}"}

    try:
        resp = httpx.get(url, headers=headers, timeout=10.0)
    except httpx.HTTPError as e:
        logger.warning("KV 조회 실패 (key=%s): %s", kv_key, e)
        return None

    if resp.status_code == 404:
        return None

    if resp.status_code != 200:
        logger.warning("KV 응답 비정상 (key=%s, status=%d): %s", kv_key, resp.status_code, resp.text[:200])
        return None

    return resp.text


def _parse_json(raw: str) -> dict:
    """JSON 파싱. 실패 시 ValueError."""
    import json
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError(f"Expected dict, got {type(data).__name__}")
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON decode error: {e}") from e


def _current_month_key() -> str:
    now = datetime.now(KST)
    return f"{now.year}-{now.month:02d}"
