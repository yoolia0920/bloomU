import json
import math
import datetime as dt
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st
from openai import OpenAI


# =========================
# App Identity (Req 1~3)
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
    ("weekly_checkin", "체크인 📈", "주간 자신감 설문을 완료했어요."),
    ("streak_3", "3일 연속 🔥", "3일 연속으로 Bloom U를 사용했어요."),
]

# Evidence mode: optional real search (Serper) + domain-whitelist
ALLOWED_SOURCE_DOMAINS = [
    ".gov", ".edu", "who.int", "oecd.org", "nih.gov", "cdc.gov", "apa.org",
    "indeed.com", "glassdoor.com", "ncs.gov", "moel.go.kr", "korea.kr"
]


# =========================
# Utilities
# =========================
def today() -> dt.date:
    return dt.date.today()

def week_key(d: Optional[dt.date] = None) -> str:
    d = d or today()
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"

def is_allowed_url(url: str) -> bool:
    u = (url or "").lower()
    return u.startswith("http") and any(dom in u for dom in ALLOWED_SOURCE_DOMAINS)

def detect_high_risk(text: str) -> bool:
    # Heuristic; production would use better classifier.
    k = [
        "자해", "죽고", "극단", "우울", "공황", "자살", "리스트컷",
        "진단", "치료", "처방", "약", "병원",
        "대출", "빚", "투자", "코인", "주식", "세금",
        "고소", "합의", "소송", "불법", "사기", "폭력"
    ]
    t = (text or "").lower()
    return any(x in t for x in k)

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
        st.session_state.messages = []  # list of {"role": "user"/"assistant", "content": "..."}
    if "active_plan" not in st.session_state:
        st.session_state.active_plan = {
            "week": week_key(),
            "tasks": [],  # [{"task": str, "day": str, "done": bool}]
            "planA": [],
            "planB": [],
        }
    if "ab_metrics" not in st.session_state:
        # per week: {"A": {"anxiety": int, "execution": int, "outcome": str, "notes": str}, "B": ...}
        st.session_state.ab_metrics = {}
    if "survey" not in st.session_state:
        # per week: {"confidence": int, "anxiety": int, "energy": int, "notes": str}
        st.session_state.survey = {}
    if "badges_unlocked" not in st.session_state:
        st.session_state.badges_unlocked = set()
    if "usage" not in st.session_state:
        st.session_state.usage = {"last_active": None, "streak": 0}

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

def unlock_badges():
    if any(m["role"] == "user" for m in st.session_state.messages):
        st.session_state.badges_unlocked.add("first_chat")

    if st.session_state.active_plan.get("tasks"):
        st.session_state.badges_unlocked.add("first_plan")

    done = sum(1 for t in st.session_state.active_plan.get("tasks", []) if t.get("done"))
    if done >= 3:
        st.session_state.badges_unlocked.add("plan_3_done")

    if week_key() in st.session_state.survey:
        st.session_state.badges_unlocked.add("weekly_checkin")


# =========================
# Evidence Search (Req 10)
# =========================
def serper_search(query: str, api_key: str, k: int = 5) -> List[Dict[str, str]]:
    """
    Uses Serper (Google Search API). Optional. If not set, fall back to curated sources.
    """
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
    """
    No-key fallback: suggests reliable institutions per domain (not query-specific).
    This keeps deployment stable.
    """
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
# Prompting & Response Parsing (Req 11~13)
# =========================
def build_system_prompt(settings: Dict[str, Any]) -> str:
    nickname = settings["nickname"]
    tone = settings["tone"]
    level = settings["level"]
    domain = settings["domain"]
    evidence_mode = settings["evidence_mode"]

    return f"""
당신은 20대 대학생들이 맞이할 모든 첫 시작을 도울 러닝메이트 코칭 매니저입니다.
사용자의 닉네임은 '{nickname}'이며 반드시 이 이름으로 부르세요.

[말투/레벨/분야]
- 말투: {tone}
- 레벨: {level}
- 분야: {domain}

[핵심 원칙]
- 공감(친구 같은 다정함) + 현실감각 있는 조언(인생 선배 관점)을 항상 함께 제공합니다.
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
  "weekly_active_plan": [{{"day":"월|화|수|목|금|토|일|", "task":"...", "done": false}}],
  "risk_warning": {{
     "is_high_risk": true/false,
     "message": "경고/권고",
     "safe_actions": ["...", "..."]
  }}
}}
"""

def call_openai_json(api_key: str, sys_prompt: str, user_prompt: str, chat: List[Dict[str, str]]) -> Dict[str, Any]:
    client = OpenAI(api_key=api_key)
    # Keep context short-ish to reduce cost/format failures
    context = chat[-12:] if len(chat) > 12 else chat

    inp = [{"role": "system", "content": sys_prompt}]
    for m in context:
        inp.append({"role": m["role"], "content": m["content"]})
    inp.append({"role": "user", "content": user_prompt})

    resp = client.responses.create(
        model=MODEL,
        input=inp,
        # hint: let model focus on JSON
        temperature=0.6,
    )
    txt = resp.output_text.strip()

    # Some models may wrap JSON in code fences; strip them
    if txt.startswith("```"):
        txt = txt.strip("`")
        # attempt to extract json block
        start = txt.find("{")
        end = txt.rfind("}")
        txt = txt[start:end+1] if start != -1 and end != -1 else txt

    return json.loads(txt)

def normalize_and_validate(ai: Dict[str, Any], sources_pool: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Ensure:
    - facts.sources are subset of sources_pool (for evidence mode)
    - URLs are whitelisted
    - required keys exist
    """
    out = {
        "empathy_summary": ai.get("empathy_summary", ""),
        "facts": [],
        "strategies": ai.get("strategies", []),
        "uncertainty_tag": ai.get("uncertainty_tag", "추정(개인화 필요)"),
        "ab_plans": ai.get("ab_plans", {
            "A": {"title": "플랜 A", "steps": [], "metrics": ["불안도0~10","실천도%","결과물/성과"]},
            "B": {"title": "플랜 B", "steps": [], "metrics": ["불안도0~10","실천도%","결과물/성과"]},
        }),
        "weekly_active_plan": ai.get("weekly_active_plan", []),
        "risk_warning": ai.get("risk_warning", {"is_high_risk": False, "message": "", "safe_actions": []}),
    }

    # Build allowed set from pool
    pool_urls = {s["url"] for s in (sources_pool or []) if is_allowed_url(s.get("url", ""))}

    facts = ai.get("facts", []) or []
    for f in facts:
        uncertainty = f.get("uncertainty", "추정")
        # map shorthand to full labels if needed
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

    # Weekly plan normalization
    plan = []
    for item in out["weekly_active_plan"][:12]:
        plan.append({
            "day": (item.get("day") or "").strip(),
            "task": (item.get("task") or "").strip(),
            "done": bool(item.get("done", False)),
        })
    out["weekly_active_plan"] = [p for p in plan if p["task"]]
    return out


# =========================
# Rendering helpers
# =========================
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

    st.markdown("### 6) 이번 주 액티브 플랜(체크리스트)")
    plan = ans.get("weekly_active_plan", [])
    if not plan:
        st.caption("아직 자동 플랜을 만들기 어려웠어요. 목표/기한/제약을 조금 더 알려주면 좋아요.")
    else:
        for p in plan:
            st.write(f"- {p['day']} {p['task']}")

    rw = ans.get("risk_warning", {}) or {}
    if rw.get("is_high_risk"):
        st.markdown("### 7) 리스크 경고")
        st.warning(rw.get("message", "고위험 주제일 수 있어요. 전문가 상담을 권장합니다."))
        safe = rw.get("safe_actions", []) or []
        if safe:
            st.write("대체 안전 행동:")
            for x in safe[:6]:
                st.write(f"- {x}")

def risk_safety_banner_if_needed(user_text: str):
    # If user text suggests high risk, show safety note regardless of model output.
    if detect_high_risk(user_text):
        st.warning(
            "⚠️ 이 대화는 법/의료/정신건강/재정 등 고위험 주제를 포함할 수 있어요.\n"
            "가능하면 전문가(상담센터/의료진/법률/금융 전문가)와 함께 확인해 주세요.\n\n"
            "만약 지금 매우 위험하거나 자해 충동이 있다면, 즉시 주변 도움을 요청하세요.\n"
            "- (한국) 자살예방 상담전화 1393\n- 정신건강위기 상담 1577-0199\n- 긴급상황 112/119"
        )


# =========================
# App UI
# =========================
st.set_page_config(page_title=f"{APP_NAME} - 상담/코칭 AI", page_icon="🌸", layout="wide")
ensure_state()

# Sidebar (Req 4~5 + API key input)
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
nickname_default = "익명" if anonymous_mode else st.session_state.settings["nickname"] or "율"
nickname = st.sidebar.text_input("닉네임(챗봇이 이 이름으로 불러요)", value=nickname_default).strip() or "익명"

st.session_state.settings.update({
    "tone": tone,
    "level": level,
    "domain": domain,
    "evidence_mode": evidence_mode,
    "anonymous_mode": anonymous_mode,
    "nickname": nickname,
})

tab = st.sidebar.radio("탭", ["채팅", "액티브 플랜", "A/B 측정", "뱃지", "주간 설문", "주간 리포트/대시보드"], index=0)

st.sidebar.divider()
st.sidebar.caption(f"타겟 사용자: {TARGET}")
st.sidebar.caption("팁: ‘목표/기한/제약/현재 상태’를 구체적으로 적을수록 플랜이 좋아져요.")


# Header
st.title(f"🌸 {APP_NAME}")
st.markdown(f"**{SLOGAN}**")
st.caption(ONE_LINER)


# =========================
# Tab: Chat (Req 6, 10~13)
# =========================
if tab == "채팅":
    st.subheader("💬 상담/코칭 챗")

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    user = st.chat_input("지금 어떤 ‘처음’을 시작하려고 해? (목표/기한/현재수준/제약을 같이 적어줘)")
    if user:
        update_streak_and_badges()
        st.session_state.messages.append({"role": "user", "content": user})
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

        # Build user prompt with SOURCES
        sources_block = ""
        if evidence_mode and sources_pool:
            sources_block = "SOURCES(공식/기관 링크):\n" + "\n".join(
                [f"- {s['title']} | {s['url']}" for s in sources_pool[:5]]
            )

        # Add personalization context: last survey + AB metrics
        wk = week_key()
        survey = st.session_state.survey.get(wk)
        metrics = st.session_state.ab_metrics.get(wk)

        personal_context = []
        if survey:
            personal_context.append(
                f"[이번 주 자가설문] 자신감={survey.get('confidence')}/10, 불안={survey.get('anxiety')}/10, 에너지={survey.get('energy')}/10, 메모={survey.get('notes','')}"
            )
        if metrics:
            a = metrics.get("A", {})
            b = metrics.get("B", {})
            personal_context.append(
                f"[A/B 측정] A(불안={a.get('anxiety')}, 실천={a.get('execution')}%, 성과={a.get('outcome','')}); "
                f"B(불안={b.get('anxiety')}, 실천={b.get('execution')}%, 성과={b.get('outcome','')})"
            )

        user_prompt = (
            f"{sources_block}\n\n"
            + ("\n".join(personal_context) + "\n\n" if personal_context else "")
            + f"사용자 메시지:\n{user}"
        )

        sys_prompt = build_system_prompt(st.session_state.settings)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            try:
                with st.spinner("Bloom U가 같이 정리하고 있어요…"):
                    ai_json = call_openai_json(api_key, sys_prompt, user_prompt, st.session_state.messages)
                    ans = normalize_and_validate(ai_json, sources_pool)
            except Exception as e:
                st.error(f"AI 응답 처리 실패(형식 오류/네트워크): {e}")
                st.stop()

            # Save plan to state (Req 6, 13)
            st.session_state.active_plan["week"] = wk
            st.session_state.active_plan["tasks"] = ans.get("weekly_active_plan", [])
            st.session_state.active_plan["planA"] = (ans.get("ab_plans", {}).get("A", {}) or {}).get("steps", []) or []
            st.session_state.active_plan["planB"] = (ans.get("ab_plans", {}).get("B", {}) or {}).get("steps", []) or []

            render_ai_answer(ans, evidence_mode)

            # store assistant content as readable markdown (not raw json)
            summary_md = (
                f"**공감 & 요약**\n{ans.get('empathy_summary','')}\n\n"
                f"**사실(정보)**\n" + "\n".join([f"- {f['text']}" for f in ans.get("facts", [])]) + "\n\n"
                f"**전략**\n" + "\n".join([f"- {s}" for s in ans.get("strategies", [])]) + "\n\n"
                f"**불확실성 태그**: {ans.get('uncertainty_tag','')}\n"
            )
            st.session_state.messages.append({"role": "assistant", "content": summary_md})

        unlock_badges()


# =========================
# Tab: Active Plan (Req 6)
# =========================
elif tab == "액티브 플랜":
    st.subheader("🗓️ 주간 액티브 플랜")
    wk = st.session_state.active_plan.get("week", week_key())
    st.write(f"주차: **{wk}**")

    tasks = st.session_state.active_plan.get("tasks", [])
    if not tasks:
        st.info("아직 플랜이 없어요. ‘채팅’에서 코칭을 받은 뒤 자동 생성돼요.")
    else:
        st.markdown("### 체크리스트")
        for i, t in enumerate(tasks):
            cols = st.columns([0.15, 0.85])
            with cols[0]:
                t["done"] = st.checkbox("완료", value=bool(t.get("done")), key=f"task_{wk}_{i}")
            with cols[1]:
                day = (t.get("day") or "").strip()
                label = f"{day+' ' if day else ''}{t.get('task','')}"
                st.write(label)

        st.session_state.active_plan["tasks"] = tasks
        unlock_badges()

        st.divider()
        st.markdown("### 플랜 A / B(코칭에서 생성됨)")
        c1, c2 = st.columns(2)
        with c1:
            st.write("**플랜 A**")
            for x in st.session_state.active_plan.get("planA", [])[:10]:
                st.write(f"- {x}")
        with c2:
            st.write("**플랜 B**")
            for x in st.session_state.active_plan.get("planB", [])[:10]:
                st.write(f"- {x}")

    st.divider()
    st.markdown("### 액션 직접 추가")
    new_task = st.text_input("새 액션", placeholder="예: 25분 집중해서 과제 1페이지 쓰기")
    if st.button("추가", use_container_width=True):
        if new_task.strip():
            st.session_state.active_plan.setdefault("tasks", []).append({"day": "", "task": new_task.strip(), "done": False})
            st.success("추가했어요!")
            unlock_badges()


# =========================
# Tab: A/B Metrics (Req 13)
# =========================
elif tab == "A/B 측정":
    st.subheader("🧪 A/B 플랜 측정 (다음 코칭에 반영)")
    wk = st.session_state.active_plan.get("week", week_key())
    st.write(f"주차: **{wk}**")

    if wk not in st.session_state.ab_metrics:
        st.session_state.ab_metrics[wk] = {
            "A": {"anxiety": 5, "execution": 50, "outcome": "", "notes": ""},
            "B": {"anxiety": 5, "execution": 50, "outcome": "", "notes": ""},
        }

    for plan_id in ["A", "B"]:
        with st.expander(f"플랜 {plan_id} 기록", expanded=(plan_id == "A")):
            anxiety = st.slider("불안도(0~10)", 0, 10, st.session_state.ab_metrics[wk][plan_id]["anxiety"], key=f"ab_anx_{wk}_{plan_id}")
            execution = st.slider("실천도(%)", 0, 100, st.session_state.ab_metrics[wk][plan_id]["execution"], key=f"ab_exec_{wk}_{plan_id}")
            outcome = st.text_input("결과물/성과", value=st.session_state.ab_metrics[wk][plan_id]["outcome"], key=f"ab_out_{wk}_{plan_id}")
            notes = st.text_area("메모", value=st.session_state.ab_metrics[wk][plan_id]["notes"], key=f"ab_note_{wk}_{plan_id}")

            st.session_state.ab_metrics[wk][plan_id] = {
                "anxiety": anxiety,
                "execution": execution,
                "outcome": outcome,
                "notes": notes,
            }

    st.success("저장됨! 다음에 ‘채팅’에서 답변 품질이 더 개인화돼요.")


# =========================
# Tab: Badges (Req 7)
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
# Tab: Weekly Survey (Req 9)
# =========================
elif tab == "주간 설문":
    st.subheader("📝 주간 자가설문(자신감 지수)")
    wk = week_key()
    st.write(f"이번 주: **{wk}**")

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
        unlock_badges()
        st.success("저장 완료! 주간 리포트/대시보드에 반영돼요.")


# =========================
# Tab: Weekly Report / Dashboard (Req 8)
# =========================
elif tab == "주간 리포트/대시보드":
    st.subheader("📊 주간 레포트 & 성장 시각화 대시보드")

    # Combine weeks
    weeks = sorted(set(list(st.session_state.survey.keys()) + list(st.session_state.ab_metrics.keys())))
    if not weeks:
        st.info("아직 데이터가 없어요. 주간 설문을 저장하거나 A/B 측정을 해보세요.")
        st.stop()

    rows = []
    for wk in weeks:
        s = st.session_state.survey.get(wk, {})
        m = st.session_state.ab_metrics.get(wk, {})
        completion = None
        if st.session_state.active_plan.get("week") == wk:
            tasks = st.session_state.active_plan.get("tasks", [])
            if tasks:
                completion = round(100 * sum(1 for t in tasks if t.get("done")) / len(tasks), 1)

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
