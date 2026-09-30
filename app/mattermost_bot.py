"""Mattermost REST + WebSocket 래퍼. 스레드(root_id) 안에서만 상호작용하도록 최소 기능만 감싼다."""
import asyncio
import json
import logging
import threading
import time
from typing import Awaitable, Callable

from mattermostdriver import Driver

from . import config

logger = logging.getLogger(__name__)

MessageHandler = Callable[[dict], Awaitable[None]]


class MattermostBot:
    def __init__(self) -> None:
        self.driver = Driver(
            {
                "url": config.MM_URL,
                "token": config.MM_BOT_TOKEN,
                "scheme": config.MM_SCHEME,
                "port": config.MM_PORT,
                "basepath": "/api/v4",
                "verify": True,
            }
        )
        self.driver.login()
        self.bot_user_id = self.driver.users.get_user("me")["id"]

    def post_root(self, channel_id: str, message: str) -> str:
        post = self.driver.posts.create_post(options={"channel_id": channel_id, "message": message})
        return post["id"]

    def reply(self, channel_id: str, root_id: str, message: str) -> str:
        post = self.driver.posts.create_post(
            options={"channel_id": channel_id, "root_id": root_id, "message": message}
        )
        return post["id"]

    def upload_and_reply(self, channel_id: str, root_id: str, filename: str, content: bytes, message: str = "") -> None:
        uploaded = self.driver.files.upload_file(
            channel_id=channel_id, files={"files": (filename, content, "application/json")}
        )
        file_id = uploaded["file_infos"][0]["id"]
        self.driver.posts.create_post(
            options={
                "channel_id": channel_id,
                "root_id": root_id,
                "message": message,
                "file_ids": [file_id],
            }
        )

    def start_listener(self, on_message: MessageHandler) -> None:
        """WebSocket 이벤트 중 'posted'만 골라 on_message로 넘긴다.

        mattermostdriver.Driver.init_websocket()은 async def가 아니라 평범한
        동기 함수고, 내부에서 자기 스스로 loop.run_until_complete()를 돌려
        블로킹한다 (라이브러리 소스로 확인). FastAPI/uvicorn이 이미 돌리고
        있는 루프 위에서 await로 부르면 "event loop is already running"으로
        죽는다 — 그래서 전용 스레드 + 그 스레드만의 새 루프에서 돌린다.
        """

        def _run() -> None:
            asyncio.set_event_loop(asyncio.new_event_loop())

            async def _handler(raw: str) -> None:
                try:
                    event = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    return
                if event.get("event") != "posted":
                    return
                try:
                    post = json.loads(event["data"]["post"])
                except (KeyError, json.JSONDecodeError):
                    return
                if post.get("user_id") == self.bot_user_id:
                    return  # 봇 자기 메시지는 무시 (루프 방지)
                await on_message(post)

            while True:
                try:
                    self.driver.init_websocket(_handler)  # 끊길 때까지 이 스레드를 블로킹
                except Exception:
                    logger.exception("Mattermost websocket 끊김, 5초 후 재연결")
                time.sleep(5)

        threading.Thread(target=_run, daemon=True, name="mm-websocket").start()
