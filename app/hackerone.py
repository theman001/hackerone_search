"""HackerOne 공식 Hacker API 클라이언트.

문서: https://api.hackerone.com/hacker-resources (GET /hackers/programs 등)
Basic Auth(username, api_token), read 요청 한도 600/min.
"""
import logging

import requests

from . import config

BASE = "https://api.hackerone.com/v1"
logger = logging.getLogger(__name__)


class HackerOneClient:
    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.auth = (config.H1_USERNAME, config.H1_API_TOKEN)
        self._session.headers["Accept"] = "application/json"

    def _get(self, path: str, **params) -> dict:
        r = self._session.get(f"{BASE}{path}", params=params, timeout=20)
        r.raise_for_status()
        return r.json()

    def list_programs(self) -> list[dict]:
        """공개 프로그램 전체를 페이지네이션 따라가며 수집. attributes만 뽑아 평평하게 반환."""
        programs = []
        page = 1
        while True:
            body = self._get("/hackers/programs", **{"page[number]": page, "page[size]": 100})
            data = body.get("data", [])
            if not data:
                break
            for item in data:
                attrs = item["attributes"]
                attrs["handle"] = attrs.get("handle") or item.get("id")
                programs.append(attrs)
            logger.info("list_programs: page %d, %d개 누적", page, len(programs))
            if len(data) < 100:
                break
            page += 1
        return programs

    def get_structured_scopes(self, handle: str) -> list[dict]:
        body = self._get(f"/hackers/programs/{handle}/structured_scopes", **{"page[size]": 100})
        return [item["attributes"] for item in body.get("data", [])]

    def get_scope_exclusions(self, handle: str) -> list[dict]:
        body = self._get(f"/hackers/programs/{handle}/scope_exclusions", **{"page[size]": 100})
        return [item["attributes"] for item in body.get("data", [])]

    def count_recent_disclosed_reports(self, handle: str) -> int:
        """공개(disclosed)된 리포트 수만 셀 수 있음 — 전체 제출량의 근사치(경쟁 강도 proxy)."""
        body = self._get("/hackers/hacktivity", **{"queryString": f"team:{handle}", "page[size]": 100})
        return len(body.get("data", []))
