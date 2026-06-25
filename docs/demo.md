# lca — 데모 둘러보기

실제 장비(RTX 5070 Laptop, 8GB)에서 에이전트를 직접 돌려 캡처한 화면입니다.
모든 것이 **100% 로컬**입니다 — 모델(LM Studio의 Qwen), 검증, UI 모두 내 PC 안에서
동작하며 코드가 외부로 나가지 않습니다.

아래 스크린샷은 `lca web`(브라우저 UI)에서 캡처했고, 동일한 에이전트를 CLI로도 쓸 수 있습니다.

---

## 0. 엔진 준비 확인 — `lca doctor`

lca는 로컬 OpenAI 호환 서버에 연결됩니다. 엔드포인트를 맞춘 뒤 점검합니다:

```console
$ setx LCA_LLM__BASE_URL "http://127.0.0.1:1234/v1"   # LM Studio 포트
$ uv run lca doctor
                                  lca doctor
┌──────────────────────────────┬──────────────────────────────────────────────┐
│ GPU · NVIDIA RTX 5070 Laptop  │ 2067/8151 MB free · driver 592.27              │
│ Discrete GPU                  │ present                                        │
│ Engine                        │ reachable (qwen3-coder-30b-a3b-instruct,       │
│                               │ qwen2.5-coder-7b-instruct, nomic-embed-text)   │
│ Context budget                │ 16384 tokens                                   │
└──────────────────────────────┴──────────────────────────────────────────────┘
┌─ Verdict ─┐
│ READY     │   ← 엔진에 연결되면 READY
└───────────┘
```

## 1. 웹 UI 열기 — `lca web`

```console
$ uv run lca web -C ./my-project
lca web → http://127.0.0.1:8765
```

깔끔한 다크 채팅 UI입니다. 상단에 "verification-grounded · 100% local"이 표시되고,
**mode** 선택으로 `gated`(쓰기/실행 전 승인), `autonomous`(위험 한도까지 자동 승인),
`plan`(제안만) 을 전환합니다.

![landing](demo-assets/01-landing.png)

## 2. 질문하기 — 스트리밍 답변 + 검증 배지

질문을 입력하고 Enter를 누르면 답변이 토큰 단위로 스트리밍되며 마크다운으로 렌더링됩니다.
근거가 확보되면 초록색 **검증 배지**가 표시됩니다 — 에이전트는 자신이 책임질 수 있는
결과만 전달합니다. (기본 한국어로 답변하도록 설정되어 있습니다.)

![질문과 답변](demo-assets/02-qa.png)

## 3. 자율 코딩 — 도구 사용 실시간 표시

**mode → autonomous** 로 바꾸고 스크립트 작성·실행을 요청하면, 에이전트가 도구를
실시간으로 호출합니다. 여기서는 `write_file`이 `palindrome.py`를 생성하고(컬러 diff 카드로
표시), 턴이 진행되는 동안 Send 버튼은 비활성화됩니다.

![작업 중](demo-assets/03-working.png)

## 4. 실행 기반 검증

이어서 `run_python`으로 파일을 실제 실행하고, 그 출력을 읽은 뒤
**`verified: pass — grounded by executed code`** 로 마무리합니다. 판정은 모델의 주장이
아니라 **실제 실행 결과**에서 나옵니다 — 이것이 이 프로젝트의 안티-할루시네이션 핵심,
"실행이 곧 진실(execution-as-oracle)"입니다.

![완료](demo-assets/04-done.png)

---

## CLI로 동일하게

```bash
uv run lca ask "이 레포에 /health 엔드포인트랑 테스트 추가하고 pytest 돌려" --auto --verify
uv run lca ask "이 레포의 인증 흐름 설명해줘"              # RAG 기반, file:line 인용
uv run lca ask "이 빌드 로그 요약해줘" -C ./proj --copy     # 답변을 클립보드로 복사
uv run lca ask "배포 체크리스트 만들어줘" --md deploy.md     # 답변을 마크다운으로 저장
uv run lca chat                                          # 멀티턴 세션
uv run lca skills                                        # 번들 스킬 11종 목록
```

자세한 명령/옵션은 [`usage.md`](usage.md)를 참고하세요.

> 참고: 두뇌 모델(30B)은 `LCA_PROFILE=quality`일 때 사용됩니다. 그 외에는 빠른 7B가
> 쉬운 작업을 처리하고 난이도에 따라 검증을 강화합니다. 웹과 CLI는 동일한 조립 루트
> (composition root)로 에이전트를 만들기 때문에 동작이 같습니다.
