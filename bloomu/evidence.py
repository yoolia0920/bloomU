from typing import Dict, List

import requests

from .helpers import is_allowed_url


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
