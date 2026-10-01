"""프로그램 점수화. docs/strategy.md 3절과 1:1로 대응.

2단계 깔때기로 API 호출을 아낀다:
  1단계(cheap): 프로그램 목록 응답 필드만으로 필터링 + 1차 점수 (추가 API 호출 없음)
  2단계(refine): 살아남은 후보만 structured_scopes/hacktivity를 추가 조회해 최종 순위
"""
import time

# 정책에 이 문구가 있으면 자동화 스캔 금지 → 무조건 제외 (협상 대상 아님)
AUTOMATION_BANLIST = [
    "no automated scan",
    "no automated tool",
    "not allowed to use automated",
    "automated scanning is not allowed",
    "automated scanners are not allowed",
    "manual testing only",
    "prohibit the use of automat",
    "scanners are prohibited",
    "no vulnerability scanners",
]

# 자동화 recon이 통하는 asset 종류만 넓은 scope로 취급
WEB_ASSET_TYPES = {"URL", "WILDCARD", "API", "CIDR"}

STAGE1_KEEP = 20  # 2단계로 넘길 후보 수 (API 호출 비용 상한)

# scope 넓은 성숙한 프로그램이 "오래됐어도 scope 보너스로 이김" 문제 대응:
# 2년 넘었는데 공개 리포트도 적지 않게 쌓였으면(이미 많이 훑였다는 뜻) 통째로 제외한다.
AGE_HARD_LIMIT_DAYS = 730
LOW_COMPETITION_THRESHOLD = 10

COMPETITION_WEIGHT = 1.0  # 기존 0.5 → scope 보너스(최대 1.5)에 안 밀리게 올림


def _policy_bans_automation(policy: str | None) -> bool:
    if not policy:
        return False
    text = policy.lower()
    return any(term in text for term in AUTOMATION_BANLIST)


def _age_days(started_accepting_at: str | None) -> float | None:
    if not started_accepting_at:
        return None
    try:
        started = time.mktime(time.strptime(started_accepting_at[:19], "%Y-%m-%dT%H:%M:%S"))
    except ValueError:
        return None
    age_days = (time.time() - started) / 86400
    return age_days if age_days >= 0 else None


def _age_score(started_accepting_at: str | None) -> float:
    age_days = _age_days(started_accepting_at)
    if age_days is None:
        return 0.5  # 정보 없으면 중립
    # 최근일수록 높은 점수, 180일 지나면 0에 수렴
    return max(0.0, 1.0 - age_days / 180)


def stage1_filter(programs: list[dict], seen_handles: set[str]) -> list[dict]:
    """API 추가 호출 없이 걸러낸다. 살아남은 것에 cheap_score를 붙여 정렬."""
    kept = []
    for p in programs:
        if not p.get("offers_bounties"):
            continue
        if p.get("submission_state") != "open":
            continue
        if p.get("state") not in (None, "public_mode"):
            continue  # 초대제 등 에이전트가 스스로 못 들어가는 프로그램
        if _policy_bans_automation(p.get("policy")):
            continue
        if p["handle"] in seen_handles:
            continue  # 이미 이전에 추천/승인/스킵한 프로그램
        score = _age_score(p.get("started_accepting_at"))
        if p.get("fast_payments"):
            score += 0.2
        p["_cheap_score"] = score
        kept.append(p)
    kept.sort(key=lambda p: p["_cheap_score"], reverse=True)
    return kept[:STAGE1_KEEP]


def refine_score(program: dict, scopes: list[dict], disclosed_count: int) -> float:
    web_scopes = [s for s in scopes if s.get("asset_type") in WEB_ASSET_TYPES and s.get("eligible_for_submission")]
    if not web_scopes:
        return -1.0  # 자동화가 못 건드리는 scope뿐이면 탈락시킨다

    age_days = _age_days(program.get("started_accepting_at"))
    if age_days is not None and age_days > AGE_HARD_LIMIT_DAYS and disclosed_count > LOW_COMPETITION_THRESHOLD:
        return -1.0  # 오래됐고 이미 많이 훑였으면 scope가 넓어도 통째로 제외

    web_ratio = len(web_scopes) / max(len(scopes), 1)
    breadth = min(len(web_scopes), 20) / 20  # 20개 넘어가면 체감
    competition_penalty = min(disclosed_count, 50) / 50  # 공개 리포트 많을수록 감점

    score = program["_cheap_score"]
    score += web_ratio * 1.0
    score += breadth * 0.5
    score -= competition_penalty * COMPETITION_WEIGHT
    return score


def format_candidate(program: dict, scopes: list[dict], score: float) -> dict:
    web_scopes = [s for s in scopes if s.get("asset_type") in WEB_ASSET_TYPES and s.get("eligible_for_submission")]
    return {
        "handle": program["handle"],
        "name": program.get("name") or program["handle"],
        "url": f"https://hackerone.com/{program['handle']}",
        "policy": program.get("policy") or "",
        "started_accepting_at": program.get("started_accepting_at"),
        "offers_bounties": bool(program.get("offers_bounties")),
        "fast_payments": bool(program.get("fast_payments")),
        "currency": program.get("currency"),
        "gold_standard_safe_harbor": bool(program.get("gold_standard_safe_harbor")),
        "score": round(score, 3),
        "scopes": scopes,
        "web_asset_count": len(web_scopes),
    }
