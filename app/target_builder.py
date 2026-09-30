"""target.json(hermes 스키마, ./target.json 참고) 조립.

구조적 필드(scope, url, platform 등)는 이미 HackerOne API로 정확히 알고 있으니
코드에서 결정론적으로 채운다. AI는 자유서술인 notes/VPN 판단만 맡는다.

automation_policy는 항상 고정값이다: prohibits_automation은 stage1에서 이미
정책 배제 필터를 통과했으므로 False. prohibits_third_party_ai_sharing도 False —
hermes는 로컬 AI로 구동되므로 "제3자 AI 공유 금지" 정책과 애초에 무관하다.
"""
import re

from .scoring import WEB_ASSET_TYPES


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


def build_target_json(candidate: dict, scope_exclusion_categories: list[str], ai_analysis: dict) -> dict:
    domain = primary_domain(candidate)
    vpn_required = bool(ai_analysis.get("vpn_required"))
    notes_parts = [n.strip() for n in [ai_analysis.get("notes", "")] if n.strip()]
    if scope_exclusion_categories:
        notes_parts.append("제외 카테고리(scope_exclusions): " + ", ".join(scope_exclusion_categories))
    if vpn_required:
        notes_parts.append("VPN 필요 — profile_name은 수동 지정 필요")

    return {
        "project_id": domain,
        "category": "web",
        "mode": "bug_bounty",
        "target": {
            "program_name": candidate["name"],
            "platform": "hackerone",
            "scope": {
                "in_scope_domains": _domains_by_eligibility(candidate["scopes"], eligible=True),
                "out_of_scope_domains": _domains_by_eligibility(candidate["scopes"], eligible=False),
            },
            "rules_url": candidate["url"],
            "reward_table_url": candidate["url"],
            "automation_policy": {
                "prohibits_automation": False,
                "prohibits_third_party_ai_sharing": False,
                "notes": " / ".join(notes_parts),
            },
            "vpn": {"required": vpn_required, "profile_name": None},
        },
        "max_rounds_per_phase": 20,
        "status": "active",
        "_comment": f"hunt-bot 자동 생성 (score={candidate['score']}) · 승인: {candidate['handle']}",
    }
