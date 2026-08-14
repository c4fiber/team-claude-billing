"""Discord 채널에 메시지 발송.

봇 토큰을 사용해 Discord API로 직접 게시.
일반 Webhook이 아닌 봇 토큰을 사용하는 이유: 버튼 클릭 인터랙션이 작동하려면
메시지를 봇이 게시해야 합니다.
"""

from __future__ import annotations

import json
import logging

import httpx

from .calculator import BillingCalculation
from .kv_reader import DepositSnapshot

logger = logging.getLogger(__name__)

DISCORD_API = "https://discord.com/api/v10"

# 색상 (Discord embed color)
COLOR_INFO = 0x378ADD     # 파랑 - 정상 알림
COLOR_WARN = 0xEF9F27     # 황색 - 임박 (D-3)
COLOR_OK = 0x639922       # 녹색 - 결제 완료
COLOR_ERROR = 0xE24B4A    # 빨강 - 결제 실패


def post_billing_alert(
    bot_token: str,
    channel_id: str,
    calc: BillingCalculation,
    deposits: DepositSnapshot,
    days_until_billing: int,
    billing_date_str: str,
) -> None:
    """결제 알림 메시지 발송 (버튼 포함, 시트 tier별 분담)."""
    color = COLOR_WARN if days_until_billing <= 3 else COLOR_INFO

    title = f"💰 {billing_date_str} 결제 알림 (D-{days_until_billing})"

    # 인당 입금액 — tier별로 표시
    amount_lines = []
    if calc.standard.seat_count > 0:
        amount_lines.append(
            f"**Standard ({calc.standard.seat_count}명)**: 인당 `{calc.standard.per_person_krw:,}원`"
        )
    if calc.premium.seat_count > 0:
        amount_lines.append(
            f"**Premium ({calc.premium.seat_count}명)**: 인당 `{calc.premium.per_person_krw:,}원`"
        )

    description_lines = [
        *amount_lines,
        "",
        f"적용 환율: `{calc.fx_rate:,.2f}` KRW/USD",
        f"안전 마진: {calc.safety_margin * 100:.0f}% (환율·수수료 변동 대비)",
    ]

    if calc.carryover_krw > 0:
        description_lines.append(f"이월 잉여금: -{calc.carryover_krw:,}원 차감 적용")

    embed = {
        "title": title,
        "description": "\n".join(description_lines),
        "color": color,
        "fields": [
            {
                "name": "총 청구 (USD, VAT 포함)",
                "value": f"${calc.total_usd:.2f}",
                "inline": True,
            },
            {
                "name": "필요 KRW",
                "value": f"{calc.total_krw_needed:,}원",
                "inline": True,
            },
            {
                "name": "예상 잉여",
                "value": f"+{calc.expected_surplus_krw:,}원 (다음 달 이월)",
                "inline": True,
            },
            {
                "name": "현재 입금 현황",
                "value": _render_deposit_status(deposits, calc.total_seats),
                "inline": False,
            },
        ],
        "footer": {
            "text": (
                f"{deposits.month_key} • 본인 시트 종류 확인 후 입금 → [✅ 입금완료] 버튼 클릭"
            ),
        },
    }

    components = [
        {
            "type": 1,  # ACTION_ROW
            "components": [
                {
                    "type": 2,  # BUTTON
                    "style": 3,  # SUCCESS
                    "label": "✅ 입금완료",
                    "custom_id": "mark_paid",
                },
                {
                    "type": 2,
                    "style": 4,  # DANGER
                    "label": "↩️ 취소",
                    "custom_id": "unmark_paid",
                },
            ],
        }
    ]

    _post_message(bot_token, channel_id, {"embeds": [embed], "components": components})


def post_monthly_report(
    bot_token: str,
    channel_id: str,
    fx_rate: float,
    fx_history_30d: list[tuple[str, float]],
    next_month_calc: BillingCalculation,
) -> None:
    """매월 1일 환율 변동 + 다음 달 예상 리포트."""
    rates = [r for _, r in fx_history_30d]
    if not rates:
        return

    avg = sum(rates) / len(rates)
    high = max(rates)
    low = min(rates)
    volatility = (high - low) / avg * 100

    # 다음 달 예상 인당 — tier별
    estimate_lines = []
    if next_month_calc.standard.seat_count > 0:
        estimate_lines.append(
            f"Standard: `{next_month_calc.standard.per_person_krw:,}원`"
        )
    if next_month_calc.premium.seat_count > 0:
        estimate_lines.append(
            f"Premium: `{next_month_calc.premium.per_person_krw:,}원`"
        )
    next_month_estimate = " / ".join(estimate_lines) if estimate_lines else "-"

    embed = {
        "title": "📈 월간 환율 리포트",
        "description": "이번 달 USD/KRW 변동 요약",
        "color": COLOR_INFO,
        "fields": [
            {"name": "현재", "value": f"`{fx_rate:,.2f}`", "inline": True},
            {"name": "월 평균", "value": f"`{avg:,.2f}`", "inline": True},
            {"name": "변동폭", "value": f"`{volatility:.2f}%`", "inline": True},
            {"name": "최고", "value": f"`{high:,.2f}`", "inline": True},
            {"name": "최저", "value": f"`{low:,.2f}`", "inline": True},
            {
                "name": "다음 달 예상 인당",
                "value": next_month_estimate,
                "inline": True,
            },
        ],
        "footer": {"text": "안전 마진 5% + VAT 10% 적용 기준"},
    }

    _post_message(bot_token, channel_id, {"embeds": [embed]})


def _render_deposit_status(deposits: DepositSnapshot, total_seats: int) -> str:
    paid_count = deposits.paid_count
    if paid_count == 0:
        return f"⬜ 0 / {total_seats} (아직 입금 체크 없음)"

    lines = [f"✅ {paid_count} / {total_seats}"]
    for name in deposits.paid_users:
        lines.append(f"  • {name}")
    return "\n".join(lines)


def post_rate_graph(
    bot_token: str,
    channel_id: str,
    image_1m: bytes,
    image_3m: bytes,
    fx_rate: float,
    stats_1m: dict,
    stats_3m: dict,
) -> None:
    """환율 그래프 PNG 2장(1개월·3개월)을 Discord 채널에 순서대로 업로드."""

    def _make_embed(title: str, filename: str, stats: dict) -> dict:
        volatility = (stats["high"] - stats["low"]) / stats["avg"] * 100
        return {
            "title": title,
            "color": COLOR_INFO,
            "image": {"url": f"attachment://{filename}"},
            "fields": [
                {"name": "현재", "value": f"`{fx_rate:,.2f}`", "inline": True},
                {"name": "평균", "value": f"`{stats['avg']:,.2f}`", "inline": True},
                {"name": "변동폭", "value": f"`{volatility:.2f}%`", "inline": True},
                {"name": "최고", "value": f"`{stats['high']:,.2f}`", "inline": True},
                {"name": "최저", "value": f"`{stats['low']:,.2f}`", "inline": True},
                {"name": "데이터", "value": f"`{stats['count']}영업일`", "inline": True},
            ],
            "footer": {"text": "한국수출입은행 매매기준율 기준"},
        }

    # 1개월 그래프
    _post_message_with_file(
        bot_token, channel_id,
        payload={"embeds": [_make_embed("📊 USD/KRW 환율 추이 (최근 1개월)", "fx_rate_1m.png", stats_1m)]},
        file_bytes=image_1m,
        filename="fx_rate_1m.png",
        content_type="image/png",
    )
    # 3개월 그래프
    _post_message_with_file(
        bot_token, channel_id,
        payload={"embeds": [_make_embed("📈 USD/KRW 환율 추이 (최근 3개월)", "fx_rate_3m.png", stats_3m)]},
        file_bytes=image_3m,
        filename="fx_rate_3m.png",
        content_type="image/png",
    )


def _post_message_with_file(
    bot_token: str,
    channel_id: str,
    payload: dict,
    file_bytes: bytes,
    filename: str,
    content_type: str,
) -> None:
    """multipart/form-data로 파일과 embed를 함께 발송."""
    url = f"{DISCORD_API}/channels/{channel_id}/messages"
    # Content-Type은 httpx가 boundary 포함해 자동 설정 — 헤더에 수동 지정 금지
    headers = {"Authorization": f"Bot {bot_token}"}
    files = {"files[0]": (filename, file_bytes, content_type)}
    data = {"payload_json": json.dumps(payload)}
    resp = httpx.post(url, headers=headers, files=files, data=data, timeout=30.0)
    if resp.status_code >= 400:
        logger.error("Discord 파일 업로드 실패 (%d): %s", resp.status_code, resp.text)
        resp.raise_for_status()
    logger.info("Discord 파일 업로드 완료 (%s)", filename)


def _post_message(bot_token: str, channel_id: str, payload: dict) -> None:
    url = f"{DISCORD_API}/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json",
    }
    resp = httpx.post(url, headers=headers, json=payload, timeout=10.0)
    if resp.status_code >= 400:
        logger.error("Discord 메시지 발송 실패 (%d): %s", resp.status_code, resp.text)
        resp.raise_for_status()
    logger.info("Discord 메시지 발송 완료")
