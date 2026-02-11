import datetime as dt
from typing import Any, Dict, List, Optional

from .constants import (
    ALLOWED_SOURCE_DOMAINS,
    DAYS,
    DAY_TO_IDX,
    IDX_TO_DAY,
    PLAN_STATUS_OPTIONS,
    STATUS_SORT_PRIORITY,
)


def today() -> dt.date:
    return dt.date.today()


def week_key(d: Optional[dt.date] = None) -> str:
    d = d or today()
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_start_from_key(wk: str) -> dt.date:
    try:
        y_str, w_str = wk.split("-W")
        y = int(y_str)
        w = int(w_str)
        return dt.date.fromisocalendar(y, w, 1)
    except Exception:
        y, w, _ = today().isocalendar()
        return dt.date.fromisocalendar(y, w, 1)


def week_of_month(d: dt.date) -> int:
    first = d.replace(day=1)
    first_monday = first - dt.timedelta(days=first.weekday())
    this_monday = d - dt.timedelta(days=d.weekday())
    return (this_monday - first_monday).days // 7 + 1


def week_label_yy_mm_ww_from_week_start(week_start: dt.date) -> str:
    yy = week_start.year % 100
    mm = week_start.month
    ww = week_of_month(week_start)
    return f"{yy:02d}년 {mm:02d}월 {ww:02d}주"


def is_allowed_url(url: str) -> bool:
    u = (url or "").lower()
    return u.startswith("http") and any(dom in u for dom in ALLOWED_SOURCE_DOMAINS)


def detect_high_risk(text: str) -> bool:
    k = [
        "자해", "죽고", "극단", "우울", "공황", "자살", "리스트컷",
        "진단", "치료", "처방", "약", "병원",
        "대출", "빚", "투자", "코인", "주식", "세금",
        "고소", "합의", "소송", "불법", "사기", "폭력",
    ]
    t = (text or "").lower()
    return any(x in t for x in k)


def normalize_day_label(day: str) -> str:
    d = (day or "").strip()
    return d if d in DAYS else ""


def task_uid(task: str, day: str, wk: str) -> str:
    h = abs(hash((task or "").strip())) % 1_000_000
    return f"{wk}_{day}_{h}"


def ensure_task_shape(t: Dict[str, Any], wk: str) -> Dict[str, Any]:
    out = {
        "week": t.get("week") or wk,
        "day": normalize_day_label(t.get("day") or ""),
        "task": (t.get("task") or "").strip(),
        "status": (t.get("status") or "").strip(),
        "hidden": bool(t.get("hidden", False)),
        "created_at": t.get("created_at") or dt.datetime.now().isoformat(),
    }
    if not out["status"]:
        if "done" in t:
            out["status"] = "체크" if bool(t.get("done")) else "진행중"
        else:
            out["status"] = "진행중"
    if out["status"] not in PLAN_STATUS_OPTIONS:
        out["status"] = "진행중"
    return out


def move_task_to_next_slot(t: Dict[str, Any]) -> Dict[str, Any]:
    wk = t.get("week") or week_key()
    day = normalize_day_label(t.get("day") or "")
    if not day:
        t["day"] = "월"
        t["week"] = wk
        return t

    if day != "일":
        t["day"] = IDX_TO_DAY[DAY_TO_IDX[day] + 1]
        t["week"] = wk
        return t

    start = week_start_from_key(wk)
    next_start = start + dt.timedelta(days=7)
    t["week"] = week_key(next_start)
    t["day"] = "월"
    return t


def sort_tasks_for_day(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        items,
        key=lambda x: (STATUS_SORT_PRIORITY.get(x.get("status"), 9), (x.get("created_at") or "")),
    )


def _parse_labeled_value(text: str, label: str) -> str:
    for line in (text or "").splitlines():
        if label not in line:
            continue
        parts = line.split(":", 1)
        if len(parts) == 2:
            val = parts[1].strip()
            if val:
                return val
    return ""


def extract_core_signals(text: str) -> Dict[str, str]:
    if not text:
        return {"goal": "", "current_status": "", "constraints": ""}
    goal = _parse_labeled_value(text, "목표") or _parse_labeled_value(text, "주간 목표")
    current_status = _parse_labeled_value(text, "현재") or _parse_labeled_value(text, "현재 상태")
    constraints = _parse_labeled_value(text, "제약") or _parse_labeled_value(text, "제한")
    return {
        "goal": goal,
        "current_status": current_status,
        "constraints": constraints,
    }


def merge_weekly_plan(existing: List[Dict[str, Any]], incoming: List[Dict[str, Any]], wk: str) -> List[Dict[str, Any]]:
    existing = [ensure_task_shape(t, wk) for t in (existing or []) if (t.get("task") or "").strip()]
    incoming = [ensure_task_shape(t, wk) for t in (incoming or []) if (t.get("task") or "").strip()]

    merged: List[Dict[str, Any]] = []
    seen = set()

    for t in existing:
        if not (t.get("day") or ""):
            continue
        key = (t.get("week", wk), t.get("day", ""), (t.get("task") or "").strip().lower())
        seen.add(key)
        merged.append(t)

    for t in incoming:
        if not (t.get("day") or ""):
            continue
        key = (t.get("week", wk), t.get("day", ""), (t.get("task") or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        merged.append(t)

    return merged
