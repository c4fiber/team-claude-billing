"""Discord 채널에 메시지 발송.

봇 토큰을 사용해 Discord API로 직접 게시.
일반 Webhook이 아닌 봇 토큰을 사용하는 이유: 버튼 클릭 인터랙션이 작동하려면
메시지를 봇이 게시해야 합니다.
"""

from __future__ import annotations

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
    """결제 알림 메시지 발송 (버튼 포함)."""
    color = COLOR_WARN if days_until_billing <= 3 else COLOR_INFO

    title = f"💰 {billing_date_str} 결제 알림 (D-{days_until_billing})"

    description_lines = [
        f"**인당 입금액: {calc.per_person_krw:,}원**",
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
                "name": "총 청구 (USD)",
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
                "value": _render_deposit_status(deposits, calc.members_count),
                "inline": False,
            },
        ],
        "footer": {
            "text": f"{deposits.month_key} • 잉여금은 다음 달 입금액에서 자동 차감",
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
                {
                    "type": 2,
                    "style": 2,  # SECONDARY
                    "label": "📊 현황",
                    "custom_id": "show_status",
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
    next_month_estimate: int,
) -> None:
    """매월 1일 환율 변동 리포트."""
    rates = [r for _, r in fx_history_30d]
    if not rates:
        return

    avg = sum(rates) / len(rates)
    high = max(rates)
    low = min(rates)
    volatility = (high - low) / avg * 100

    embed = {
        "title": "📈 월간 환율 리포트",
        "description": f"이번 달 USD/KRW 변동 요약",
        "color": COLOR_INFO,
        "fields": [
            {"name": "현재", "value": f"`{fx_rate:,.2f}`", "inline": True},
            {"name": "월 평균", "value": f"`{avg:,.2f}`", "inline": True},
            {"name": "변동폭", "value": f"`{volatility:.2f}%`", "inline": True},
            {"name": "최고", "value": f"`{high:,.2f}`", "inline": True},
            {"name": "최저", "value": f"`{low:,.2f}`", "inline": True},
            {
                "name": "다음 달 예상 인당",
                "value": f"`{next_month_estimate:,}원`",
                "inline": True,
            },
        ],
        "footer": {"text": "안전 마진 5% 적용 기준"},
    }

    _post_message(bot_token, channel_id, {"embeds": [embed]})


def _render_deposit_status(deposits: DepositSnapshot, members_count: int) -> str:
    paid_count = deposits.paid_count
    if paid_count == 0:
        return f"⬜ 0 / {members_count} (아직 입금 체크 없음)"

    lines = [f"✅ {paid_count} / {members_count}"]
    for name in deposits.paid_users:
        lines.append(f"  • {name}")
    return "\n".join(lines)


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
