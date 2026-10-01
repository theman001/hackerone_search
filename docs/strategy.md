# 탐색 전략 (사전1)

## 1. 전제: hermes agent가 못 하는 것

Hermes는 AI 에이전트다. 사람 해커처럼 몇 주씩 붙잡고 비즈니스 로직을 파고들거나,
수동으로 회원가입·본인인증·결제를 거치거나, WAF/anti-bot을 우회하며 버티는 방식은
안 되고(정책 위반이기도 함) 못 한다. 반대로 넓은 표면을 빠르고 지치지 않고
훑는 건 잘한다. 그러니 "이 에이전트가 이길 수 있는 게임"만 고른다.

**자동화가 강한 영역**
- 서브도메인/엔드포인트 recon, 자산 목록화
- 알려진 CVE/버전 fingerprinting, 기본 설정 오류(CORS, 보안 헤더, 노출된 `.git`/`.env`)
- IDOR 패턴(ID 순차 변경), 열린 리다이렉트, 반사형 XSS, SSRF 파라미터
- GraphQL introspection, S3/스토리지 버킷 노출, 서브도메인 테이크오버, JWT `alg=none`류

**자동화가 약한 영역**
- 멀티스텝 비즈니스 로직, 레이스 컨디션(정밀 타이밍), 모바일/바이너리/하드웨어
- 수동 KYC·유료가입이 필요한 asset, 장기 세션 유지가 필요한 플로우

**결론**: 웹/API scope 비중이 높고, 자동화 스캔을 명시적으로 금지하지 않는 프로그램만
후보로 남긴다. 정책에서 "no automated scanning / scanners not allowed / manual testing
only" 류 문구가 보이면 그 프로그램은 아예 제외한다 — 여기는 협상 대상이 아니라
프로그램 규칙이다.

## 2. 수익화 관점: 왜 "신생/저경쟁" 프로그램인가

참고 자료 3개의 공통점을 추리면:
- HackerOne/Bugcrowd 공개 프로그램이 진입장벽이 낮다 (huinmulgae4, dailylearn)
- 결제/계정/API처럼 보상이 큰 영역에 집중하라 (huinmulgae4)
- 최초 제보자만 보상받는 경우가 많아 속도가 중요하다 (dailylearn)
- 신생 스타트업·중소·공공기관 프로그램이 늘고 있다 (dailylearn)

여기서 hermes에 맞는 결론: 유명 대기업 프로그램은 이미 수백 명이 훑어서 쉬운 버그가
안 남아있다. AI 에이전트의 recon 수준 탐색으로 이길 수 있는 곳은 **아직 사람들이
많이 안 본 프로그램** — 즉 시작한 지 얼마 안 됐거나(`started_accepting_at`이 최근),
Hacktivity에 리포트가 적은 곳이다. 여기서는 "잘 알려진 취약점 클래스"도 아직
안 잡혔을 확률이 높다.

## 3. 점수화 기준 (사전2 스크립트에서 그대로 구현)

프로그램마다 아래를 점수화해서 상위 N개만 Mattermost로 올린다.

| 기준 | 근거 | 가중치 방향 |
|---|---|---|
| 정책에 자동화 스캔 금지 문구 | 위반하면 안 됨 | **있으면 즉시 제외** (점수 아님, 필터) |
| `offers_bounties` | 돈이 안 나오면 의미 없음 | false면 제외 |
| `submission_state == open` | 제출 불가 프로그램 제외 | 아니면 제외 |
| 프로그램 나이 (`started_accepting_at`) | 최근일수록 덜 훑였음 | 최근일수록 +점수 |
| 웹/API asset 비중 (`structured_scopes`) | 자동화가 잘 먹히는 영역 | 비중 높을수록 +점수 |
| in-scope asset 개수 | 넓을수록 recon 표면 ↑ | 많을수록 +점수 (과도하게 많으면 체감 감소) |
| `fast_payments` | 실제 수익화 신뢰도 | true면 +점수 |
| Hacktivity 최근 리포트 수 (상위 후보만 조회) | 경쟁 강도 proxy | 적을수록 +점수 |

가중치는 `app/hackerone.py` 상단 상수로 빼둬서 나중에 숫자만 바꾸면 된다.
지금은 이 이상 정교화하지 않는다 — 실제로 몇 주 돌려보고 리포트 채택률을 보면서
가중치를 튜닝하는 게 지금 ML스러운 스코어링 모델을 만드는 것보다 훨씬 실용적이다.

## 4. 운영 루프

1. Mattermost `/hunt` → 채널에 새 스레드(루트 포스트) 생성, 점수 상위 후보 목록 게시
2. 담당자가 그 스레드에 번호로 답장 → 단건 승인
3. 승인된 프로그램의 HackerOne API 원본 정보(정책 본문·scope·바운티 정보·URL)를
   가공 없이 JSON으로 묶어 → 같은 스레드에 `[도메인].json` 파일로 업로드
   (AI 호출 없음 — 이 파일 자체가 target.json은 아니고, 사람이 target.json을
   작성할 때 참고할 원본 자료다)
4. 승인/스킵 이력은 SQLite에 남겨 같은 프로그램을 반복 추천하지 않음

모든 상호작용은 1번이 만든 스레드 안에서만 일어난다 (번호 답장, 파일 전달 포함).

## 5. 구현 중 확인한 API 실제 제약 (설계에 반영됨)

문서만 보고 짐작하지 않고 `GET /v1/hackers/programs` 등 실제 엔드포인트를 호출/확인한
결과, 원래 가정을 두 가지 수정했다.

1. **`state != "public_mode"`(초대제) 프로그램은 아예 제외한다.** 사람 해커는 초대를
   수락하는 수동 절차를 거치지만, hermes는 그 과정을 자동화할 방법이 없다. 즉
   "탐색은 됐는데 참여를 못 하는" 프로그램은 후보로서 의미가 없다.
2. **정책 자동화-금지 키워드 필터는 추가 API 호출 없이 1단계에서 바로 적용된다.**
   `policy` 텍스트가 프로그램 목록 응답에 이미 포함돼 있어서다. 반면 scope 구성
   (웹/API 비중)과 공개 리포트 수(경쟁 강도 proxy, `GET /hackers/hacktivity?queryString=team_handle:<handle>`
   — 문서는 `team:`이라고 적혀 있지만 실제로는 에러 없이 조용히 0건만 돌려주는
   깨진 필드다, `team_handle:`이 진짜 동작하는 필드)는
   프로그램당 API 호출이 추가로 드니, **상위 20개(cheap score 기준)만 2차로 정밀
   조회**하는 깔때기 구조로 짰다 (`app/scoring.py` STAGE1_KEEP). 공개 프로그램이
   많아도 분당 요청 한도(600/min) 안에서 끝난다.

참고: HackerOne이 회원가입 없이 훑어볼 수 있는 공개 디렉터리 페이지가 있지만, 그건
문서화 안 된 내부 GraphQL로 렌더링되는 웹 프런트엔드라 API 계약이 없다. 여기서는
쓰지 않고 공식 문서화된 Hacker API(`/v1/hackers/...`)만 사용한다.

3. **`scope_exclusions` 엔드포인트는 도메인 목록이 아니라 카테고리(예: Social
   Engineering, Physical Security)다.** `target.json`의 `out_of_scope_domains`는
   대신 `structured_scopes` 중 `eligible_for_submission=false`인 항목에서 뽑는다.
   `scope_exclusions`의 카테고리는 `automation_policy.notes`에 참고 정보로만 덧붙인다.
