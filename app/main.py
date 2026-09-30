"""슬래시 커맨드 진입점 + 스레드 내 상호작용. 모든 상호작용은 /hunt가 만든 루트 포스트의 스레드 안에서만 일어난다."""
import asyncio
import json
import logging

from fastapi import FastAPI, Form, HTTPException

from . import ai_client, config, db, hackerone, scoring, target_builder
from .mattermost_bot import MattermostBot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
bot: MattermostBot | None = None


@app.on_event("startup")
async def startup() -> None:
    global bot
    db.init_db()
    bot = MattermostBot()
    bot.start_listener(handle_thread_reply)  # 내부에서 전용 스레드를 띄우고 바로 리턴함
    logger.info("Mattermost bot ready, listening for thread replies")


def _run_discovery() -> tuple[list[dict], str]:
    """블로킹 I/O 모음. run_in_executor로 이벤트루프 밖에서 돌린다."""
    client = hackerone.HackerOneClient()
    programs = client.list_programs()
    seen = db.get_seen_handles()
    shortlist = scoring.stage1_filter(programs, seen)

    scored = []
    for p in shortlist:
        try:
            scopes = client.get_structured_scopes(p["handle"])
            disclosed = client.count_recent_disclosed_reports(p["handle"])
        except Exception:
            logger.warning("skip %s: fetch failed", p["handle"], exc_info=True)
            continue
        score = scoring.refine_score(p, scopes, disclosed)
        if score < 0:
            continue
        scored.append((score, p, scopes))

    scored.sort(key=lambda t: t[0], reverse=True)
    top = scored[: config.TOP_N_CANDIDATES]
    candidates = [scoring.format_candidate(p, s, sc) for sc, p, s in top]

    if not candidates:
        return [], "조건에 맞는 새 후보 프로그램을 못 찾았습니다. (정책상 자동화 금지 / 이미 추천됨 / scope 부적합 등으로 모두 제외)"

    lines = [f"🎯 새 후보 프로그램 {len(candidates)}개 (자동화 적합도 순)\n"]
    for i, c in enumerate(candidates, 1):
        lines.append(
            f"**{i}. {c['name']}** (`{c['handle']}`)\n"
            f"   - {c['url']}\n"
            f"   - 시작일: {c['started_accepting_at'] or '정보없음'} · fast_payments: {c['fast_payments']}\n"
            f"   - 자동화 가능 asset: {c['web_asset_count']}개 · score: {c['score']}"
        )
    lines.append("\n이 스레드에 **번호**로 답장하면 그 프로그램을 승인합니다 (예: `1`). `skip`이면 취소.")
    return candidates, "\n".join(lines)


async def run_discovery_and_post(channel_id: str, user_id: str) -> None:
    loop = asyncio.get_running_loop()
    try:
        candidates, message = await loop.run_in_executor(None, _run_discovery)
    except Exception as e:
        logger.exception("프로그램 탐색 실패")
        bot.post_root(channel_id, f"⚠️ 탐색 중 오류가 발생했습니다: `{e}` (컨테이너 로그 확인 필요)")
        return
    root_id = bot.post_root(channel_id, message)
    if candidates:
        db.create_session(root_id, channel_id, user_id, candidates)


@app.post("/slash/hunt")
async def slash_hunt(
    token: str = Form(...),
    channel_id: str = Form(...),
    user_id: str = Form(...),
):
    if config.MM_SLASH_TOKEN and token != config.MM_SLASH_TOKEN:
        raise HTTPException(status_code=403, detail="invalid slash token")

    asyncio.create_task(run_discovery_and_post(channel_id, user_id))
    return {"response_type": "ephemeral", "text": "🔍 프로그램 탐색 시작... 잠시 후 이 채널에 결과가 올라옵니다."}


async def handle_thread_reply(post: dict) -> None:
    root_id = post.get("root_id")
    if not root_id:
        return  # 스레드 답장이 아니면 무시

    session = db.get_session(root_id)
    if session is None or session["status"] != "awaiting_approval":
        return  # 우리가 만든 스레드가 아니거나 이미 처리됨

    channel_id = session["channel_id"]
    text = (post.get("message") or "").strip()

    if text.lower() in ("skip", "cancel", "취소"):
        db.close_session(root_id, "cancelled")
        bot.reply(channel_id, root_id, "탐색을 취소했습니다.")
        return

    candidates = json.loads(session["candidates_json"])
    try:
        idx = int(text) - 1
    except ValueError:
        bot.reply(channel_id, root_id, f"숫자(1~{len(candidates)})로 답장하거나 `skip`을 입력해주세요.")
        return
    if not (0 <= idx < len(candidates)):
        bot.reply(channel_id, root_id, f"1~{len(candidates)} 범위의 번호를 입력해주세요.")
        return

    chosen = candidates[idx]
    db.close_session(root_id, "done", chosen["handle"])
    bot.reply(channel_id, root_id, f"✅ **{chosen['name']}** 승인. target.json 생성 중...")

    loop = asyncio.get_running_loop()

    def _build() -> dict:
        client = hackerone.HackerOneClient()
        try:
            exclusions = client.get_scope_exclusions(chosen["handle"])
        except Exception:
            exclusions = []  # 부가 정보라 실패해도 진행
        categories = [e["category"] for e in exclusions if e.get("category")]
        analysis = ai_client.analyze_policy(chosen)  # 실패해도 기본값 반환(예외 없음)
        return target_builder.build_target_json(chosen, categories, analysis)

    try:
        target = await loop.run_in_executor(None, _build)
    except Exception as e:
        logger.exception("target.json 생성 실패")
        bot.reply(channel_id, root_id, f"⚠️ target.json 생성 중 오류: {e}")
        return

    filename = f"{target['project_id']}.json"
    content = json.dumps(target, ensure_ascii=False, indent=2).encode("utf-8")
    bot.upload_and_reply(channel_id, root_id, filename, content, f"`{filename}` 생성 완료")
