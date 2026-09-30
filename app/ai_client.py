"""정책 원문에서 사람이 읽어야만 알 수 있는 두 가지만 AI에 묻는다: VPN 필요 여부, 특이사항 요약.
scope/URL 등 구조적 필드는 target_builder.py가 API 데이터로 결정론적으로 채운다.
"""
import json
import logging

from openai import OpenAI

from . import config

logger = logging.getLogger(__name__)

_PROMPT = """아래는 HackerOne 버그바운티 프로그램의 정책 원문이다. 다음 JSON 형식으로만 답하라.
다른 텍스트, 코드블록 없이 JSON 객체 하나만 출력한다.

{{"vpn_required": true 또는 false, "notes": "정책에서 특이사항(rate limit, 테스트 가능 시간대, VPN/접근 절차, 중복 처리 방식 등)을 2~3문장 한국어로 요약. 특이사항 없으면 빈 문자열."}}

# 프로그램: {name}
# 정책 원문
{policy}
"""


def analyze_policy(candidate: dict) -> dict:
    """실패해도 예외를 던지지 않는다 — 이 필드들은 부가 정보라 실패 시 안전한 기본값으로 진행한다."""
    default = {"vpn_required": False, "notes": ""}
    if not candidate.get("policy"):
        return default

    try:
        client = OpenAI(base_url=config.AI_BASE_URL, api_key=config.AI_API_KEY)
        resp = client.chat.completions.create(
            model=config.AI_MODEL,
            messages=[{"role": "user", "content": _PROMPT.format(name=candidate["name"], policy=candidate["policy"])}],
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(raw)
        return {
            "vpn_required": bool(parsed.get("vpn_required", False)),
            "notes": str(parsed.get("notes", "")),
        }
    except Exception:
        logger.warning("정책 AI 분석 실패, 기본값으로 진행", exc_info=True)
        return default
