"""잉여금 이력 저장.

GitHub Actions의 working-directory가 매번 초기화되므로,
잉여금 데이터는 같은 repo의 `data/surplus.json`에 커밋해서 보존합니다.

구조:
{
    "2026-04": {"per_person": 28000, "needed": 195000, "fx": 1380.5, "actual_charge_krw": 192340},
    "2026-05": {...}
}
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "surplus.json"


def load_history(path: Path = DEFAULT_PATH) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.warning("surplus.json 파싱 실패, 빈 이력으로 시작: %s", e)
        return {}


def save_history(history: dict[str, dict], path: Path = DEFAULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(history, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def previous_carryover(history: dict[str, dict]) -> int:
    """가장 최근 월의 미사용 잉여금."""
    if not history:
        return 0
    latest_key = max(history.keys())
    latest = history[latest_key]
    actual = latest.get("actual_charge_krw")
    collected = latest.get("collected_krw")
    if actual is None or collected is None:
        return 0
    return max(0, collected - actual)
