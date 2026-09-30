"""Mattermost REST + WebSocket 래퍼. 스레드(root_id) 안에서만 상호작용하도록 최소 기능만 감싼다."""
import json
import logging
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

    async def start_listener(self, on_message: MessageHandler) -> None:
        """WebSocket으로 들어오는 모든 이벤트 중 'posted'만 골라 on_message로 넘긴다."""

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

        await self.driver.init_websocket(_handler)
