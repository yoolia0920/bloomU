import json
import datetime as dt
from typing import Dict, Any, List, Optional

import pandas as pd
import requests
import streamlit as st
from openai import OpenAI


# =========================
# App Identity
# =========================
APP_NAME = "Bloom U"
SLOGAN = '“Where You Begin to Bloom” – 20대의 모든 ‘처음’을 함께 합니다.'
ONE_LINER = "내 상황 · 수준 · 성향에 맞춰 함께 성장해주는 개인 트레이너형 AI"
TARGET = "20대 대학생"

MODEL = "gpt-5-mini"

TONE_OPTIONS = ["따뜻한 친구형", "현실직언형", "선배멘토형", "코치·트레이너형", "부모님형"]
LEVEL_OPTIONS = ["완전 입문", "진행 중", "고급자"]
DOMAIN_OPTIONS = ["진로", "연애", "전공공부", "일상 멘탈관리", "개인사정(가족/경제/관계)", "기타"]

UNCERTAINTY_OPTIONS = ["확실(규정/공식)", "보통(평균 통계/경험치)", "추정(개인화 필요)"]

BADGES = [
    ("first_chat", "첫 대화 🌱", "Bloom U와 첫 대화를 시작했어요."),
    ("first_plan", "첫 플랜 🗓️", "주간 액티브 플랜을 만들었어요."),
    ("plan_3_done", "실천가 💪", "플랜에서 3개 이상의 액션을 완료했어요."),
    ("plan_7_done", "최고의 실천가🔥💪", "플랜을 모두 완료했어요!"),
    ("weekly_checkin", "체크인 📈", "주간 자신감 설문을 완료했어요."),
    ("streak_3", "3일 연속 🔥", "3일 연속으로 Bloom U를 사용했어요."),
    ("streak_7", "7일 연속 🔥🔥", "일주일 동안 Bloom U를 사용했어요."),
    ("streak_31", "한 달 연속 성실함🔥🔥🔥", "한 달 동안 Bloom U를 사용했어요!"),
]

ALLOWED_SOURCE_DOMAINS = [
    ".gov", ".edu", "who.int", "oecd.org", "nih.gov", "cdc.gov", "apa.org",
    "indeed.com", "glassdoor.com", "ncs.gov", "moel.go.kr", "korea.kr"
]

PLAN_STATUS_OPTIONS = ["체크", "진행중", "미루기"]
STATUS_SORT_PRIORITY = {"진행중": 0, "미루기": 1, "체크": 2}
DAYS = ["월", "화", "수", "목", "금", "토", "일"]
DAY_TO_IDX = {d: i for i, d in enumerate(DAYS)}
IDX_TO_DAY = {i: d for d, i in DAY_TO_IDX.items()}

# ✅ 톤 옵션별 “말투 규칙” (프롬프트에 강제 주입)
TONE_GUIDE = {
    "따뜻한 친구형": [
        "부드럽고 다정한 말투. 시작은 공감 1~2문장.",
        "제안형 표현(‘~해볼래?’, ‘괜찮다면…’)을 사용.",
        "단정/비난 금지. 대안은 2~3개로 간단히."
    ],
    "현실직언형": [
        "간결·직설. 핵심부터 말하고 다음 행동을 명확히.",
        "핑계는 부드럽게 끊고 ‘지금 할 것’ 1~3개 제시.",
        "과장된 위로는 하지 말고 실행에 집중."
    ],
    "선배멘토형": [
        "선배처럼 공감 + 경험/일반론 기반 조언.",
        "장기/단기 로드맵과 우선순위를 잡아준다.",
        "마지막에 질문 1개만 던져 선택을 돕는다."
    ],
    "코치·트레이너형": [
        "목표지향, 측정 가능한 행동 중심.",
        "시간 박스(예: 15분) + 체크리스트 + 피드백 루프 포함.",
        "불필요한 감정 과잉 없이 ‘실행/측정’ 중심."
    ],
    "부모님형": [
        "따뜻하지만 단호. 안전/건강/기본 루틴을 먼저 챙김.",
        "수면/식사/무리 금지 같은 기본 루틴 1회 언급.",
        "비난은 금지, 보호적 뉘앙스로 조언."
    ],
}


# =========================
# Utilities
# =========================
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
        return dt.date.fromisocalendar(y, w, 1)  # Monday
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
        "고소", "합의", "소송", "불법", "사기", "폭력"
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
    """
    '미루기' 선택 시:
    - day가 월~토: 다음 요일로 이동 (week 유지)
    - day가 일: 다음 주 월로 이동 (week +1)
    - day가 비어있으면: 이번 주 '월'로 배치 (week 유지)
    """
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
        key=lambda x: (STATUS_SORT_PRIORITY.get(x.get("status"), 9), (x.get("created_at") or ""))
    )

def update_streak_and_badges():
    last = st.session_state.usage.get("last_active")
    t = today()
    if last is None:
        st.session_state.usage["streak"] = 1
    else:
        last_d = dt.date.fromisoformat(last)
        delta = (t - last_d).days
        if delta == 0:
            pass
        elif delta == 1:
            st.session_state.usage["streak"] = st.session_state.usage.get("streak", 1) + 1
        else:
            st.session_state.usage["streak"] = 1
    st.session_state.usage["last_active"] = t.isoformat()

    if st.session_state.usage.get("streak", 0) >= 3:
        st.session_state.badges_unlocked.add("streak_3")

def ensure_core_context():
    if "core_context" not in st.session_state:
        st.session_state.core_context = {
            "profile": {},
            "weeks": {},
        }

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

def get_week_core_context(wk: str) -> Dict[str, Any]:
    ensure_core_context()
    weeks = st.session_state.core_context.setdefault("weeks", {})
    if wk not in weeks:
        weeks[wk] = {
            "week": wk,
            "goal": "",
            "current_status": "",
            "constraints": "",
            "last_user_message": "",
            "survey": {},
            "ab_metrics": {},
            "plan": {"tasks": 0, "done": 0, "completion": None},
            "updated_at": dt.datetime.now().isoformat(),
        }
    return weeks[wk]

def update_core_context_from_settings():
    ensure_core_context()
    st.session_state.core_context["profile"] = {
        "tone": st.session_state.settings.get("tone"),
        "level": st.session_state.settings.get("level"),
        "domain": st.session_state.settings.get("domain"),
        "nickname": st.session_state.settings.get("nickname"),
        "evidence_mode": st.session_state.settings.get("evidence_mode"),
    }

def update_core_context_from_chat(user_text: str, wk: str):
    core = get_week_core_context(wk)
    signals = extract_core_signals(user_text)
    if signals.get("goal"):
        core["goal"] = signals["goal"]
    if signals.get("current_status"):
        core["current_status"] = signals["current_status"]
    if signals.get("constraints"):
        core["constraints"] = signals["constraints"]
    core["last_user_message"] = user_text
    core["updated_at"] = dt.datetime.now().isoformat()

def update_core_context_from_plan(wk: str, tasks: Optional[List[Dict[str, Any]]] = None):
    core = get_week_core_context(wk)
    tasks = tasks if tasks is not None else (st.session_state.plan_by_week.get(wk, []) or [])
    done = sum(1 for t in tasks if t.get("status") == "체크")
    total = len(tasks)
    completion = round(100 * done / total, 1) if total else None
    core["plan"] = {"tasks": total, "done": done, "completion": completion}
    core["updated_at"] = dt.datetime.now().isoformat()

def update_core_context_from_survey(wk: str, survey: Dict[str, Any]):
    core = get_week_core_context(wk)
    core["survey"] = dict(survey or {})
    core["updated_at"] = dt.datetime.now().isoformat()

def update_core_context_from_ab_metrics(wk: str, metrics: Dict[str, Any]):
    core = get_week_core_context(wk)
    core["ab_metrics"] = dict(metrics or {})
    core["updated_at"] = dt.datetime.now().isoformat()

def unlock_badges():
    if any(m["role"] == "user" for m in st.session_state.messages):
        st.session_state.badges_unlocked.add("first_chat")

    any_tasks = any((st.session_state.plan_by_week.get(wk) or []) for wk in st.session_state.plan_by_week.keys())
    if any_tasks:
        st.session_state.badges_unlocked.add("first_plan")

    wk = st.session_state.active_plan.get("week", week_key())
    tasks = st.session_state.plan_by_week.get(wk, []) or []
    update_core_context_from_plan(wk, tasks)
    done = sum(1 for t in tasks if t.get("status") == "체크")
    if done >= 3:
        st.session_state.badges_unlocked.add("plan_3_done")

    if tasks and all(t.get("status") == "체크" for t in tasks):
        st.session_state.badges_unlocked.add("plan_7_done")

    if week_key() in st.session_state.survey:
        st.session_state.badges_unlocked.add("weekly_checkin")

def ensure_state():
    if "settings" not in st.session_state:
        st.session_state.settings = {
            "tone": TONE_OPTIONS[0],
            "level": LEVEL_OPTIONS[0],
            "domain": DOMAIN_OPTIONS[0],
            "evidence_mode": True,
            "anonymous_mode": True,
            "nickname": "익명",
        }
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "plan_by_week" not in st.session_state:
        st.session_state.plan_by_week = {}
    if "active_plan" not in st.session_state:
        st.session_state.active_plan = {
            "week": week_key(),
            "planA": [],
            "planB": [],
        }
    if "ab_metrics" not in st.session_state:
        st.session_state.ab_metrics = {}
    if "survey" not in st.session_state:
        st.session_state.survey = {}
    if "badges_unlocked" not in st.session_state:
        st.session_state.badges_unlocked = set()
    if "usage" not in st.session_state:
        st.session_state.usage = {"last_active": None, "streak": 0}
    if "last_ai_answer" not in st.session_state:
        st.session_state.last_ai_answer = None
    if "last_evidence_mode" not in st.session_state:
        st.session_state.last_evidence_mode = False
    if "last_sources_pool" not in st.session_state:
        st.session_state.last_sources_pool = []
    ensure_core_context()

    # ✅ 사용자 Notion 입력 기반 저장(1번)
    if "notion" not in st.session_state:
        st.session_state.notion = {
            "token": "",
            "db_id": "",
            "title_prop": "Name",  # 사용자 DB의 Title property 이름
        }
        # ✅ 데일리 패턴 체크 저장소 (날짜별 누적)
    # (호환) daily_pattern / daily_patterns 둘 다 지원
    if "daily_pattern" not in st.session_state and "daily_patterns" not in st.session_state:
        st.session_state.daily_pattern = {}

    # 누군가 daily_patterns를 쓰는 경우도 있어 동기화
    if "daily_patterns" not in st.session_state:
        st.session_state.daily_patterns = st.session_state.daily_pattern
    else:
        st.session_state.daily_pattern = st.session_state.daily_patterns

# =========================
# ✅ NEW: Weekly Plan Merge (누적 저장 + 중복 방지)
# =========================
def merge_weekly_plan(existing: List[Dict[str, Any]], incoming: List[Dict[str, Any]], wk: str) -> List[Dict[str, Any]]:
    """
    기존 주간 플랜(existing)에 새로 생성된 플랜(incoming)을 '누적'합니다.
    - 중복 기준: (week, day, task) 동일하면 기존 것을 유지 (status/created_at 유지)
    - task 공백은 제외
    - day가 비어있는 건 누적에서 제외(원하면 아래 조건을 바꿀 수 있어요)
    """
    existing = [ensure_task_shape(t, wk) for t in (existing or []) if (t.get("task") or "").strip()]
    incoming = [ensure_task_shape(t, wk) for t in (incoming or []) if (t.get("task") or "").strip()]

    merged: List[Dict[str, Any]] = []
    seen = set()

    # 1) 기존 먼저 넣기 (기존 유지)
    for t in existing:
        if not (t.get("day") or ""):
            continue
        key = (t.get("week", wk), t.get("day", ""), (t.get("task") or "").strip().lower())
        seen.add(key)
        merged.append(t)

    # 2) 새 플랜 추가 (중복 제외)
    for t in incoming:
        if not (t.get("day") or ""):
            continue
        key = (t.get("week", wk), t.get("day", ""), (t.get("task") or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        merged.append(t)

    return merged


# =========================
# Evidence Search
# =========================
def serper_search(query: str, api_key: str, k: int = 5) -> List[Dict[str, str]]:
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": query, "num": k}
    r = requests.post(url, headers=headers, json=payload, timeout=12)
    r.raise_for_status()
    data = r.json()
    out = []
    for item in (data.get("organic") or [])[:k]:
        link = item.get("link", "")
        title = item.get("title", "")
        if is_allowed_url(link):
            out.append({"title": title, "url": link})
    return out

def curated_sources(domain: str) -> List[Dict[str, str]]:
    if domain == "진로":
        return [
            {"title": "고용노동부(MOEL) - 청년/취업 지원", "url": "https://www.moel.go.kr/"},
            {"title": "OECD - Education & Skills", "url": "https://www.oecd.org/education/"},
            {"title": "Indeed Career Guide", "url": "https://www.indeed.com/career-advice"},
        ]
    if domain == "전공공부":
        return [
            {"title": "MIT OpenCourseWare", "url": "https://ocw.mit.edu/"},
            {"title": "Khan Academy", "url": "https://www.khanacademy.org/"},
            {"title": "Google Scholar", "url": "https://scholar.google.com/"},
        ]
    if domain == "일상 멘탈관리":
        return [
            {"title": "WHO - Mental health", "url": "https://www.who.int/health-topics/mental-health"},
            {"title": "CDC - Mental Health", "url": "https://www.cdc.gov/mentalhealth/"},
            {"title": "APA - Psychology Topics", "url": "https://www.apa.org/topics"},
        ]
    if domain == "연애":
        return [
            {"title": "APA - Relationships", "url": "https://www.apa.org/topics/relationships"},
            {"title": "CDC - Healthy Relationships", "url": "https://www.cdc.gov/"},
            {"title": "University Counseling Center resources (예: .edu)", "url": "https://www.google.com/search?q=site%3Aedu+healthy+relationships"},
        ]
    if domain == "개인사정(가족/경제/관계)":
        return [
            {"title": "korea.kr (정부 정책/지원)", "url": "https://www.korea.kr/"},
            {"title": "NIH - Stress & Coping", "url": "https://www.nih.gov/"},
            {"title": "WHO - Social determinants", "url": "https://www.who.int/"},
        ]
    return [
        {"title": "korea.kr", "url": "https://www.korea.kr/"},
        {"title": "WHO", "url": "https://www.who.int/"},
        {"title": "OECD", "url": "https://www.oecd.org/"},
    ]


# =========================
# Prompting & Parsing
# =========================
def build_system_prompt(settings: Dict[str, Any]) -> str:
    nickname = settings["nickname"]
    tone = settings["tone"]
    level = settings["level"]
    domain = settings["domain"]
    evidence_mode = settings["evidence_mode"]

    tone_rules = "\n".join([f"- {x}" for x in TONE_GUIDE.get(tone, [])])

    return f"""
당신은 20대 대학생들이 맞이할 모든 첫 시작을 도울 러닝메이트 코칭 매니저입니다.
사용자의 닉네임은 '{nickname}'이며 반드시 이 이름으로 부르세요.

[말투/레벨/분야]
- 말투: {tone}
- 레벨: {level}
- 분야: {domain}

[말투 규칙(반드시 준수)]
{tone_rules}

[핵심 원칙]
- 공감(다정함) + 현실 조언(실행 가능한 조언)을 함께 제공합니다.
- 사실(정보)과 전략(개인화 조언)을 명확히 구분합니다.
- 불확실성 태그를 반드시 붙입니다: {", ".join(UNCERTAINTY_OPTIONS)}
- A/B 플랜(서로 다른 전략 2개)을 제공하고, 측정 지표를 포함합니다:
  - 불안도(0~10), 실천도(%), 결과물/성과(자유기입)

[리스크]
- 법/의료/정신건강/재정 등 고위험 가능성이 있으면:
  - 전문가 상담 권고 + 대체 안전 행동 2~4개를 반드시 포함합니다.

[증거기반모드]
- evidence_mode={str(evidence_mode).lower()}
- 증거기반모드가 켜져 있을 때, '사실(정보)' 항목에는 아래 'SOURCES'로 제공되는 링크들만 근거로 사용하세요.
- 링크가 충분하지 않으면, 사실 항목은 최소화하고 불확실성 태그를 '추정' 또는 '보통'으로 조정하세요.

[출력 형식]
반드시 JSON만 출력하세요. (설명 텍스트 금지)

JSON 스키마:
{{
  "empathy_summary": "2~4문장",
  "facts": [{{"text":"...", "uncertainty":"확실/보통/추정", "sources":[{{"title":"...","url":"..."}}, ...]}} ],
  "strategies": ["...", "..."],
  "uncertainty_tag": "확실(규정/공식) | 보통(평균 통계/경험치) | 추정(개인화 필요)",
  "ab_plans": {{
    "A": {{"title":"...", "steps":["..."], "metrics":["불안도0~10","실천도%","결과물/성과"]}},
    "B": {{"title":"...", "steps":["..."], "metrics":["불안도0~10","실천도%","결과물/성과"]}}
  }},
  "weekly_active_plan": [{{"day":"월|화|수|목|금|토|일|", "task":"...", "status":"체크|진행중|미루기"}}],
  "risk_warning": {{
     "is_high_risk": true/false,
     "message": "경고/권고",
     "safe_actions": ["...", "..."]
  }}
}}
""".strip()

def call_openai_json(api_key: str, sys_prompt: str, user_prompt: str, chat: List[Dict[str, str]]) -> Dict[str, Any]:
    client = OpenAI(api_key=api_key)
    context = chat[-12:] if len(chat) > 12 else chat

    inp = [{"role": "system", "content": sys_prompt}]
    for m in context:
        inp.append({"role": m["role"], "content": m["content"]})
    inp.append({"role": "user", "content": user_prompt})

    resp = client.responses.create(model=MODEL, input=inp)
    txt = (resp.output_text or "").strip()

    if txt.startswith("```"):
        txt = txt.strip("`")
        start = txt.find("{")
        end = txt.rfind("}")
        txt = txt[start:end + 1] if start != -1 and end != -1 else txt

    return json.loads(txt)

def normalize_and_validate(ai: Dict[str, Any], sources_pool: List[Dict[str, str]], wk: str) -> Dict[str, Any]:
    out = {
        "empathy_summary": ai.get("empathy_summary", ""),
        "facts": [],
        "strategies": ai.get("strategies", []),
        "uncertainty_tag": ai.get("uncertainty_tag", "추정(개인화 필요)"),
        "ab_plans": ai.get("ab_plans", {
            "A": {"title": "플랜 A", "steps": [], "metrics": ["불안도0~10", "실천도%", "결과물/성과"]},
            "B": {"title": "플랜 B", "steps": [], "metrics": ["불안도0~10", "실천도%", "결과물/성과"]},
        }),
        "weekly_active_plan": ai.get("weekly_active_plan", []),
        "risk_warning": ai.get("risk_warning", {"is_high_risk": False, "message": "", "safe_actions": []}),
    }

    pool_urls = {s["url"] for s in (sources_pool or []) if is_allowed_url(s.get("url", ""))}

    facts = ai.get("facts", []) or []
    for f in facts:
        uncertainty = f.get("uncertainty", "추정")
        if uncertainty == "확실":
            uncertainty_full = UNCERTAINTY_OPTIONS[0]
        elif uncertainty == "보통":
            uncertainty_full = UNCERTAINTY_OPTIONS[1]
        else:
            uncertainty_full = UNCERTAINTY_OPTIONS[2]

        srcs = []
        for s in (f.get("sources", []) or []):
            url = s.get("url", "")
            title = s.get("title", url)
            if is_allowed_url(url) and (not pool_urls or url in pool_urls):
                srcs.append({"title": title, "url": url})

        out["facts"].append({"text": f.get("text", ""), "uncertainty": uncertainty_full, "sources": srcs})

    plan = []
    for item in (out.get("weekly_active_plan") or [])[:24]:
        day = normalize_day_label(item.get("day") or "")
        status = (item.get("status") or "진행중").strip()
        if status not in PLAN_STATUS_OPTIONS:
            status = "진행중"
        plan.append({
            "week": wk,
            "day": day,
            "task": (item.get("task") or "").strip(),
            "status": status,
            "created_at": dt.datetime.now().isoformat(),
        })
    out["weekly_active_plan"] = [p for p in plan if p["task"]]
    return out


# =========================
# Rendering helpers
# =========================
def risk_safety_banner_if_needed(user_text: str):
    if detect_high_risk(user_text):
        st.warning(
            "⚠️ 이 대화는 법/의료/정신건강/재정 등 고위험 주제를 포함할 수 있어요.\n"
            "가능하면 전문가(상담센터/의료진/법률/금융 전문가)와 함께 확인해 주세요.\n\n"
            "만약 지금 매우 위험하거나 자해 충동이 있다면, 즉시 주변 도움을 요청하세요.\n"
            "- (한국) 자살예방 상담전화 1393\n- 정신건강위기 상담 1577-0199\n- 긴급상황 112/119"
        )

def render_ai_answer(ans: Dict[str, Any], evidence_mode: bool):
    st.markdown("### 1) 공감 & 상황 요약")
    st.write(ans.get("empathy_summary", ""))

    st.markdown("### 2) 사실(정보)")
    facts = ans.get("facts", [])
    if not facts:
        st.caption("이번 답변에서는 확정 가능한 사실 정보가 많지 않았어요.")
    for f in facts:
        st.write(f"- {f['text']}")
        st.caption(f"불확실성: {f['uncertainty']}")
        if evidence_mode:
            srcs = f.get("sources", [])
            if srcs:
                st.caption("근거(공식/기관 자료):")
                for s in srcs[:3]:
                    st.markdown(f"- [{s['title']}]({s['url']})")

    st.markdown("### 3) 전략(개인화 조언)")
    for s in ans.get("strategies", [])[:10]:
        st.write(f"- {s}")

    st.markdown("### 4) 불확실성 태그")
    st.info(ans.get("uncertainty_tag", "추정(개인화 필요)"))

    st.markdown("### 5) A/B 플랜")
    ab = ans.get("ab_plans", {})
    c1, c2 = st.columns(2)
    with c1:
        a = ab.get("A", {})
        st.subheader(f"플랜 A: {a.get('title','')}")
        for step in (a.get("steps") or [])[:8]:
            st.write(f"- {step}")
        st.caption("측정 지표: " + ", ".join(a.get("metrics") or []))
    with c2:
        b = ab.get("B", {})
        st.subheader(f"플랜 B: {b.get('title','')}")
        for step in (b.get("steps") or [])[:8]:
            st.write(f"- {step}")
        st.caption("측정 지표: " + ", ".join(b.get("metrics") or []))


# =========================
# Notion Export (✅ 1번: 사용자 Notion에 저장)
# =========================
def notion_ready() -> bool:
    tok = (st.session_state.notion.get("token") or "").strip()
    dbid = (st.session_state.notion.get("db_id") or "").strip()
    return bool(tok) and bool(dbid)

def notion_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

def _rt(text: str) -> Dict[str, Any]:
    return {"type": "text", "text": {"content": text}}

def build_week_plan_blocks(week_label: str, wk: str, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    blocks.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [_rt(f"주간 액티브 플랜 · {week_label}")]}
    })
    blocks.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [_rt(f"WeekKey: {wk}")]}
    })

    tasks_norm = [ensure_task_shape(t, wk) for t in (tasks or []) if (t.get("task") or "").strip()]
    for d in DAYS:
        day_items = [t for t in tasks_norm if t.get("day") == d]
        if not day_items:
            continue
        day_items = sort_tasks_for_day(day_items)

        blocks.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": [_rt(d)]}
        })
        for t in day_items:
            status = t.get("status", "진행중")
            icon = "✅" if status == "체크" else ("⏳" if status == "진행중" else "🕒")
            line = f"{icon} [{status}] {t.get('task','')}"
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [_rt(line)]}
            })

    if len(blocks) <= 2:
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [_rt("이번 주에 저장할 플랜이 없어요.")]},
        })
    return blocks[:100]

def notion_create_week_page(token: str, db_id: str, title_prop: str, week_label: str, wk: str, tasks: List[Dict[str, Any]]) -> str:
    title = f"{week_label} · Bloom U 플랜"

    # ✅ Notion DB마다 Title property 이름이 다를 수 있어서 사용자 입력값(title_prop)을 사용
    properties = {
        title_prop: {"title": [_rt(title)]}
    }

    payload = {
        "parent": {"database_id": db_id},
        "properties": properties,
        "children": build_week_plan_blocks(week_label, wk, tasks),
    }

    r = requests.post("https://api.notion.com/v1/pages", headers=notion_headers(token), json=payload, timeout=25)
    if r.status_code >= 300:
        raise RuntimeError(f"Notion 저장 실패: {r.status_code} - {r.text}")

    return (r.json() or {}).get("url", "")


# =========================
# App UI
# =========================
st.set_page_config(page_title=f"{APP_NAME} - 상담/코칭 AI", page_icon="🌸", layout="wide")
ensure_state()

# Sidebar
st.sidebar.title(f"🌸 {APP_NAME}")
st.sidebar.caption(SLOGAN)
st.sidebar.caption(ONE_LINER)
st.sidebar.divider()

api_key = st.sidebar.text_input("OpenAI API Key", type="password", value=st.secrets.get("OPENAI_API_KEY", ""))
if not api_key:
    st.sidebar.info("키를 입력하면 코칭이 시작돼요. (Streamlit Cloud에서는 Secrets로 넣는 걸 추천)")

tone = st.sidebar.selectbox("코칭 말투", TONE_OPTIONS, index=TONE_OPTIONS.index(st.session_state.settings["tone"]))
level = st.sidebar.selectbox("사용자 레벨", LEVEL_OPTIONS, index=LEVEL_OPTIONS.index(st.session_state.settings["level"]))
domain = st.sidebar.selectbox("상담 분야", DOMAIN_OPTIONS, index=DOMAIN_OPTIONS.index(st.session_state.settings["domain"]))
evidence_mode = st.sidebar.toggle("증거기반모드(사실/정보에 근거 링크)", value=st.session_state.settings["evidence_mode"])

anonymous_mode = st.sidebar.toggle("익명모드", value=st.session_state.settings["anonymous_mode"])
nickname_default = "익명" if anonymous_mode else st.session_state.settings["nickname"] or "user"
nickname = st.sidebar.text_input("닉네임(챗봇이 이 이름으로 불러요)", value=nickname_default).strip() or "익명"

st.session_state.settings.update({
    "tone": tone,
    "level": level,
    "domain": domain,
    "evidence_mode": evidence_mode,
    "anonymous_mode": anonymous_mode,
    "nickname": nickname,
})
update_core_context_from_settings()

tab = st.sidebar.radio(
    "탭",
    [
        "채팅",
        "주간 액티브 플랜",
        "전략 A/B 측정",
        "데일리 패턴 체크",   # ✅ 추가
        "뱃지",
        "주간 자가설문",
        "주간 리포트/성장 대시보드"
    ],
    index=0
)

st.sidebar.divider()
st.sidebar.caption(f"타겟 사용자: {TARGET}")
st.sidebar.caption("팁: ‘목표/기한/제약/현재 상태’를 구체적으로 적을수록 플랜이 좋아져요.")

# ✅ Notion 연결(사용자 입력 방식)
st.sidebar.markdown("### 🔗 Notion 연결(사용자)")
st.sidebar.caption("사용자 본인의 Notion에 저장하려면 토큰/DB ID를 입력해야 해요.")
st.session_state.notion["token"] = st.sidebar.text_input(
    "Notion Token (사용자)",
    type="password",
    value=st.session_state.notion.get("token", ""),
    placeholder="secret_..."
).strip()
st.session_state.notion["db_id"] = st.sidebar.text_input(
    "Notion Database ID (사용자)",
    value=st.session_state.notion.get("db_id", ""),
    placeholder="예: 0123abcd..."
).strip()
st.session_state.notion["title_prop"] = st.sidebar.text_input(
    "DB Title 속성 이름(보통 Name/제목)",
    value=st.session_state.notion.get("title_prop", "Name"),
    placeholder="예: Name"
).strip() or "Name"

if notion_ready():
    st.sidebar.success("Notion 연결 입력 완료 ✅")
else:
    st.sidebar.info("Notion 저장 기능을 쓰려면 토큰 + DB ID가 필요해요.")

# Header
st.title(f"🌸 {APP_NAME}")
st.markdown(f"**{SLOGAN}**")
st.caption(ONE_LINER)


# =========================
# Tab: Chat
# =========================
if tab == "채팅":
    st.subheader("💬 상담/코칭 챗")

    def render_recent_links():
        sources = st.session_state.last_sources_pool or []
        if not sources:
            return
        st.markdown("#### 추천 링크")
        for s in sources[:5]:
            title = s.get("title") or s.get("url")
            url = s.get("url")
            if url:
                st.markdown(f"- [{title}]({url})")
        st.divider()

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    user = st.chat_input("지금 어떤 ‘처음’을 시작하려고 해? (목표/기한/현재수준/제약을 같이 적어줘)")
    if not user and st.session_state.last_ai_answer:
        st.markdown("#### 최근 답변")
        render_ai_answer(st.session_state.last_ai_answer, st.session_state.last_evidence_mode)
        st.divider()
        render_recent_links()
    if user:
        wk = week_key()
        update_streak_and_badges()
        st.session_state.messages.append({"role": "user", "content": user})
        update_core_context_from_chat(user, wk)
        with st.chat_message("user"):
            st.markdown(user)

        risk_safety_banner_if_needed(user)

        if not api_key:
            with st.chat_message("assistant"):
                st.error("사이드바에 OpenAI API Key를 넣어야 해요.")
            st.stop()

        # Evidence pool
        sources_pool = []
        if evidence_mode:
            serper_key = st.secrets.get("SERPER_API_KEY", "")
            if serper_key:
                try:
                    q = f"{domain} 대학생 {user}"
                    sources_pool = serper_search(q, serper_key, k=5)
                except Exception:
                    sources_pool = curated_sources(domain)
            else:
                sources_pool = curated_sources(domain)

        sources_block = ""
        if evidence_mode and sources_pool:
            sources_block = "SOURCES(공식/기관 링크):\n" + "\n".join(
                [f"- {s['title']} | {s['url']}" for s in sources_pool[:5]]
            )

        survey = st.session_state.survey.get(wk)
        metrics = st.session_state.ab_metrics.get(wk)
        core = get_week_core_context(wk)

        personal_context = []
        if survey or core.get("survey"):
            survey = survey or core.get("survey")
            personal_context.append(
                f"[이번 주 자가설문] 자신감={survey.get('confidence')}/10, 불안={survey.get('anxiety')}/10, "
                f"에너지={survey.get('energy')}/10, 메모={survey.get('notes','')}"
            )
        if metrics or core.get("ab_metrics"):
            metrics = metrics or core.get("ab_metrics")
            a = metrics.get("A", {})
            b = metrics.get("B", {})
            personal_context.append(
                f"[전략 A/B 측정] A(불안={a.get('anxiety')}, 실천={a.get('execution')}%, 성과={a.get('outcome','')}); "
                f"B(불안={b.get('anxiety')}, 실천={b.get('execution')}%, 성과={b.get('outcome','')})"
            )
        if core.get("goal"):
            personal_context.append(f"[핵심 목표] {core.get('goal')}")
        if core.get("current_status"):
            personal_context.append(f"[현재 상태] {core.get('current_status')}")
        if core.get("constraints"):
            personal_context.append(f"[제약/조건] {core.get('constraints')}")

        user_prompt = (
            f"{sources_block}\n\n"
            + ("\n".join(personal_context) + "\n\n" if personal_context else "")
            + f"사용자 메시지:\n{user}"
        )

        # ✅ tone option이 실제 말투에 반영되도록 system prompt에 강제 주입됨(build_system_prompt)
        sys_prompt = build_system_prompt(st.session_state.settings)

        with st.chat_message("assistant"):
            try:
                with st.spinner("Bloom U가 대화를 준비중이에요"):
                    ai_json = call_openai_json(api_key, sys_prompt, user_prompt, st.session_state.messages)
                    ans = normalize_and_validate(ai_json, sources_pool, wk=wk)
            except Exception as e:
                st.error(f"AI 응답 처리 실패(형식 오류/네트워크): {e}")
                st.stop()

            st.session_state.last_ai_answer = ans
            st.session_state.last_evidence_mode = evidence_mode
            st.session_state.last_sources_pool = sources_pool

            # save plan
            st.session_state.active_plan["week"] = wk
            st.session_state.active_plan["planA"] = (ans.get("ab_plans", {}).get("A", {}) or {}).get("steps", []) or []
            st.session_state.active_plan["planB"] = (ans.get("ab_plans", {}).get("B", {}) or {}).get("steps", []) or []

            # ✅✅✅ 핵심 수정: 이번 주 생성 플랜을 덮어쓰기 대신 "누적" 저장
            existing_tasks = st.session_state.plan_by_week.get(wk, []) or []
            new_tasks = [ensure_task_shape(t, wk) for t in ans.get("weekly_active_plan", [])]
            st.session_state.plan_by_week[wk] = merge_weekly_plan(existing_tasks, new_tasks, wk)
            update_core_context_from_plan(wk, st.session_state.plan_by_week[wk])

            render_ai_answer(ans, evidence_mode)

            summary_md = (
                f"**공감 & 요약**\n{ans.get('empathy_summary','')}\n\n"
                f"**사실(정보)**\n" + "\n".join([f"- {f['text']}" for f in ans.get("facts", [])]) + "\n\n"
                f"**전략**\n" + "\n".join([f"- {s}" for s in ans.get("strategies", [])]) + "\n\n"
                f"**불확실성 태그**: {ans.get('uncertainty_tag','')}\n"
            )
            st.session_state.messages.append({"role": "assistant", "content": summary_md})

        unlock_badges()


# =========================
# Tab: Weekly Active Plan (Calendar + Filters + Notion Export)
# =========================
elif tab == "주간 액티브 플랜":
    st.subheader("🗓️ 주간 액티브 플랜 (달력)")

    all_weeks = sorted(set([week_key()] + list(st.session_state.plan_by_week.keys())))
    current_wk = st.session_state.active_plan.get("week", week_key())
    if current_wk not in all_weeks:
        all_weeks.append(current_wk)
        all_weeks = sorted(all_weeks)

    chosen_wk = st.selectbox(
        "주차 선택",
        all_weeks,
        index=all_weeks.index(current_wk) if current_wk in all_weeks else 0
    )
    st.session_state.active_plan["week"] = chosen_wk

    week_start = week_start_from_key(chosen_wk)
    label = week_label_yy_mm_ww_from_week_start(week_start)
    st.write(f"주차: **{label}**  (키: {chosen_wk})")

    st.markdown("### 📤 Notion으로 내보내기")
    st.caption("선택한 주차의 플랜을 사용자의 Notion Database에 ‘페이지 1개’로 저장합니다.")
    exp_col1, exp_col2 = st.columns([0.60, 0.40])
    with exp_col1:
        st.info("Notion DB에 Integration을 Share 했는지 확인해요. Share가 없으면 저장이 실패해요.")
    with exp_col2:
        if st.button("Notion에 저장", use_container_width=True, disabled=not notion_ready()):
            try:
                tok = st.session_state.notion["token"].strip()
                dbid = st.session_state.notion["db_id"].strip()
                title_prop = st.session_state.notion["title_prop"].strip() or "Name"
                tasks = st.session_state.plan_by_week.get(chosen_wk, []) or []
                page_url = notion_create_week_page(tok, dbid, title_prop, label, chosen_wk, tasks)
                st.success("Notion 저장 완료 ✅")
                if page_url:
                    st.markdown(f"- 저장된 페이지: {page_url}")
            except Exception as e:
                st.error(f"Notion 저장 실패: {e}")

    st.divider()

    # Filters
    st.markdown("### 보기 옵션")
    c1, c2, c3 = st.columns([0.38, 0.32, 0.30])
    with c1:
        status_filter = st.multiselect(
            "상태 필터",
            PLAN_STATUS_OPTIONS,
            default=PLAN_STATUS_OPTIONS,
            help="예: ‘체크’만 모아보기"
        )
    with c2:
        show_only_today = st.toggle("오늘 요일만 보기", value=False)
    with c3:
        show_sort = st.toggle("상태별 자동 정렬(진행중→미루기→체크)", value=True)

    st.divider()

    tasks = st.session_state.plan_by_week.get(chosen_wk, []) or []
    tasks = [ensure_task_shape(t, chosen_wk) for t in tasks if (t.get("task") or "").strip()]
    st.session_state.plan_by_week[chosen_wk] = tasks

    st.markdown("### 달력 보기 (요일별)")
    st.caption("체크박스 = ‘체크’ 토글 / 상태 선택 = 체크·진행중·미루기 / ‘미루기’ 선택 시 자동으로 다음 요일(또는 다음 주)로 이동")

    cols = st.columns(7)

    def get_day_items(day_label: str) -> List[Dict[str, Any]]:
        items = [t for t in st.session_state.plan_by_week.get(chosen_wk, []) if t.get("day") == day_label]
        items = [t for t in items if t.get("status") in status_filter]
        if show_sort:
            items = sort_tasks_for_day(items)
        return items

    days_to_render = DAYS
    if show_only_today:
        days_to_render = [IDX_TO_DAY.get(today().weekday(), "월")]

    for i, d in enumerate(DAYS):
        with cols[i]:
            date_i = week_start + dt.timedelta(days=i)
            date_label = date_i.strftime("%m/%d")
            is_today_col = (date_i == today())

            if is_today_col:
                st.markdown(f"#### {d} · {date_label} ⭐")
            else:
                st.markdown(f"#### {d} · {date_label}")

            if show_only_today and d not in days_to_render:
                st.caption(" ")
                continue

            day_items = get_day_items(d)
            if not day_items:
                st.caption("—")
                continue

            for j, item in enumerate(day_items):
                uid = task_uid(item["task"], item.get("day", ""), item.get("week", chosen_wk))
                base_key = f"cal_{uid}_{j}"

                checked_now = st.checkbox(
                    label="",
                    value=(item["status"] == "체크"),
                    key=f"{base_key}_chk",
                    help="체크(완료) 토글"
                )

                cur_status = item["status"] if item["status"] in PLAN_STATUS_OPTIONS else "진행중"
                selected_status = st.selectbox(
                    "상태",
                    PLAN_STATUS_OPTIONS,
                    index=PLAN_STATUS_OPTIONS.index(cur_status),
                    key=f"{base_key}_status",
                    label_visibility="collapsed"
                )

                prev_status = item["status"]
                if checked_now:
                    item["status"] = "체크"
                else:
                    if selected_status == "체크":
                        item["status"] = "진행중"
                    else:
                        item["status"] = selected_status

                # Auto-reschedule when switched to '미루기'
                if item["status"] == "미루기" and prev_status != "미루기":
                    cur_list = st.session_state.plan_by_week.get(chosen_wk, []) or []

                    removed = False
                    for idx in range(len(cur_list) - 1, -1, -1):
                        t = cur_list[idx]
                        if t.get("task") == item.get("task") and t.get("day") == item.get("day") and t.get("created_at") == item.get("created_at"):
                            cur_list.pop(idx)
                            removed = True
                            break
                    if not removed:
                        for idx in range(len(cur_list) - 1, -1, -1):
                            t = cur_list[idx]
                            if t.get("task") == item.get("task") and t.get("day") == item.get("day"):
                                cur_list.pop(idx)
                                break

                    st.session_state.plan_by_week[chosen_wk] = cur_list

                    moved = dict(item)
                    moved = move_task_to_next_slot(moved)

                    target_wk = moved.get("week", chosen_wk)
                    st.session_state.plan_by_week.setdefault(target_wk, [])
                    st.session_state.plan_by_week[target_wk].append(moved)

                    st.rerun()

                badge = "✅" if item["status"] == "체크" else ("⏳" if item["status"] == "진행중" else "🕒")
                st.write(f"{badge} {item['task']}")

    unlock_badges()

    st.divider()
    st.markdown("### 전략 A / B(코칭에서 생성됨)")
    c1, c2 = st.columns(2)
    with c1:
        st.write("**전략 A**")
        for x in st.session_state.active_plan.get("planA", [])[:10]:
            st.write(f"- {x}")
    with c2:
        st.write("**전략 B**")
        for x in st.session_state.active_plan.get("planB", [])[:10]:
            st.write(f"- {x}")

    st.divider()
    st.markdown("### 액션 직접 추가")
    colA, colB = st.columns([0.30, 0.70])
    with colA:
        new_day = st.selectbox("요일", [""] + DAYS, index=0)
    with colB:
        new_task = st.text_input("새 액션", placeholder="예: 25분 집중해서 과제 1페이지 쓰기")
    new_status = st.selectbox("초기 상태", PLAN_STATUS_OPTIONS, index=PLAN_STATUS_OPTIONS.index("진행중"))

    if st.button("추가", use_container_width=True):
        if new_task.strip():
            t = {
                "week": chosen_wk,
                "day": normalize_day_label(new_day),
                "task": new_task.strip(),
                "status": new_status,
                "created_at": dt.datetime.now().isoformat(),
            }
            st.session_state.plan_by_week.setdefault(chosen_wk, [])
            st.session_state.plan_by_week[chosen_wk].append(t)
            st.success("추가했어요!")
            unlock_badges()
            st.rerun()


# =========================
# Tab: A/B Metrics (✅ 저장 버튼 + success 메시지)
# =========================
elif tab == "전략 A/B 측정":
    st.subheader("🧪 전략A/B 플랜 측정 (다음 코칭에 반영)")
    wk = st.session_state.active_plan.get("week", week_key())
    week_start = week_start_from_key(wk)
    st.write(f"주차: **{week_label_yy_mm_ww_from_week_start(week_start)}**  (키: {wk})")

    if wk not in st.session_state.ab_metrics:
        st.session_state.ab_metrics[wk] = {
            "A": {"anxiety": 5, "execution": 50, "outcome": "", "notes": ""},
            "B": {"anxiety": 5, "execution": 50, "outcome": "", "notes": ""},
        }

    # 입력 UI
    for plan_id in ["A", "B"]:
        with st.expander(f"플랜 {plan_id} 기록", expanded=(plan_id == "A")):
            anxiety = st.slider(
                "불안도(0~10)", 0, 10, st.session_state.ab_metrics[wk][plan_id]["anxiety"],
                key=f"ab_anx_{wk}_{plan_id}"
            )
            execution = st.slider(
                "실천도(%)", 0, 100, st.session_state.ab_metrics[wk][plan_id]["execution"],
                key=f"ab_exec_{wk}_{plan_id}"
            )
            outcome = st.text_input(
                "결과물/성과", value=st.session_state.ab_metrics[wk][plan_id]["outcome"],
                key=f"ab_out_{wk}_{plan_id}"
            )
            notes = st.text_area(
                "메모", value=st.session_state.ab_metrics[wk][plan_id]["notes"],
                key=f"ab_note_{wk}_{plan_id}"
            )

    # ✅ “저장” 버튼을 눌러야 저장 + 메시지 뜨게 수정
    if st.button("저장", use_container_width=True):
        st.session_state.ab_metrics[wk]["A"] = {
            "anxiety": st.session_state.get(f"ab_anx_{wk}_A"),
            "execution": st.session_state.get(f"ab_exec_{wk}_A"),
            "outcome": st.session_state.get(f"ab_out_{wk}_A", ""),
            "notes": st.session_state.get(f"ab_note_{wk}_A", ""),
        }
        st.session_state.ab_metrics[wk]["B"] = {
            "anxiety": st.session_state.get(f"ab_anx_{wk}_B"),
            "execution": st.session_state.get(f"ab_exec_{wk}_B"),
            "outcome": st.session_state.get(f"ab_out_{wk}_B", ""),
            "notes": st.session_state.get(f"ab_note_{wk}_B", ""),
        }
        update_core_context_from_ab_metrics(wk, st.session_state.ab_metrics[wk])
        st.success("저장됨! 다음에 ‘채팅’에서는 답변을 더 개인맞춤형으로 해드릴게요.")


# =========================
# Tab: Badges
# =========================
elif tab == "뱃지":
    st.subheader("🏅 뱃지 시스템")
    unlock_badges()

    col1, col2 = st.columns(2)
    for idx, (bid, name, desc) in enumerate(BADGES):
        owned = bid in st.session_state.badges_unlocked
        with (col1 if idx % 2 == 0 else col2):
            st.markdown(f"### {'✅' if owned else '⬜'} {name}")
            st.caption(desc)

    st.divider()
    st.write(f"연속 사용일: **{st.session_state.usage.get('streak', 0)}일**")


# =========================
# Tab: Weekly Survey
# =========================
elif tab == "주간 자가설문":
    st.subheader("📝 주간 자가설문(자신감 지수)")
    wk = week_key()
    week_start = week_start_from_key(wk)
    st.write(f"이번 주: **{week_label_yy_mm_ww_from_week_start(week_start)}**  (키: {wk})")

    cur = st.session_state.survey.get(wk, {"confidence": 5, "anxiety": 5, "energy": 5, "notes": ""})

    confidence = st.slider("자신감 지수(0~10)", 0, 10, int(cur.get("confidence", 5)))
    anxiety = st.slider("불안도(0~10)", 0, 10, int(cur.get("anxiety", 5)))
    energy = st.slider("에너지/컨디션(0~10)", 0, 10, int(cur.get("energy", 5)))
    notes = st.text_area("한 줄 기록(선택)", value=cur.get("notes", ""), placeholder="예: 이번 주는 불안했지만 작은 행동 2개는 해냈다.")

    if st.button("저장", use_container_width=True):
        st.session_state.survey[wk] = {
            "confidence": confidence,
            "anxiety": anxiety,
            "energy": energy,
            "notes": notes.strip(),
            "saved_at": dt.datetime.now().isoformat(),
        }
        update_core_context_from_survey(wk, st.session_state.survey[wk])
        unlock_badges()
        st.success("저장 완료! 주간 리포트/대시보드에 반영돼요.")


# =========================
# Tab: Weekly Report / Dashboard
# =========================
elif tab == "주간 리포트/성장 대시보드":
    st.subheader("📊 주간 레포트 & 성장 시각화 대시보드")

    weeks = sorted(set(list(st.session_state.survey.keys()) + list(st.session_state.ab_metrics.keys()) + list(st.session_state.plan_by_week.keys())))
    if not weeks:
        st.info("아직 데이터가 없어요. 주간 설문을 저장하거나 전략 A/B 맞춤 측정을 해보세요.")
        st.stop()

    rows = []
    for wk in weeks:
        core = get_week_core_context(wk)
        s = st.session_state.survey.get(wk, {}) or core.get("survey", {})
        m = st.session_state.ab_metrics.get(wk, {}) or core.get("ab_metrics", {})
        tasks = st.session_state.plan_by_week.get(wk, []) or []

        completion = None
        if tasks:
            completion = round(100 * sum(1 for t in tasks if t.get("status") == "체크") / len(tasks), 1)
        update_core_context_from_plan(wk, tasks)

        rows.append({
            "week": wk,
            "confidence": s.get("confidence"),
            "anxiety": s.get("anxiety"),
            "energy": s.get("energy"),
            "plan_completion_%": completion,
            "A_anxiety": (m.get("A") or {}).get("anxiety"),
            "A_execution_%": (m.get("A") or {}).get("execution"),
            "B_anxiety": (m.get("B") or {}).get("anxiety"),
            "B_execution_%": (m.get("B") or {}).get("execution"),
            "notes": s.get("notes", ""),
        })

    df = pd.DataFrame(rows).sort_values("week")
    st.dataframe(df, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 자신감/불안/에너지 추이")
        chart_df = df.set_index("week")[["confidence", "anxiety", "energy"]]
        st.line_chart(chart_df)
    with c2:
        st.markdown("### A/B 실천도 비교")
        chart_ab = df.set_index("week")[["A_execution_%", "B_execution_%"]]
        st.line_chart(chart_ab)

    st.divider()
    st.markdown("### 이번 주 요약")
    latest = df.iloc[-1].to_dict()
    bullets = []
    if latest.get("confidence") is not None:
        bullets.append(f"- 자신감: **{latest['confidence']} / 10**")
    if latest.get("anxiety") is not None:
        bullets.append(f"- 불안: **{latest['anxiety']} / 10**")
    if latest.get("energy") is not None:
        bullets.append(f"- 에너지: **{latest['energy']} / 10**")
    if latest.get("plan_completion_%") is not None:
        bullets.append(f"- 목표 달성률(플랜): **{latest['plan_completion_%']}%**")
    st.write("\n".join(bullets) if bullets else "이번 주 데이터가 아직 충분하지 않아요.")

    st.caption("팁: A/B 측정값과 주간 설문을 꾸준히 쌓으면 ‘나에게 맞는 전략’이 더 정확해져요.")

# =========================
# Tab: Daily Pattern Tracker (NEW)
# =========================
elif tab == "데일리 패턴 체크":

    # ✅ 안전 초기화
    if "daily_patterns" not in st.session_state:
        st.session_state.daily_patterns = {}

    st.subheader("📊 데일리 패턴 체크")

    today_str = today().isoformat()

    st.caption("오늘 하루의 패턴을 기록해서 나만의 루틴을 만들어보세요.")

    # 기본값
    cur = st.session_state.daily_patterns.get(
        today_str,
        {
            "water": 3,
            "exercise": 3,
            "sleep": 3,
            "condition": 3,
            "custom": 3,
            "memo": ""
        }
    )

    st.markdown("### ✅ 오늘 체크")

    water = st.slider("💧 수분 섭취", 1, 5, cur["water"])
    exercise = st.slider("🏃 운동량", 1, 5, cur["exercise"])
    sleep = st.slider("😴 수면 만족도", 1, 5, cur["sleep"])
    condition = st.slider("🙂 컨디션", 1, 5, cur["condition"])
    custom = st.slider("⭐ 개인 목표", 1, 5, cur["custom"])

    memo = st.text_area("📝 메모", value=cur["memo"])

    if st.button("💾 오늘 기록 저장", use_container_width=True):

        st.session_state.daily_patterns[today_str] = {
            "water": water,
            "exercise": exercise,
            "sleep": sleep,
            "condition": condition,
            "custom": custom,
            "memo": memo,
            "saved_at": dt.datetime.now().isoformat()
        }

        st.success("오늘 패턴이 저장됐어요! ✅")

    st.divider()

    # =====================
    # 📈 통계 보기
    # =====================
    st.markdown("### 📈 누적 통계")

    if not st.session_state.daily_patterns:
        st.info("아직 저장된 기록이 없어요.")
    else:
        df = pd.DataFrame.from_dict(
            st.session_state.daily_patterns,
            orient="index"
        )

        df.index = pd.to_datetime(df.index)

        # 월간 평균
        monthly = df.resample("M").mean(numeric_only=True)

        # 연간 평균
        yearly = df.resample("Y").mean(numeric_only=True)

        st.markdown("#### 📅 월간 평균")
        st.dataframe(monthly.round(2), use_container_width=True)

        st.markdown("#### 📆 연간 평균")
        st.dataframe(yearly.round(2), use_container_width=True)

        st.markdown("#### 📊 추이 그래프")
        st.line_chart(
            df[["water", "exercise", "sleep", "condition", "custom"]]
        )
