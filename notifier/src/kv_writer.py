"""Cloudflare Workers KV 쓰기.

Notifier(GitHub Actions)가 Workers와 공유할 값을 KV에 씁니다.
읽기는 kv_reader.py, 쓰기는 이 모듈을 사용합니다.

Cloudflare REST API:
    PUT /accounts/{account_id}/storage/kv/namespaces/{ns_id}/values/{key}
    Body: raw UTF-8 string (no JSON envelope)
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_CF_API_BASE = "https://api.cloudflare.com/client/v4"


def put_kv_value(
    account_id: str,
    namespace_id: str,
    api_token: str,
    kv_key: str,
    value: str,
    *,
    expiration_ttl: int | None = None,
) -> None:
    """KV에 문자열 값을 씁니다."""
    url = f"{_CF_API_BASE}/accounts/{account_id}/storage/kv/namespaces/{namespace_id}/values/{kv_key}"
    headers = {"Authorization": f"Bearer {api_token}"}
    params: dict = {}
    if expiration_ttl is not None:
        params["expiration_ttl"] = expiration_ttl

    try:
        resp = httpx.put(
            url,
            headers=headers,
            content=value.encode("utf-8"),
            params=params,
            timeout=10.0,
        )
    except httpx.HTTPError as e:
        logger.error("KV 쓰기 HTTP 오류 (key=%s): %s", kv_key, e)
        raise

    if resp.status_code not in (200, 201):
        logger.error(
            "KV 쓰기 실패 (key=%s, status=%d): %s",
            kv_key,
            resp.status_code,
            resp.text[:200],
        )
        resp.raise_for_status()

    logger.info("KV 쓰기 완료 (key=%s)", kv_key)
