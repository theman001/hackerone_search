"""점수화 로직 자가 점검. pytest 없이 `python tests/test_scoring.py`로 바로 실행."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import scoring


def _iso_days_ago(days: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() - days * 86400))


def _program(**overrides):
    base = {
        "handle": "acme",
        "name": "Acme",
        "offers_bounties": True,
        "submission_state": "open",
        "state": "public_mode",
        "policy": "Standard policy, automated recon is fine.",
        "started_accepting_at": None,
        "fast_payments": False,
    }
    base.update(overrides)
    return base


def test_automation_ban_excludes_program():
    banned = _program(policy="No automated scanning tools are allowed.")
    result = scoring.stage1_filter([banned], seen_handles=set())
    assert result == [], "정책이 자동화 스캔을 금지하면 후보에서 빠져야 한다"


def test_invite_only_excluded():
    private = _program(state="soft_launched")
    result = scoring.stage1_filter([private], seen_handles=set())
    assert result == [], "초대제(public_mode 아님) 프로그램은 에이전트가 못 들어가므로 제외돼야 한다"


def test_no_bounty_excluded():
    no_bounty = _program(offers_bounties=False)
    result = scoring.stage1_filter([no_bounty], seen_handles=set())
    assert result == []


def test_seen_handle_excluded():
    p = _program()
    result = scoring.stage1_filter([p], seen_handles={"acme"})
    assert result == [], "이미 추천/승인/스킵한 프로그램은 다시 나오면 안 된다"


def test_ok_program_survives_stage1():
    p = _program()
    result = scoring.stage1_filter([p], seen_handles=set())
    assert len(result) == 1
    assert "_cheap_score" in result[0]


def test_refine_score_rejects_non_web_scope():
    p = _program()
    p["_cheap_score"] = 0.5
    mobile_only = [{"asset_type": "MOBILE_APPLICATION_ANDROID", "eligible_for_submission": True}]
    assert scoring.refine_score(p, mobile_only, disclosed_count=0) < 0, "웹/API asset이 없으면 자동화 부적합으로 탈락해야 한다"


def test_refine_score_rewards_web_scope_and_penalizes_competition():
    p = _program()
    p["_cheap_score"] = 0.5
    web_scopes = [{"asset_type": "URL", "eligible_for_submission": True}] * 5
    low_competition = scoring.refine_score(p, web_scopes, disclosed_count=0)
    high_competition = scoring.refine_score(p, web_scopes, disclosed_count=50)
    assert low_competition > high_competition, "공개 리포트가 많을수록(경쟁 심할수록) 점수가 낮아야 한다"


def test_old_and_heavily_disclosed_excluded_even_with_wide_scope():
    old_popular = _program(started_accepting_at=_iso_days_ago(1000))  # 2년(730일) 넘음
    old_popular["_cheap_score"] = 0.5
    web_scopes = [{"asset_type": "URL", "eligible_for_submission": True}] * 20  # scope 보너스 꽉 채움
    score = scoring.refine_score(old_popular, web_scopes, disclosed_count=50)
    assert score < 0, "2년 넘었고 공개 리포트도 많으면 scope가 넓어도 통째로 제외돼야 한다"


def test_old_but_quiet_program_not_hard_excluded():
    old_quiet = _program(started_accepting_at=_iso_days_ago(1000))
    old_quiet["_cheap_score"] = 0.5
    web_scopes = [{"asset_type": "URL", "eligible_for_submission": True}] * 5
    score = scoring.refine_score(old_quiet, web_scopes, disclosed_count=2)
    assert score >= 0, "오래됐어도 공개 리포트가 적으면(LOW_COMPETITION_THRESHOLD 이하) 하드 제외하면 안 된다"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok: {t.__name__}")
    print(f"{len(tests)} passed")
