"""target_builder 자가 점검. `python tests/test_target_builder.py`로 실행."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import target_builder

CANDIDATE = {
    "handle": "acme",
    "name": "Acme",
    "url": "https://hackerone.com/acme",
    "policy": "policy text",
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


def test_build_target_json_scope_and_flags():
    result = target_builder.build_target_json(CANDIDATE, ["Social Engineering"], {"vpn_required": True, "notes": "rate limit 있음"})
    assert result["project_id"] == "acme.com"
    assert result["target"]["platform"] == "hackerone"
    assert set(result["target"]["scope"]["in_scope_domains"]) == {"*.acme.com", "https://api.acme.com"}
    assert result["target"]["scope"]["out_of_scope_domains"] == ["blog.acme.com"]
    assert result["target"]["automation_policy"]["prohibits_automation"] is False
    assert result["target"]["vpn"]["required"] is True
    assert "rate limit" in result["target"]["automation_policy"]["notes"]
    assert "Social Engineering" in result["target"]["automation_policy"]["notes"]


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok: {t.__name__}")
    print(f"{len(tests)} passed")
