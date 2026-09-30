# hackerone_search

HackerOne Hacker API로 "AI 에이전트(hermes)가 이길 수 있는" 신생/저경쟁 버그바운티
프로그램을 탐색하고, Mattermost 스레드에서 승인 → AI가 `target.json` 생성까지
이어지는 봇. 전략 배경은 [docs/strategy.md](docs/strategy.md) 참고.

## 동작 흐름

1. Mattermost에서 `/hunt` 입력 → 봇이 채널에 새 루트 포스트로 후보 프로그램 목록(최대 5개) 게시
2. **그 스레드에** 번호로 답장(`1`, `2`, ...) → 단건 승인. `skip`이면 취소
3. 봇이 승인된 프로그램의 scope/정책을 AI에 전달 → `target.json` 생성 → 같은 스레드에
   `<도메인>.json` 파일로 업로드

이미 추천/승인/스킵된 프로그램은 SQLite에 기록되어 다음 `/hunt`에서 다시 안 나온다.

## 준비물

1. **HackerOne API 토큰** — https://hackerone.com/settings/api_token 에서 발급.
   무료, 크레딧 불필요. username + token을 `.env`의 `H1_USERNAME`/`H1_API_TOKEN`에.
2. **Mattermost 봇 계정**
   - 시스템 콘솔 → 통합 → 봇 계정 생성 → Personal Access Token 발급 → `MM_BOT_TOKEN`
   - 결과를 올릴 채널에 이 봇을 초대하고, 채널 ID를 `MM_CHANNEL_ID`에 (채널 상세 → 정보에서 확인)
   - 시스템 콘솔 → 통합 → 슬래시 커맨드 추가:
     - 명령어: `/hunt`
     - 요청 URL: `http://hunt-bot:8000/slash/hunt` (같은 docker 네트워크 기준)
     - 요청 방식: POST
     - 생성된 토큰을 `.env`의 `MM_SLASH_TOKEN`에 (없으면 검증을 생략하니 꼭 넣을 것)
3. **AI API 키** — OpenAI 호환 엔드포인트 아무거나. `AI_BASE_URL`을 비우면 OpenAI 공식
   엔드포인트를 쓴다. 모델은 `AI_MODEL`로 교체 가능, 코드 수정 불필요.
4. **target.json 스키마** — [target.json](target.json)(필드 설명)과
   [target_example.json](target_example.json)(예시)이 이미 리포지토리에 있다.
   구조적 필드(scope, url, platform 등)는 HackerOne API 데이터로 코드가 결정론적으로
   채우고([app/target_builder.py](app/target_builder.py)), AI는 정책 원문에서만
   알 수 있는 `vpn.required`와 `notes` 두 개만 판단한다([app/ai_client.py](app/ai_client.py)).
   스키마가 바뀌면 `target_builder.py`의 `build_target_json`만 고치면 된다.

## 배포 (Radxa Rock 5 / OMV, docker compose)

`docker-compose.yml`은 실제 비밀값을 담기 때문에 `.gitignore`에 있고 리포지토리에는
없다. 대신 [docker-compose_example.yml](docker-compose_example.yml)을 커밋해뒀다.

1. 이 리포지토리를 GitHub에 push하면 `.github/workflows/docker-publish.yml`이
   `ghcr.io/<owner>/<repo>:latest` 로 amd64+arm64 이미지를 빌드해 올린다.
2. `cp docker-compose_example.yml docker-compose.yml`
3. `docker-compose.yml`의 `environment:` 아래 값들을 실제 값으로 채우고
   (`env_file` 방식이 아니라 값을 직접 써넣는 구조), `networks:`를 Mattermost가
   붙어있는 기존 네트워크 이름으로 바꾼다 (`docker network ls`로 확인).
4. OMV GUI(docker compose 플러그인)에 완성된 `docker-compose.yml` 내용을 그대로
   붙여넣고 up — 별도 `.env` 파일 업로드 불필요.

## 로컬 개발

```bash
pip install -r requirements.txt
cp .env.example .env   # 값 채우기
DB_PATH=./hunt.db uvicorn app.main:app --reload
```

## 점수화 기준 튜닝

가중치/제외 키워드는 [app/scoring.py](app/scoring.py) 상단 상수
(`AUTOMATION_BANLIST`, `WEB_ASSET_TYPES`, 각 점수 계산식)에 몰아뒀다.
숫자만 바꾸면 된다.
