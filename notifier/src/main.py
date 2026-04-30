"""메인 진입점.

GitHub Actions에서 매일 실행되며, 결제일까지 남은 일수에 따라 알림을 발송합니다.

트리거 조건:
- 결제일 7일 전 → D-7 알림
- 결제일 3일 전 → D-3 알림
- 매월 1일 → 월간 리포트
- 그 외 → 아무 동작 없음
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .calculator import calculate_billing
from .config import Config
from .discord_client import post_billing_alert, post_monthly_report
from .fx_client import fetch_usd_krw_rate
from .kv_reader import fetch_current_deposits
from .surplus_store import load_history, previous_carryover

KST = ZoneInfo("Asia/Seoul")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["auto", "billing-alert", "monthly-report", "dry-run"],
        default="auto",
        help="auto: 날짜에 따라 자동 결정, dry-run: 실제 발송 없이 계산만 출력",
    )
    parser.add_argument(
        "--force-days",
        type=int,
        default=None,
        help="강제로 D-N 알림 발송 (테스트용)",
    )
    args = parser.parse_args()

    cfg = Config.from_env()
    today = datetime.now(KST).date()

    if args.mode == "auto":
        return run_auto(cfg, today)
    if args.mode == "billing-alert":
        days = args.force_days if args.force_days is not None else 7
        return run_billing_alert(cfg, today, days)
    if args.mode == "monthly-report":
        return run_monthly_report(cfg, today)
    if args.mode == "dry-run":
        return run_dry_run(cfg, today)
    return 1


def run_auto(cfg: Config, today: date) -> int:
    """오늘 날짜 기준 적절한 알림 자동 트리거."""
    days_until = days_until_billing(today, cfg.billing_day)

    if today.day == 1:
        logger.info("매월 1일 — 월간 리포트 발송")
        return run_monthly_report(cfg, today)

    if days_until == 7:
        logger.info("D-7 — 결제 알림 발송")
        return run_billing_alert(cfg, today, 7)

    if days_until == 3:
        logger.info("D-3 — 결제 알림 발송")
        return run_billing_alert(cfg, today, 3)

    logger.info("오늘은 알림 발송 대상이 아닙니다 (D-%d).", days_until)
    return 0


def run_billing_alert(cfg: Config, today: date, days_until: int) -> int:
    fx_rate = fetch_usd_krw_rate(cfg.koreaexim_api_key)
    history = load_history()
    carryover = previous_carryover(history)

    calc = calculate_billing(
        fx_rate=fx_rate,
        standard_seats=cfg.standard_seats,
        premium_seats=cfg.premium_seats,
        standard_price_usd=cfg.standard_price_usd,
        premium_price_usd=cfg.premium_price_usd,
        vat_rate=cfg.vat_rate,
        safety_margin=cfg.safety_margin,
        carryover_krw=carryover,
    )

    deposits = fetch_current_deposits(
        account_id=cfg.cf_account_id,
        namespace_id=cfg.cf_kv_namespace_id,
        api_token=cfg.cf_api_token,
    )

    billing_date = next_billing_date(today, cfg.billing_day)
    billing_date_str = billing_date.strftime("%Y년 %m월 %d일")

    post_billing_alert(
        bot_token=cfg.bot_token,
        channel_id=cfg.channel_id,
        calc=calc,
        deposits=deposits,
        days_until_billing=days_until,
        billing_date_str=billing_date_str,
    )
    return 0


def run_monthly_report(cfg: Config, today: date) -> int:
    fx_rate = fetch_usd_krw_rate(cfg.koreaexim_api_key)

    # TODO: 환율 이력 30일치 — 현재는 단순 구현
    fx_history_30d: list[tuple[str, float]] = [(today.isoformat(), fx_rate)]

    estimate = calculate_billing(
        fx_rate=fx_rate,
        standard_seats=cfg.standard_seats,
        premium_seats=cfg.premium_seats,
        standard_price_usd=cfg.standard_price_usd,
        premium_price_usd=cfg.premium_price_usd,
        vat_rate=cfg.vat_rate,
        safety_margin=cfg.safety_margin,
        carryover_krw=0,
    )

    post_monthly_report(
        bot_token=cfg.bot_token,
        channel_id=cfg.channel_id,
        fx_rate=fx_rate,
        fx_history_30d=fx_history_30d,
        next_month_calc=estimate,
    )
    return 0


def run_dry_run(cfg: Config, today: date) -> int:
    """실제 발송 없이 계산 결과만 출력."""
    fx_rate = fetch_usd_krw_rate(cfg.koreaexim_api_key)
    history = load_history()
    carryover = previous_carryover(history)

    calc = calculate_billing(
        fx_rate=fx_rate,
        standard_seats=cfg.standard_seats,
        premium_seats=cfg.premium_seats,
        standard_price_usd=cfg.standard_price_usd,
        premium_price_usd=cfg.premium_price_usd,
        vat_rate=cfg.vat_rate,
        safety_margin=cfg.safety_margin,
        carryover_krw=carryover,
    )

    print("=" * 50)
    print(f"오늘: {today}")
    print(
        f"시트: Standard {cfg.standard_seats}명 (${cfg.standard_price_usd}/시트) + "
        f"Premium {cfg.premium_seats}명 (${cfg.premium_price_usd}/시트)"
    )
    print(f"환율: {fx_rate:,.2f} KRW/USD")
    print(f"마진: {cfg.safety_margin*100:.0f}%, VAT: {cfg.vat_rate*100:.0f}%")
    print(f"이월: {carryover:,}원")
    print(f"총 청구 USD (VAT 포함): ${calc.total_usd:.2f}")
    print(f"필요 KRW: {calc.total_krw_needed:,}원")
    print()
    if calc.standard.seat_count > 0:
        print(
            f"Standard 인당 입금: {calc.standard.per_person_krw:,}원 "
            f"× {calc.standard.seat_count}명"
        )
    if calc.premium.seat_count > 0:
        print(
            f"Premium 인당 입금: {calc.premium.per_person_krw:,}원 "
            f"× {calc.premium.seat_count}명"
        )
    print(f"총 모금액: {calc.total_collected_krw:,}원")
    print(f"예상 잉여: {calc.expected_surplus_krw:,}원")
    print(f"D-{days_until_billing(today, cfg.billing_day)} until billing")
    print("=" * 50)
    return 0


def days_until_billing(today: date, billing_day: int) -> int:
    """다음 결제일까지 남은 일수."""
    return (next_billing_date(today, billing_day) - today).days


def next_billing_date(today: date, billing_day: int) -> date:
    """오늘 기준 다음 결제일."""
    try:
        candidate = today.replace(day=billing_day)
    except ValueError:
        # 28일 이후 결제일이고 그 달에 그 일자가 없는 경우 → 그 달 말일로 보정
        candidate = (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    if candidate < today:
        # 이번 달 결제일이 이미 지남 → 다음 달
        next_month = today.replace(day=1) + timedelta(days=32)
        try:
            candidate = next_month.replace(day=billing_day)
        except ValueError:
            candidate = (next_month.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return candidate


if __name__ == "__main__":
    sys.exit(main())
