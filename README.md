# AI Campus Assistant

## 1. 프로젝트 소개

AI Campus Assistant는 대학생이 과제와 마감일을 효율적으로 관리할 수 있도록 개발한 웹 애플리케이션입니다.

사용자는 회원가입과 로그인을 통해 인증할 수 있으며, 자신의 과제를 등록·수정·삭제하고 과목별로 정리할 수 있습니다. 캘린더와 통계 화면으로 일정과 진행 상황을 한눈에 확인할 수 있고, **AI 도우미**에게 남은 과제 중 무엇부터 시작해야 할지 조언을 받을 수 있습니다. 화면은 6개 언어(한국어, 몽골어, 중국어, 러시아어, 베트남어, 영어)를 지원합니다.

본 프로젝트는 Python 기반의 FastAPI 백엔드와 SQLite 데이터베이스를 사용하며, AI 기능에는 Google Gemini API를 사용합니다. 백엔드는 pytest 자동화 테스트로 검증합니다.

## 2. 주요 기능

### 사용자 인증
- 회원가입 및 로그인
- Argon2 기반 비밀번호 해시 처리
- JWT(JSON Web Token)를 이용한 인증
- 인증된 사용자 정보 조회 및 언어 설정 변경

### 과제 관리
- 과제 등록, 조회, 수정, 삭제
- 과제 완료 상태 변경 (완료 시각 기록)
- 중요도(높음/보통/낮음)와 메모
- 과제명·과목명·메모 검색, 상태·과목·중요도 필터, 마감일·중요도·최신순 정렬
- 사용자별 과제 데이터 분리
- 마감일 형식(`YYYY-MM-DD`) 검증

### 과목 관리
- 과제를 추가하면 과목이 자동으로 생성됨 (대소문자 구분 없이 같은 과목으로 인식)
- 과목 직접 추가, 이름 변경(관련 과제에도 반영), 색상 변경
- 과목별 진행률 표시
- 과제가 남아 있는 과목은 삭제할 수 없음

### 캘린더
- 월간 캘린더에 마감일 표시 (과목 색상으로 구분)
- 이전 달 / 다음 달 / 오늘로 이동
- 날짜를 선택하면 그날 마감인 과제 목록 표시
- 기한이 지난 과제가 있는 날 강조

### 통계 및 대시보드
- 남은 과제, 7일 이내 마감, 기한 초과, 완료율
- 주별 완료한 과제 수 (최근 8주) 막대 그래프
- 앞으로 7일간 마감 과제 수 막대 그래프
- 과목별·중요도별 진행률
- 그래프를 표로도 볼 수 있음 (접근성)

### AI 도우미
- 사용자의 미완료 과제를 바탕으로 학습 계획 조언
- 마감일 순 정렬, 기한 초과 과제 표시, 같은 날이면 중요도가 높은 과제 우선
- 사용자가 선택한 언어로 답변
- AI를 사용할 수 없는 경우 규칙 기반 조언으로 자동 전환

### 다국어 지원 (i18n)
- 화면의 모든 문구를 6개 언어로 제공
- 상단에서 언어를 바꾸면 즉시 반영되고, 로그인 상태라면 사용자 설정에도 저장
- 날짜와 요일은 선택한 언어의 형식으로 표시

## 3. 개발 환경 및 사용 기술

| 구분 | 기술 |
|---|---|
| 프로그래밍 언어 | Python, JavaScript |
| 백엔드 프레임워크 | FastAPI |
| 데이터베이스 | SQLite |
| 인증 | JWT |
| 비밀번호 보안 | Argon2 |
| AI | Google Gemini API (`google-genai`), Anthropic Claude API (선택) |
| 프런트엔드 | HTML, CSS, JavaScript (프레임워크 없음) |
| 테스트 | pytest, FastAPI TestClient |
| API 테스트 및 문서 | Swagger UI |
| 버전 관리 | Git, GitHub |

## 4. 프로젝트 구조

```text
AI-Campus-Assistant/
├── backend/
│   ├── __init__.py
│   ├── main.py          # 앱 생성, CORS, 회원/과제 API
│   ├── auth.py          # JWT 발급·검증, 비밀번호 해시, 현재 사용자
│   ├── database.py      # SQLite 연결, 테이블 생성, 마이그레이션
│   ├── courses.py       # 과목 API
│   ├── stats.py         # 통계 API
│   └── assistant.py     # AI 도우미 API (Gemini → Claude → 규칙 기반)
├── frontend/
│   ├── index.html
│   ├── style.css
│   ├── i18n.js          # 6개 언어 번역, 날짜 형식
│   ├── app.js           # 공통: API 호출, 로그인, 과제 목록, 수정 창, 채팅
│   ├── courses.js       # 과목 관리
│   ├── calendar.js      # 월간 캘린더
│   ├── stats.js         # 대시보드와 통계 그래프
│   └── main.js          # 시작
├── tests/               # pytest 자동화 테스트
├── .env.example
├── .gitignore
├── pytest.ini
├── requirements.txt
└── README.md
```

※ `.env` 환경 설정 파일과 데이터베이스 파일은 민감한 정보(API 키 등) 및 로컬 데이터를 포함할 수 있으므로 GitHub 저장소에 업로드하지 않습니다.

### 데이터베이스 구조

| 테이블 | 주요 컬럼 |
|---|---|
| `users` | id, username, email, password_hash, country, preferred_language |
| `courses` | id, user_id, name, color — (user_id, name) 중복 불가 |
| `assignments` | id, user_id, course_id, title, course, deadline, priority, notes, completed, completed_at |

서버가 시작될 때 이전 버전의 데이터베이스에 없는 컬럼과 테이블을 자동으로 추가하고, 기존 과제의 과목을 `courses` 테이블로 옮깁니다. 기존 데이터는 삭제되지 않습니다.

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

프로젝트 루트 디렉터리(`AI-Campus-Assistant/`)에서 `.env.example`을 복사해 `.env` 파일을 만들고 값을 채웁니다.

```bash
cp .env.example .env
```

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

### 5.7 테스트 실행

프로젝트 루트 디렉터리에서 다음 명령어를 실행합니다.

```bash
./.venv/bin/python -m pytest
```

테스트는 매번 임시 데이터베이스를 새로 만들어 사용하므로 실제 `campus.db`에는 영향을 주지 않습니다. 또한 AI API 키를 제거한 상태로 실행되며, AI 호출은 가짜 함수로 대체하므로 외부 서비스에 요청을 보내지 않습니다.

## 6. 주요 API

| HTTP 메서드 | 엔드포인트 | 설명 |
|---|---|---|
| GET | `/` | API 기본 경로 |
| GET | `/api/health` | 서버 상태 확인 |
| POST | `/api/auth/register` | 회원가입 |
| POST | `/api/auth/login` | 로그인 |
| GET | `/api/auth/me` | 현재 인증된 사용자 정보 조회 |
| PATCH | `/api/auth/me` | 언어·국가 설정 변경 |
| GET | `/api/assignments` | 과제 목록 조회 (`?status=`, `?course_id=` 필터) |
| POST | `/api/assignments` | 과제 등록 |
| PATCH | `/api/assignments/{assignment_id}` | 과제 수정 (보낸 항목만 변경) |
| DELETE | `/api/assignments/{assignment_id}` | 과제 삭제 |
| GET | `/api/courses` | 과목 목록과 과목별 과제 수 |
| POST | `/api/courses` | 과목 추가 |
| PATCH | `/api/courses/{course_id}` | 과목 이름·색상 변경 |
| DELETE | `/api/courses/{course_id}` | 과목 삭제 (과제가 없을 때만) |
| GET | `/api/stats` | 대시보드·통계 데이터 (`?weeks=1~26`) |
| POST | `/api/assistant` | AI 도우미 조언 요청 |

`/api/health`와 회원가입·로그인을 제외한 모든 API는 JWT 인증이 필요합니다. 로그인 성공 후 발급된 액세스 토큰을 `Authorization: Bearer <token>` 헤더에 포함해야 합니다.

### 과제 등록 예시

```json
{
  "title": "IoT 보고서",
  "course": "사물인터넷",
  "deadline": "2026-10-26",
  "priority": "high",
  "notes": "A4 15쪽 이상, PDF"
}
```

`priority`(기본값 `medium`)와 `notes`(기본값 빈 문자열)는 생략할 수 있습니다. 같은 이름의 과목이 없으면 자동으로 만들어집니다.

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

- 규칙 기반 조언은 외부 서비스 없이 마감일 순 정렬, 남은 일수 및 초과 일수, 중요한 과제 표시를 제공합니다.
- 따라서 API 키가 없거나, 사용 한도를 초과했거나, 네트워크 오류가 발생해도 서비스가 중단되지 않습니다.
- 백엔드에 연결할 수 없는 경우 프런트엔드가 자체 오프라인 요약을 표시합니다.
- AI 답변이 최대 길이에 도달해 잘린 경우에는 잘린 답변을 표시하지 않고 다음 단계로 넘어갑니다.
- AI 라이브러리는 실제로 호출할 때만 불러오므로, 설치되어 있지 않아도 앱의 나머지 기능은 동작합니다.

## 8. 인증 및 보안

- 비밀번호를 평문으로 저장하지 않고 Argon2 해시를 사용합니다.
- 로그인 성공 시 JWT 액세스 토큰을 발급합니다.
- 인증이 필요한 API에서는 토큰을 검증합니다.
- 과제·과목·통계 조회 및 수정 시 인증된 사용자의 ID를 기준으로 데이터에 접근합니다.
- 다른 사용자의 과제나 과목에 접근하거나 수정하려는 요청은 허용하지 않습니다 (HTTP 404).
- 모든 SQL은 매개변수(`?`)를 사용하여 SQL 인젝션을 방지합니다.
- 로그아웃 시 화면의 과제 목록과 채팅 기록을 초기화하여 다음 사용자에게 이전 사용자의 정보가 보이지 않도록 합니다.
- 사용자 입력과 AI 답변은 HTML로 직접 삽입하지 않고 `textContent`로 표시합니다 (XSS 방지).
- API 키는 백엔드의 환경 변수에만 저장되며 브라우저에 노출되지 않습니다.
- 환경 변수 파일과 데이터베이스 파일이 공개 저장소에 포함되지 않도록 관리합니다.

### 개인정보 관련 안내

AI 기능을 사용할 때 사용자의 미완료 과제 **제목, 과목명, 마감일, 중요도, 메모(앞부분 200자)**가 외부 AI 서비스(Google 또는 Anthropic)로 전송됩니다. 비밀번호와 이메일은 전송되지 않습니다. Gemini 무료 등급으로 전송된 데이터는 Google의 서비스 개선에 사용될 수 있으므로, 민감한 개인정보는 과제 제목이나 메모에 입력하지 않는 것을 권장합니다.

## 9. 테스트 및 검증

### 9.1 자동화 테스트 (pytest)

`tests/` 폴더에 83개의 테스트가 있으며 모두 통과합니다.

| 파일 | 내용 | 테스트 수 |
|---|---|---|
| `test_auth.py` | 회원가입·로그인, 중복 409, 비밀번호 해시, 만료·위조 토큰 401, 언어 변경 | 19 |
| `test_assignments.py` | 등록·수정·삭제, 입력값 검증(422), 필터, 완료 시각, 사용자 간 데이터 분리 | 26 |
| `test_courses.py` | 과목 자동 생성, 이름·색상 변경, 중복 409, 삭제 제한, 사용자 간 분리 | 14 |
| `test_stats.py` | 통계 수치, 주별·일별 집계, 사용자 간 분리 | 9 |
| `test_assistant.py` | 규칙 기반 조언, 6개 언어, Gemini→Claude→규칙 전환, 다른 사용자 과제 미전송 | 14 |
| `test_database.py` | 이전 버전 DB 마이그레이션 시 데이터 보존 | 1 |

### 9.2 수동 테스트

| 테스트 항목 | 결과 |
|---|---|
| 회원가입 후 자동 로그인, 선택한 언어로 화면 표시 | 성공 |
| 과제 추가, 수정 창에서 제목·과목·마감일·중요도·메모 변경 | 성공 |
| 검색, 상태·과목·중요도 필터, 정렬 | 성공 |
| 과목 추가, 이름·색상 변경, 과제가 있는 과목 삭제 버튼 비활성화 | 성공 |
| 캘린더 월 이동, 날짜 선택 시 과제 목록 표시 | 성공 |
| 통계 그래프 표시, 마우스 오버 시 툴팁, 표 보기 전환 | 성공 |
| 상단 언어 변경 시 전체 화면 번역 및 사용자 설정 저장 | 성공 |
| AI 도우미 답변 (Gemini, 규칙 기반) 및 출처 배지 표시 | 성공 |
| 로그아웃 시 채팅 기록 초기화 | 성공 |
| 모바일 화면(390px)에서 가로 스크롤 없이 표시 | 성공 |

위 결과는 개발 과정에서 수행한 테스트를 기준으로 작성했습니다. 모든 예외 상황에 대한 테스트가 완료되었다는 의미는 아닙니다. 번역은 개발자가 작성했으므로 각 언어 사용자의 검토를 거치면 더 자연스러워질 수 있습니다.

## 10. 향후 개선 사항

- 프런트엔드 자동화 테스트 (예: Playwright)
- 이메일 형식 검증 등 입력값 검증 강화
- AI 요청에 사용자별 요청 횟수 제한(rate limit) 적용
- 마감 알림 (이메일 또는 브라우저 알림)
- 실제 배포 환경 구성
- 사용자 경험 및 접근성 개선

## 11. 개발 목표

본 프로젝트의 목표는 대학생의 과제 관리 과정을 단순화하고, 인증과 사용자별 데이터 분리를 적용한 웹 애플리케이션을 구현하는 것입니다. 나아가 AI를 활용해 사용자가 과제의 우선순위를 판단하는 데 도움을 주고, 다양한 국적의 학생이 자신의 언어로 사용할 수 있도록 하고자 했습니다.

개발 과정에서 REST API 설계, 데이터베이스 연동과 마이그레이션, 사용자 인증, 비밀번호 보안, 외부 AI API 연동 및 장애 대비(fallback) 설계, 다국어 지원, 자동화 테스트, Git을 이용한 버전 관리 등을 학습하고 적용했습니다.
