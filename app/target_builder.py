"""승인된 프로그램의 HackerOne API 원본 정보를 그대로 JSON으로 묶는다. AI 호출 없음.

여기서 만드는 파일은 hermes의 target.json 그 자체가 아니라, 사람(또는 다른 프로세스)이
target.json을 작성할 때 참고할 원본 자료다 — 그래서 스키마를 어설프게 맞추려 하지 않고,
API에서 가져온 내용을 가공 없이 담는다. 본문(정책)은 길어도 자르지 않는다.
"""
import re

from .scoring import WEB_ASSET_TYPES

# ponytail: 우리가 직접 자르는 로직이 없어서 지금은 항상 False.
# 나중에 어딘가(업로드 한도 등)에서 실제로 잘라야 하는 상황이 생기면
# 그 지점에서 이 값을 True로 세팅하는 로직을 넣을 것.
POLICY_TRUNCATED = False


def _domains_by_eligibility(scopes: list[dict], eligible: bool) -> list[str]:
    return [
        s["asset_identifier"]
        for s in scopes
        if s.get("asset_type") in WEB_ASSET_TYPES and s.get("eligible_for_submission") is eligible
    ]


def primary_domain(candidate: dict) -> str:
    """파일명(<도메인>.json)에 쓸 대표 도메인. 못 찾으면 handle로 fallback."""
    in_scope = _domains_by_eligibility(candidate["scopes"], eligible=True)
    if not in_scope:
        return candidate["handle"]
    raw = in_scope[0]
    domain = re.sub(r"^https?://", "", raw)
    domain = domain.lstrip("*.")
    domain = domain.split("/")[0]
    return domain or candidate["handle"]


def build_target_json(candidate: dict, scope_exclusions: list[dict]) -> dict:
    return {
        "handle": candidate["handle"],
        "name": candidate["name"],
        "hackerone_url": candidate["url"],
        "bounty_info": {
            "offers_bounties": candidate.get("offers_bounties"),
            "fast_payments": candidate.get("fast_payments"),
            "currency": candidate.get("currency"),
            "gold_standard_safe_harbor": candidate.get("gold_standard_safe_harbor"),
        },
        "policy": candidate["policy"],
        "policy_truncated": POLICY_TRUNCATED,
        "scope": {
            "structured_scopes": candidate["scopes"],
            "scope_exclusions": scope_exclusions,
        },
    }
