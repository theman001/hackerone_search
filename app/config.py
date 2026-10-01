"""환경변수 로딩. .env는 docker-compose의 env_file로 주입되므로 여기선 os.environ만 읽는다."""
import os


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"필수 환경변수 누락: {name}")
    return val


# HackerOne Hacker API
H1_USERNAME = _require("H1_USERNAME")
H1_API_TOKEN = _require("H1_API_TOKEN")

# Mattermost
MM_URL = _require("MM_URL")  # 예: mattermost (compose 내부 서비스명), 포트 없이
MM_PORT = int(os.environ.get("MM_PORT", "8065"))
MM_SCHEME = os.environ.get("MM_SCHEME", "http")
MM_BOT_TOKEN = _require("MM_BOT_TOKEN")
MM_CHANNEL_ID = _require("MM_CHANNEL_ID")  # 탐색 결과를 올릴 채널
MM_SLASH_TOKEN = os.environ.get("MM_SLASH_TOKEN", "")  # 슬래시 커맨드 검증용 (선택이지만 강력 권장)

DB_PATH = os.environ.get("DB_PATH", "/data/hunt.db")

TOP_N_CANDIDATES = int(os.environ.get("TOP_N_CANDIDATES", "5"))
