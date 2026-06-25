# lca 사용법

실전 안내: 엔진을 켜고, CLI나 브라우저에서 에이전트를 사용합니다. 모든 명령은 레포 루트에서
`uv run`으로 실행합니다.

## 0. 최초 1회 설정

```bash
uv sync                       # 기본 설치 (Python 3.12+, uv)
uv sync --extra rag --extra web --extra search --extra mcp   # 필요한 기능
uv sync --extra browser && uv run playwright install chromium  # 브라우저 도구(선택)
uv sync --extra office        # Word/PowerPoint/Excel 생성(선택)
```

## 1. 추론 엔진 켜기 (필수)

lca는 로컬 OpenAI 호환 서버에 연결됩니다. **LM Studio** 기준: 모델을 로드하고
(`qwen2.5-coder-7b-instruct`, 두뇌용 `qwen3-coder-30b-a3b-instruct`) 로컬 서버를 시작합니다.

**엔드포인트:** lca 기본값은 `http://127.0.0.1:8080/v1`이지만 LM Studio는 `:1234`에서
서빙합니다. lca가 그쪽을 보도록 맞추세요(환경변수 설정 또는 LM Studio 포트 변경):

```powershell
# PowerShell (새 터미널부터 적용):
setx LCA_LLM__BASE_URL "http://127.0.0.1:1234/v1"
setx LCA_PROFILE "quality"     # 30B 두뇌 사용; 생략/"fast"면 7B 유지
# 변수 적용을 위해 새 터미널을 엽니다
```

신뢰하기 전에 점검:

```bash
uv run lca doctor              # GPU + 엔진 도달 여부; READY / NOT READY 출력
uv run lca config              # 실제 엔드포인트/모델/프로파일/자율성/응답 언어
```

엔진 엔드포인트에 도달하기 전에는 `doctor`가 **NOT READY**로 표시됩니다.

## 2. 코드 인덱싱 (레포 인식 답변용)

```bash
uv run lca index .             # RAG 인덱스 생성 → 답변이 file:line 인용
uv run lca stats               # 인덱싱된 청크 + 학습된 경험 수
```

## 3. 작업 시키기

```bash
uv run lca ask "오늘 날짜를 출력하는 hello.py 만들고 실행해"
uv run lca ask "이 레포의 JWT 인증 흐름 설명해줘"
uv run lca chat                # 멀티턴 세션 (Ctrl-D / 'exit' 로 종료)
uv run lca web                 # 브라우저 UI → http://127.0.0.1:8765
```

### 유용한 `ask` 옵션

| 옵션 | 효과 |
|---|---|
| `--auto` | 자율 모드: 위험 한도까지 자동 승인(y/n 안 물어봄). |
| `--plan` | 계획만 — 실행 없이 행동 제안. |
| `--verify` | 최종 답변 검증(확신 없으면 abstain; best-of-N). |
| `--no-route` | 난이도 기반 모델/검증 자동 선택 끄기. |
| `--mcp` | 로컬 MCP 서버 연결(filesystem/git/fetch). |
| `--copy` | 최종 답변을 클립보드로 복사. |
| `--md 파일` | 최종 답변을 `.md` 파일로 저장. |
| `-C 폴더` | 다른 작업 폴더 대상으로 실행. |

예시:

```bash
uv run lca ask "/health 엔드포인트랑 테스트 추가하고 pytest 돌려" --auto --verify
uv run lca ask "이 빌드 로그 요약해줘" -C ./myproject --copy
uv run lca ask "배포 체크리스트를 마크다운으로 줘" --md deploy.md
```

기본은 **gated** 모드입니다: 파일 쓰기나 셸 실행 전에 승인을 요청합니다. 무인 실행은 `--auto`.

## 4. 스킬 (Agent Skills)

```bash
uv run lca skills              # 설치된 Agent Skills(SKILL.md) 목록
```

요청이 스킬 설명과 매칭되면 에이전트가 해당 스킬의 지침을 자동으로 로드합니다
(`use_skill` 도구). 번들 스킬: 정규화 스키마, 안전한 FastAPI 엔드포인트, 접근성 React
컴포넌트, 로그 요약, 디버깅, 배포, Word/PowerPoint/Excel 생성, 마크다운, 다이어그램.
직접 추가하려면 `<작업폴더>/skills/<이름>/SKILL.md`.

## 5. 기타 명령

```bash
uv run lca mcp                 # 연결된 MCP 도구 목록
uv run lca learn               # 자가 개선 루프(rollout → reward → SFT 코퍼스)
uv run lca eval                # 평가 스위트 실행 + 스코어카드 출력
```

## 응답 언어

기본적으로 에이전트는 **한국어**로 답변합니다(코드/식별자/명령/경로는 그대로 유지).
다른 언어로 바꾸려면:

```powershell
setx LCA_RESPONSE_LANGUAGE "English"   # 또는 원하는 언어
```

## 문제 해결

- **`doctor`가 NOT READY / "Engine unreachable"** — 서버가 꺼져 있거나 포트가 다릅니다.
  LM Studio 서버를 켜고 `LCA_LLM__BASE_URL`을 설정하세요.
- **계속 7B로만 답함** — `LCA_PROFILE=quality`로 설정하고 30B를 로드하세요.
- **계속 승인을 물어봄** — 기본 gated 모드입니다. `--auto`를 쓰세요.
