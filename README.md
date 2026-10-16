# AI Campus Assistant

## 1. 프로젝트 소개

AI Campus Assistant는 대학생이 과제와 마감일을 효율적으로 관리할 수 있도록 개발한 웹 애플리케이션입니다.

사용자는 회원가입과 로그인을 통해 인증할 수 있으며, 자신의 과제를 등록하고 조회하고 완료 상태를 변경하거나 삭제할 수 있습니다.

본 프로젝트는 Python 기반의 FastAPI 백엔드와 SQLite 데이터베이스를 사용합니다.

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

### 프런트엔드
- HTML, CSS, JavaScript 기반 사용자 인터페이스
- 과제 검색 및 필터링
- 과제 현황 표시
- 규칙 기반 채팅 인터페이스

## 3. 개발 환경 및 사용 기술

| 구분 | 기술 |
|---|---|
| 프로그래밍 언어 | Python, JavaScript |
| 백엔드 프레임워크 | FastAPI |
| 데이터베이스 | SQLite |
| 인증 | JWT |
| 비밀번호 보안 | Argon2 |
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
└── README.md
```

※ `.env` 환경 설정 파일과 데이터베이스 파일은 민감한 정보 및 로컬 데이터를 포함할 수 있으므로 GitHub 저장소에 업로드하지 않습니다.

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
pip install fastapi uvicorn "pwdlib[argon2]" "PyJWT[crypto]" python-dotenv
```

### 5.4 환경 변수 설정

`backend/.env` 파일에 다음 환경 변수를 설정합니다.

```dotenv
JWT_SECRET_KEY=your_random_secret_key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

`JWT_SECRET_KEY`에는 충분히 길고 무작위인 비밀 키를 사용해야 합니다. 실제 비밀 키는 공개 저장소에 업로드하지 않습니다.

### 5.5 서버 실행

프로젝트 루트 디렉터리에서 다음 명령어를 실행합니다.

```bash
./.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

서버 실행 후 다음 주소에서 API를 확인할 수 있습니다.

- API 문서: http://127.0.0.1:8001/docs
- 상태 확인: http://127.0.0.1:8001/api/health

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

과제 API는 JWT 인증이 필요합니다. 로그인 성공 후 발급된 액세스 토큰을 `Authorization: Bearer <token>` 헤더에 포함해야 합니다.

## 7. 인증 및 보안

- 비밀번호를 평문으로 저장하지 않고 Argon2 해시를 사용합니다.
- 로그인 성공 시 JWT 액세스 토큰을 발급합니다.
- 인증이 필요한 API에서는 토큰을 검증합니다.
- 과제 조회 및 수정 시 인증된 사용자의 ID를 기준으로 데이터에 접근합니다.
- 다른 사용자의 과제에 접근하거나 수정하려는 요청은 허용하지 않습니다.
- 환경 변수 파일과 데이터베이스 파일이 공개 저장소에 포함되지 않도록 관리합니다.

## 8. 테스트 및 검증

개발 과정에서 다음 항목을 테스트했습니다.

| 테스트 항목 | 결과 |
|---|---|
| 정상적인 회원가입 및 로그인 | 성공 |
| 잘못된 로그인 정보 | HTTP 401 반환 |
| 인증 토큰 없이 과제 API 요청 | HTTP 401 반환 |
| 유효하지 않은 토큰 사용 | HTTP 401 반환 |
| 인증된 사용자의 과제 등록 및 수정 | 성공 |
| 다른 사용자의 과제 목록 조회 시도 | 해당 사용자의 과제만 조회 |
| 다른 사용자의 과제 수정 또는 삭제 시도 | HTTP 404 반환 |

위 결과는 개발 과정에서 수행한 테스트를 기준으로 작성했습니다. 모든 예외 상황에 대한 테스트가 완료되었다는 의미는 아닙니다.

## 9. 향후 개선 사항

- 프런트엔드와 JWT 인증 API의 연동 개선
- 자동화된 테스트 코드 추가
- 예외 처리 및 입력값 검증 강화
- 실제 배포 환경 구성
- 규칙 기반 채팅 기능의 확장
- 사용자 경험 및 접근성 개선

## 10. 개발 목표

본 프로젝트의 목표는 대학생의 과제 관리 과정을 단순화하고, 인증과 사용자별 데이터 분리를 적용한 웹 애플리케이션을 구현하는 것입니다.

개발 과정에서 REST API 설계, 데이터베이스 연동, 사용자 인증, 비밀번호 보안, Git을 이용한 버전 관리 등을 학습하고 적용했습니다.