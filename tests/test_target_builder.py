"""target_builder 자가 점검. `python tests/test_target_builder.py`로 실행."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import target_builder

CANDIDATE = {
    "handle": "acme",
    "name": "Acme",
    "url": "https://hackerone.com/acme",
    "policy": "policy text, 길어도 안 자름" * 1000,
    "offers_bounties": True,
    "fast_payments": True,
    "currency": "usd",
    "gold_standard_safe_harbor": False,
    "score": 1.23,
    "scopes": [
        {"asset_identifier": "*.acme.com", "asset_type": "WILDCARD", "eligible_for_submission": True},
        {"asset_identifier": "https://api.acme.com", "asset_type": "URL", "eligible_for_submission": True},
        {"asset_identifier": "blog.acme.com", "asset_type": "URL", "eligible_for_submission": False},
        {"asset_identifier": "com.acme.app", "asset_type": "MOBILE_APPLICATION_ANDROID", "eligible_for_submission": True},
    ],
}


def test_primary_domain_strips_wildcard_and_scheme():
    assert target_builder.primary_domain(CANDIDATE) == "acme.com"


def test_primary_domain_falls_back_to_handle():
    no_scope = {**CANDIDATE, "scopes": []}
    assert target_builder.primary_domain(no_scope) == "acme"


def test_build_target_json_has_no_ai_fields_and_full_policy():
    result = target_builder.build_target_json(CANDIDATE, scope_exclusions=[{"category": "Social Engineering"}])
    assert result["handle"] == "acme"
    assert result["hackerone_url"] == "https://hackerone.com/acme"
    assert result["policy"] == CANDIDATE["policy"], "본문은 길어도 그대로 담겨야 한다(자르지 않음)"
    assert result["policy_truncated"] is False
    assert result["bounty_info"] == {
        "offers_bounties": True,
        "fast_payments": True,
        "currency": "usd",
        "gold_standard_safe_harbor": False,
    }
    assert result["scope"]["structured_scopes"] == CANDIDATE["scopes"]
    assert result["scope"]["scope_exclusions"] == [{"category": "Social Engineering"}]
    assert "project_id" not in result and "automation_policy" not in result, "AI 전용 필드가 남아있으면 안 된다"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok: {t.__name__}")
    print(f"{len(tests)} passed")
