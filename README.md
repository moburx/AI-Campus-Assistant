# AI Campus Assistant

## 1. 프로젝트 소개

AI Campus Assistant는 대학생이 과제와 마감일을 효율적으로 관리할 수 있도록 개발한 웹 애플리케이션입니다.

사용자는 회원가입과 로그인을 통해 인증할 수 있으며, 자신의 과제를 등록하고 조회하고 완료 상태를 변경하거나 삭제할 수 있습니다. 또한 **AI 도우미**에게 남은 과제 중 무엇부터 시작해야 할지 조언을 받을 수 있습니다.

본 프로젝트는 Python 기반의 FastAPI 백엔드와 SQLite 데이터베이스를 사용하며, AI 기능에는 Google Gemini API를 사용합니다.

## 2. 주요 기능

### 사용자 인증
- 회원가입 및 로그인
- Argon2 기반 비밀번호 해시 처리
- JWT(JSON Web Token)를 이용한 인증
- 인증된 사용자 정보 조회

### 과제 관리
- 과제 등록
- 등록된 과제 목록 조회
- 과제 완료 상태 변경
- 과제 삭제
- 사용자별 과제 데이터 분리
- 마감일 형식(`YYYY-MM-DD`) 검증

### AI 도우미
- 사용자의 미완료 과제를 바탕으로 학습 계획 조언
- 마감일 순 정렬 및 기한 초과 과제 표시
- 사용자가 선택한 언어로 답변 (한국어, 몽골어, 중국어, 러시아어, 베트남어, 영어)
- AI를 사용할 수 없는 경우 규칙 기반 조언으로 자동 전환

### 프런트엔드
- HTML, CSS, JavaScript 기반 사용자 인터페이스
- 과제 검색 및 필터링
- 과제 현황 표시
- AI 도우미 채팅 인터페이스 (답변 출처 배지 표시)

## 3. 개발 환경 및 사용 기술

| 구분 | 기술 |
|---|---|
| 프로그래밍 언어 | Python, JavaScript |
| 백엔드 프레임워크 | FastAPI |
| 데이터베이스 | SQLite |
| 인증 | JWT |
| 비밀번호 보안 | Argon2 |
| AI | Google Gemini API (`google-genai`), Anthropic Claude API (선택) |
| 프런트엔드 | HTML, CSS, JavaScript |
| API 테스트 및 문서 | Swagger UI |
| 버전 관리 | Git, GitHub |

## 4. 프로젝트 구조

```text
AI-Campus-Assistant/
├── backend/
│   ├── __init__.py
│   ├── database.py
│   └── main.py
├── frontend/
│   ├── app.js
│   ├── index.html
│   └── style.css
├── .gitignore
├── requirements.txt
└── README.md
```

※ `.env` 환경 설정 파일과 데이터베이스 파일은 민감한 정보(API 키 등) 및 로컬 데이터를 포함할 수 있으므로 GitHub 저장소에 업로드하지 않습니다.

## 5. 설치 및 실행 방법

### 5.1 저장소 복제

```bash
git clone git@github.com:moburx/AI-Campus-Assistant.git
cd AI-Campus-Assistant
```

### 5.2 가상 환경 생성 및 활성화

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 5.3 필요한 패키지 설치

```bash
pip install -r requirements.txt
```

### 5.4 환경 변수 설정

`.env` 파일에 다음 환경 변수를 설정합니다.

```dotenv
JWT_SECRET_KEY=your_random_secret_key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# AI 기능 (선택 사항 — 설정하지 않으면 규칙 기반 조언으로 동작)
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=your_gemini_flash_model_name
```

- `JWT_SECRET_KEY`에는 충분히 길고 무작위인 비밀 키를 사용해야 합니다.
- Gemini API 키는 [Google AI Studio](https://aistudio.google.com)에서 **Get API key → Create API key**로 발급할 수 있습니다.
- 사용 가능한 모델 이름은 계정에 따라 다를 수 있으므로, 다음 명령어로 확인한 후 `GEMINI_MODEL`에 입력합니다.

```bash
./.venv/bin/python -c "from dotenv import load_dotenv; import os; load_dotenv(); from google import genai; [print(m.name) for m in genai.Client(api_key=os.getenv('GEMINI_API_KEY')).models.list() if 'flash' in m.name]"
```

실제 비밀 키와 API 키는 공개 저장소에 업로드하지 않습니다.

### 5.5 서버 실행

프로젝트 루트 디렉터리에서 다음 명령어를 실행합니다.

```bash
./.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

서버 실행 후 다음 주소에서 API를 확인할 수 있습니다.

- API 문서: http://127.0.0.1:8001/docs
- 상태 확인: http://127.0.0.1:8001/api/health

※ `.env` 파일을 수정한 경우에는 서버를 종료(`Ctrl+C`)한 후 다시 실행해야 변경 사항이 적용됩니다.

### 5.6 프런트엔드 실행

VS Code에서 `frontend/index.html`을 마우스 오른쪽 버튼으로 클릭한 후 **Open with Live Server**를 선택합니다 (포트 5500). Live Server 확장 프로그램이 필요합니다.

CORS 설정상 `http://127.0.0.1:5500`과 `http://localhost:5500`에서의 요청만 허용됩니다.

## 6. 주요 API

| HTTP 메서드 | 엔드포인트 | 설명 |
|---|---|---|
| GET | `/` | API 기본 경로 |
| GET | `/api/health` | 서버 상태 확인 |
| POST | `/api/auth/register` | 회원가입 |
| POST | `/api/auth/login` | 로그인 |
| GET | `/api/auth/me` | 현재 인증된 사용자 정보 조회 |
| GET | `/api/assignments` | 사용자 과제 목록 조회 |
| POST | `/api/assignments` | 과제 등록 |
| PATCH | `/api/assignments/{assignment_id}` | 과제 완료 상태 변경 |
| DELETE | `/api/assignments/{assignment_id}` | 과제 삭제 |
| POST | `/api/assistant` | AI 도우미 조언 요청 |

과제 API와 AI 도우미 API는 JWT 인증이 필요합니다. 로그인 성공 후 발급된 액세스 토큰을 `Authorization: Bearer <token>` 헤더에 포함해야 합니다.

### AI 도우미 API 예시

요청:

```json
{ "question": "이번 주에 무엇부터 시작해야 할까요?" }
```

응답:

```json
{
  "answer": "현재 남은 과제들을 마감일 순으로 정리한 학습 계획입니다: ...",
  "source": "gemini",
  "assignment_count": 3
}
```

`source` 필드는 답변을 생성한 방식을 나타냅니다.

## 7. AI 도우미 동작 방식

AI 도우미는 아래 순서로 답변을 생성하며, 한 단계가 실패하면 자동으로 다음 단계로 넘어갑니다.

| 순서 | 방식 | `source` 값 | 조건 |
|---|---|---|---|
| 1 | Google Gemini | `gemini` | `GEMINI_API_KEY` 설정 시 |
| 2 | Anthropic Claude | `claude` | `ANTHROPIC_API_KEY` 설정 시 |
| 3 | 규칙 기반 조언 | `rules` | 위 방식을 모두 사용할 수 없을 때 |

- 규칙 기반 조언은 외부 서비스 없이 마감일 순 정렬, 남은 일수 및 초과 일수를 표시합니다.
- 따라서 API 키가 없거나, 사용 한도를 초과했거나, 네트워크 오류가 발생해도 서비스가 중단되지 않습니다.
- 백엔드에 연결할 수 없는 경우 프런트엔드가 자체 오프라인 답변을 표시합니다.
- AI 답변이 최대 길이에 도달해 잘린 경우에는 잘린 답변을 표시하지 않고 다음 단계로 넘어갑니다.

## 8. 인증 및 보안

- 비밀번호를 평문으로 저장하지 않고 Argon2 해시를 사용합니다.
- 로그인 성공 시 JWT 액세스 토큰을 발급합니다.
- 인증이 필요한 API에서는 토큰을 검증합니다.
- 과제 조회 및 수정 시 인증된 사용자의 ID를 기준으로 데이터에 접근합니다.
- 다른 사용자의 과제에 접근하거나 수정하려는 요청은 허용하지 않습니다.
- 로그아웃 시 화면의 과제 목록과 채팅 기록을 초기화하여 다음 사용자에게 이전 사용자의 정보가 보이지 않도록 합니다.
- AI 답변은 HTML로 직접 삽입하지 않고 안전하게 변환하여 표시합니다 (XSS 방지).
- API 키는 백엔드의 환경 변수에만 저장되며 브라우저에 노출되지 않습니다.
- 환경 변수 파일과 데이터베이스 파일이 공개 저장소에 포함되지 않도록 관리합니다.

### 개인정보 관련 안내

AI 기능을 사용할 때 사용자의 미완료 과제 **제목, 과목명, 마감일**이 외부 AI 서비스(Google 또는 Anthropic)로 전송됩니다. 비밀번호와 이메일은 전송되지 않습니다. Gemini 무료 등급으로 전송된 데이터는 Google의 서비스 개선에 사용될 수 있으므로, 민감한 개인정보는 과제 제목에 입력하지 않는 것을 권장합니다.

## 9. 테스트 및 검증

개발 과정에서 다음 항목을 테스트했습니다.

| 테스트 항목 | 결과 |
|---|---|
| 정상적인 회원가입 및 로그인 | 성공 |
| 잘못된 로그인 정보 | HTTP 401 반환 |
| 인증 토큰 없이 과제 API 요청 | HTTP 401 반환 |
| 유효하지 않거나 만료된 토큰 사용 | HTTP 401 반환 |
| 인증된 사용자의 과제 등록 및 수정 | 성공 |
| 잘못된 마감일 형식 입력 (예: `stringstri`) | HTTP 422 반환 |
| 다른 사용자의 과제 목록 조회 시도 | 해당 사용자의 과제만 조회 |
| 다른 사용자의 과제 수정 또는 삭제 시도 | HTTP 404 반환 |
| AI 도우미: 기한 초과 과제를 우선 표시하고 마감일 순으로 조언 | 성공 (`source: gemini`) |
| AI 도우미: 사용자 언어로 답변 (`ko` 사용자 → 한국어) | 성공 |
| AI 사용 불가 시 규칙 기반 조언으로 전환 | 성공 (`source: rules`) |
| 프런트엔드 채팅에서 AI 답변 및 출처 배지 표시 | 성공 |
| 로그아웃 시 채팅 기록 초기화 | 성공 |

위 결과는 개발 과정에서 수행한 테스트를 기준으로 작성했습니다. 모든 예외 상황에 대한 테스트가 완료되었다는 의미는 아닙니다.

## 10. 향후 개선 사항

- 자동화된 테스트 코드 추가 (`pytest`)
- 사용자 언어 설정값을 지원 언어 코드로 제한
- 이메일 형식 검증 등 입력값 검증 강화
- AI 요청에 사용자별 요청 횟수 제한(rate limit) 적용
- 실제 배포 환경 구성
- 사용자 경험 및 접근성 개선

## 11. 개발 목표

본 프로젝트의 목표는 대학생의 과제 관리 과정을 단순화하고, 인증과 사용자별 데이터 분리를 적용한 웹 애플리케이션을 구현하는 것입니다. 나아가 AI를 활용해 사용자가 과제의 우선순위를 판단하는 데 도움을 주고자 했습니다.

개발 과정에서 REST API 설계, 데이터베이스 연동, 사용자 인증, 비밀번호 보안, 외부 AI API 연동 및 장애 대비(fallback) 설계, Git을 이용한 버전 관리 등을 학습하고 적용했습니다.