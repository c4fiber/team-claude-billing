"""환율 그래프 생성.

GitHub Actions는 디스플레이 서버가 없으므로 Agg 백엔드를 pyplot import 전에 설정.
annotation 텍스트는 ASCII만 사용해 한글 폰트 의존성을 제거.
"""

from __future__ import annotations

import io
from datetime import datetime

import matplotlib
matplotlib.use("Agg")  # non-interactive backend — must be before pyplot import
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

_BG_COLOR = "#2b2d31"       # Discord dark 배경
_LINE_COLOR = "#5865F2"     # Discord blurple
_FILL_COLOR = "#5865F2"
_TEXT_COLOR = "#ffffff"
_GRID_COLOR = "#ffffff"
_HIGH_COLOR = "#57f287"     # Discord green
_LOW_COLOR = "#ed4245"      # Discord red
_CUR_COLOR = "#fee75c"      # Discord yellow


def generate_fx_graph(history: list[tuple[str, float]]) -> bytes:
    """30 영업일치 USD/KRW 이력을 라인 차트 PNG로 반환.

    Args:
        history: [(YYYY-MM-DD, rate), ...] 오름차순 정렬된 이력
    Returns:
        PNG 바이트
    """
    if not history:
        raise ValueError("history is empty")

    dates = [datetime.fromisoformat(d).date() for d, _ in history]
    rates = [r for _, r in history]

    high_idx = rates.index(max(rates))
    low_idx = rates.index(min(rates))

    fig, ax = plt.subplots(figsize=(10, 4), facecolor=_BG_COLOR)
    ax.set_facecolor(_BG_COLOR)

    # 라인 + 면적 채우기
    ax.plot(dates, rates, color=_LINE_COLOR, linewidth=2, zorder=3)
    ax.fill_between(dates, rates, alpha=0.15, color=_FILL_COLOR, zorder=2)

    # 최고/최저/현재 마커
    ax.plot(dates[high_idx], rates[high_idx], marker="^", color=_HIGH_COLOR, markersize=8, zorder=4)
    ax.plot(dates[low_idx], rates[low_idx], marker="v", color=_LOW_COLOR, markersize=8, zorder=4)
    ax.plot(dates[-1], rates[-1], marker="o", color=_CUR_COLOR, markersize=8, zorder=4)

    # annotation — ASCII only (no Korean font dependency)
    ax.annotate(
        f"High {rates[high_idx]:,.0f}",
        xy=(dates[high_idx], rates[high_idx]),
        xytext=(0, 10),
        textcoords="offset points",
        ha="center",
        color=_HIGH_COLOR,
        fontsize=8,
    )
    ax.annotate(
        f"Low {rates[low_idx]:,.0f}",
        xy=(dates[low_idx], rates[low_idx]),
        xytext=(0, -16),
        textcoords="offset points",
        ha="center",
        color=_LOW_COLOR,
        fontsize=8,
    )
    ax.annotate(
        f"Now {rates[-1]:,.0f}",
        xy=(dates[-1], rates[-1]),
        xytext=(0, 10),
        textcoords="offset points",
        ha="center",
        color=_CUR_COLOR,
        fontsize=8,
    )

    # X축: MM/DD 형식, 매주 눈금
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    plt.xticks(rotation=30, ha="right", color=_TEXT_COLOR, fontsize=8)

    # Y축: 천 단위 콤마
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    plt.yticks(color=_TEXT_COLOR, fontsize=8)

    # 가로 그리드
    ax.yaxis.grid(True, linestyle="--", alpha=0.3, color=_GRID_COLOR, zorder=1)
    ax.set_axisbelow(True)
    ax.xaxis.grid(False)

    for spine in ax.spines.values():
        spine.set_edgecolor("#3f4147")

    ax.set_title(
        f"USD/KRW Exchange Rate — Last {len(history)} Business Days",
        color=_TEXT_COLOR,
        fontsize=11,
        pad=10,
    )

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor=_BG_COLOR)
    plt.close(fig)
    buf.seek(0)
    return buf.read()
