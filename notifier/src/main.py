"""메인 진입점.

GitHub Actions에서 매일 실행되며, 결제일까지 남은 일수에 따라 알림을 발송합니다.

트리거 조건:
- 결제일 7일 전 (D-7) → 결제 알림 + 환율 변동폭 그래프(1개월·3개월)
- 결제일 3일 전 (D-3) → 결제 알림만 (그래프 없음 — D-7과 중복 방지)
- 매월 1일 → 월간 리포트만 (그래프 없음)
- 그 외 → 아무 동작 없음
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import base64
import json

from .calculator import calculate_billing
from .config import Config
from .discord_client import post_billing_alert, post_monthly_report, post_rate_graph
from .fx_client import fetch_usd_krw_rate, fetch_usd_krw_history, fetch_usd_krw_history_30d
from .kv_reader import fetch_current_deposits, fetch_locked_billing_rate
from .kv_writer import put_kv_value
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
        choices=["auto", "billing-alert", "monthly-report", "rate-graph", "dry-run"],
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
    if args.mode == "rate-graph":
        return run_rate_graph(cfg, today)
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
        logger.info("D-7 — 결제 알림 + 환율 그래프 발송")
        return run_billing_alert(cfg, today, 7)

    if days_until == 3:
        logger.info("D-3 — 결제 알림 발송")
        return run_billing_alert(cfg, today, 3)

    logger.info("오늘은 알림 발송 대상이 아닙니다 (D-%d).", days_until)
    return 0


def run_billing_alert(cfg: Config, today: date, days_until: int) -> int:
    fx_rate = fetch_usd_krw_rate(cfg.koreaexim_api_key)  # 가장 최근 조회 가능한 환율

    billing_date = next_billing_date(today, cfg.billing_day)
    billing_date_str = billing_date.strftime("%Y년 %m월 %d일")

    # D-7과 D-3에서 서로 다른 환율이 쓰이지 않도록, 이번 결제 주기에서 처음
    # 조회된 환율을 KV에 고정하고 이후(D-3 등)에는 그 값을 그대로 재사용.
    fx_rate = _get_or_lock_billing_rate(cfg, billing_date, fx_rate)

    # 환율 변동폭 그래프는 D-7에서만 발송 (D-3/월간 리포트와 중복 발송 방지)
    if days_until == 7:
        try:
            _send_rate_graphs(cfg, today, fx_rate, cache_kv=True)
        except Exception as e:
            logger.warning("결제 알림 환율 그래프 발송 실패 (무시): %s", e)

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

    fx_history_30d = fetch_usd_krw_history_30d(cfg.koreaexim_api_key)
    if not fx_history_30d:
        fx_history_30d = [(today.isoformat(), fx_rate)]
    elif fx_history_30d[-1][0] != today.isoformat():
        fx_history_30d.append((today.isoformat(), fx_rate))

    _save_rate_snapshot_to_kv(cfg, fx_rate, fx_history_30d, today)

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


def run_rate_graph(cfg: Config, today: date) -> int:
    """최근 1개월·3개월 환율 그래프 2장을 생성해 Discord에 발송 (수동 실행 전용)."""
    fx_rate = fetch_usd_krw_rate(cfg.koreaexim_api_key)
    if not _send_rate_graphs(cfg, today, fx_rate, cache_kv=True):
        logger.error("환율 이력 데이터를 가져올 수 없습니다.")
        return 1
    return 0


def _send_rate_graphs(cfg: Config, today: date, fx_rate: float, *, cache_kv: bool) -> bool:
    """최근 1개월·3개월 환율 그래프 2장을 생성해 Discord에 발송.

    cache_kv=True면 /rate 커맨드가 즉시 반환할 수 있도록 KV에도 캐시 저장.
    이력 데이터를 가져오지 못하면 아무것도 보내지 않고 False 반환.
    """
    from .graph_generator import generate_fx_graph

    history = fetch_usd_krw_history(cfg.koreaexim_api_key, business_days=90)
    if not history:
        return False

    # API는 11시 이전 당일 데이터를 제공하지 않으므로 오늘 값을 명시적으로 포함
    if history[-1][0] != today.isoformat():
        history.append((today.isoformat(), fx_rate))

    history_3m = history
    history_1m = history[-30:]  # 최근 30 영업일 = 1개월

    def _stats(h: list[tuple[str, float]]) -> dict:
        rates = [r for _, r in h]
        return {"avg": sum(rates) / len(rates), "high": max(rates), "low": min(rates), "count": len(rates)}

    image_1m = generate_fx_graph(history_1m)
    image_3m = generate_fx_graph(history_3m)

    post_rate_graph(
        bot_token=cfg.bot_token,
        channel_id=cfg.channel_id,
        image_1m=image_1m,
        image_3m=image_3m,
        fx_rate=fx_rate,
        stats_1m=_stats(history_1m),
        stats_3m=_stats(history_3m),
    )

    if cache_kv:
        # KV 캐시: /rate 커맨드는 1M 그래프를 반환
        _save_rate_snapshot_to_kv(cfg, fx_rate, history_1m, today)
        _cache_rate_graph_to_kv(cfg, image_1m)

    return True


def _get_or_lock_billing_rate(cfg: Config, billing_date: date, spot_rate: float) -> float:
    """이번 결제 주기(billing_date)에 고정할 환율을 반환.

    D-7에서 이미 고정한 값이 있으면 그대로 재사용하고(D-3과 동일한 환율 보장),
    없으면(이번 주기 첫 조회) 지금 조회한 스팟 환율을 KV에 고정해 반환합니다.
    """
    billing_date_iso = billing_date.isoformat()
    locked = fetch_locked_billing_rate(
        cfg.cf_account_id, cfg.cf_kv_namespace_id, cfg.cf_api_token, billing_date_iso,
    )
    if locked is not None:
        logger.info("이번 결제 주기(%s) 고정 환율 재사용: %.2f", billing_date_iso, locked)
        return locked

    try:
        put_kv_value(
            cfg.cf_account_id, cfg.cf_kv_namespace_id, cfg.cf_api_token,
            "fx:locked_rate", json.dumps({"billing_date": billing_date_iso, "rate": spot_rate}),
        )
        logger.info("이번 결제 주기(%s) 환율 고정: %.2f", billing_date_iso, spot_rate)
    except Exception as e:
        logger.warning("환율 고정 KV 저장 실패 (이번 실행은 스팟 환율로 계속 진행): %s", e)
    return spot_rate


def _cache_rate_graph_to_kv(cfg: Config, image_bytes: bytes) -> None:
    """PNG를 base64로 인코딩해 KV에 저장. Workers /rate 커맨드가 이 값을 읽어 반환."""
    encoded = base64.b64encode(image_bytes).decode("ascii")
    try:
        put_kv_value(
            cfg.cf_account_id, cfg.cf_kv_namespace_id, cfg.cf_api_token,
            "fx:rate_graph", encoded,
        )
        logger.info("환율 그래프 KV 캐시 저장 완료 (%d bytes → %d chars)", len(image_bytes), len(encoded))
    except Exception as e:
        logger.warning("그래프 KV 캐시 저장 실패 (무시): %s", e)


def _save_rate_snapshot_to_kv(
    cfg: Config,
    fx_rate: float,
    history: list[tuple[str, float]],
    today: date,
) -> None:
    """최신 환율 스냅샷을 KV에 저장 (/rate 커맨드용)."""
    rates = [r for _, r in history]
    snapshot = {
        "rate": round(fx_rate, 2),
        "avg_30d": round(sum(rates) / len(rates), 2) if rates else round(fx_rate, 2),
        "high_30d": round(max(rates), 2) if rates else round(fx_rate, 2),
        "low_30d": round(min(rates), 2) if rates else round(fx_rate, 2),
        "updated_at": today.isoformat(),
        "data_points": len(rates),
    }
    try:
        put_kv_value(
            cfg.cf_account_id,
            cfg.cf_kv_namespace_id,
            cfg.cf_api_token,
            "fx:latest_rate",
            json.dumps(snapshot),
        )
    except Exception as e:
        logger.warning("KV 스냅샷 저장 실패 (무시): %s", e)


def run_dry_run(cfg: Config, today: date) -> int:
    """실제 발송 없이 계산 결과만 출력."""
    fx_rate = fetch_usd_krw_rate(cfg.koreaexim_api_key)

    # 이번 결제 주기에 고정된 환율이 있으면 실제 billing-alert와 동일하게 그 값을 미리보기
    # (dry-run은 조회만 하고 KV에 새로 고정하지는 않음)
    billing_date = next_billing_date(today, cfg.billing_day)
    locked_rate = fetch_locked_billing_rate(
        cfg.cf_account_id, cfg.cf_kv_namespace_id, cfg.cf_api_token, billing_date.isoformat(),
    )
    effective_rate = locked_rate if locked_rate is not None else fx_rate

    history = load_history()
    carryover = previous_carryover(history)

    calc = calculate_billing(
        fx_rate=effective_rate,
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
    print(f"환율(스팟): {fx_rate:,.2f} KRW/USD")
    if locked_rate is not None:
        print(f"환율(이번 결제 주기 고정값, {billing_date}): {locked_rate:,.2f} KRW/USD")
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
