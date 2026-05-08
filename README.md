# schedular — 학교공지 AI 알림 (스케줄러 + 알림 영역)

20팀 "학교 공지 AI 개인 맞춤형 알림 서비스" 의 **스케줄러 + 알림 발송** 컴포넌트.

매 30분마다 발송 대기 알림을 Redis 큐에 적재하고, 워커가 큐에서 꺼내 SMTP 로 이메일을 보냅니다.
스크래퍼/매칭 엔진 등 다른 영역은 별도 모듈에서 만들고, 이 컴포넌트는 `fetch_pending_notifications()` 한 군데로만 연결합니다.

## 구성

```
┌─────────────┐    push job    ┌──────────┐    pop job    ┌─────────────┐
│ Celery Beat │ ─────────────▶ │  Redis   │ ────────────▶ │   Worker    │
│  (스케줄러) │                │  (큐)    │               │ (실행 엔진) │
└─────────────┘                └──────────┘               └──────┬──────┘
                                                                 │ SMTP
                                                                 ▼
                                                            (Gmail 등)
```

세 프로세스(Beat, Redis, Worker)는 서로 직접 호출하지 않고 Redis 메시지로만 대화합니다. 한 컴포넌트가 죽어도 큐에 메시지가 보존됩니다.

## 디렉토리

```
.
├── requirements.txt
├── .env.example
├── docker-compose.yml          Redis 7-alpine
├── app/
│   ├── config.py               .env 로드
│   ├── celery_app.py           Celery + Beat 30분 스케줄
│   ├── tasks.py                dispatch / send_email_task
│   └── notifier.py             smtplib STARTTLS 발송
└── scripts/
    ├── send_test_email.py      SMTP 단독 검증
    └── enqueue_test_email.py   Redis→Worker 경로 검증
```

## 사전 준비

- Python 3.11+
- Docker (Redis 띄우기 용)
- Gmail 계정 + **앱 비밀번호 16자리** (2단계 인증 활성화 후 발급)
  - Google 계정 → 보안 → 2단계 인증 → 앱 비밀번호

## 설치

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env
# .env 열어서 SMTP_USER / SMTP_PASSWORD / TEST_EMAIL_TO 채우기
```

## Redis 실행

```powershell
docker compose up -d redis
```

`localhost:6379` 에 Redis 가 뜹니다. `.env` 의 `REDIS_URL` 기본값과 일치.

## 실행

세 개의 PowerShell 창이 필요합니다 (개발 시).

### 터미널 A — Worker

```powershell
celery -A app.celery_app worker --loglevel=info --pool=solo
```

> **Windows 주의**: `--pool=solo` 필수. 기본 prefork 풀은 Windows 에서 동작하지 않습니다.

### 터미널 B — Beat (30분 스케줄러)

```powershell
celery -A app.celery_app beat --loglevel=info
```

> Beat 는 **한 개만** 띄울 것. 여러 개 띄우면 같은 시각에 디스패처가 중복 실행됩니다.

### 터미널 C — 작업 트리거 / 검증

아래 검증 스크립트들을 사용합니다.

## 산출물 검증 (3가지)

### 1. SMTP 단독 — 이메일 1건 실제 발송

```powershell
python -m scripts.send_test_email
```

Celery / Redis 우회. SMTP 자격증명만 점검합니다. 받은편지함에 메일이 도착하면 성공.

### 2. Redis 큐 + Worker 경로

```powershell
# 워커가 떠 있는 상태에서
python -m scripts.enqueue_test_email
```

`send_email_task.delay()` → Redis → Worker → SMTP 까지 전부 검증. 워커 로그에 `email sent: to=...` 가 찍히고 메일이 도착합니다.

### 3. Beat 30분 스케줄

Beat 프로세스 로그에서 다음과 같은 라인을 확인:

```
Scheduler: Sending due task dispatch-pending-notifications-every-30-min (app.tasks.dispatch_pending_notifications)
```

데모 시 30분 대기가 부담스러우면 [app/celery_app.py:25](app/celery_app.py#L25) 의 `crontab(minute="*/30")` 을 잠시 `crontab(minute="*")` (1분 주기) 로 바꿔서 보여주면 됩니다.

## 데이터 흐름 (15:00 디스패치 예시)

```
15:00:00  Beat       → Redis 에 dispatch 메시지 push
15:00:00  Worker     ← dispatch 메시지 pop, 함수 실행
15:00:01  dispatch   : DB 에서 score>=7 알림 N건 조회
15:00:01  dispatch   : send_email_task 메시지 N건을 Redis 에 push, 종료
15:00:01+ Worker     ← 발송 메시지 1건씩 pop → SMTP 전송
15:30:00  Beat       → 다음 dispatch 트리거
```

## 인터페이스 (다른 팀과의 접점)

[app/tasks.py](app/tasks.py) 의 `fetch_pending_notifications()` 가 유일한 통합 지점입니다.

```python
def fetch_pending_notifications() -> list[dict]:
    # 매칭 엔진 팀이 score>=7 인 알림을 notifications 테이블에 기록 →
    # 이 함수에서 status='pending' 인 행을 SELECT 해 반환하도록 교체
    return []
```

반환 dict 형태: `{"to": str, "subject": str, "body": str, "html": Optional[str]}`

매칭 엔진 팀의 `notifications` 테이블 스키마가 확정되면 SQL 한 번으로 채우면 됩니다.

## 안정성 정책

- **재시도**: SMTP 일시 장애 시 지수 백오프로 최대 3회 재시도 ([app/tasks.py:36-44](app/tasks.py#L36-L44)).
- **워커 사망 보호**: `task_acks_late=True` + `task_reject_on_worker_lost=True` — 워커가 처리 중 죽어도 메시지가 다른 워커로 재배분됩니다 ([app/celery_app.py:13-19](app/celery_app.py#L13-L19)).
- **중복 방지**: 디스패처는 30분 단위로만 트리거되므로, 같은 알림이 두 번 큐잉되지 않도록 `notifications.status` 를 `pending → sent` 로 갱신하는 책임은 워커 측 (또는 매칭 팀의 dedupe 로직) 에서 처리해야 합니다. (TODO: 통합 시점에 합의)

## 트러블슈팅

| 증상 | 원인 / 조치 |
|---|---|
| `ConnectionRefusedError: ... 6379` | Redis 미기동. `docker compose up -d redis` |
| 워커가 메시지를 안 가져감 (Windows) | `--pool=solo` 누락. prefork 풀은 Windows 비호환 |
| `SMTPAuthenticationError` (Gmail) | 일반 비밀번호 사용. **앱 비밀번호 16자리** 가 필요 (2단계 인증 활성화 후 발급) |
| Beat 로그에 due task 가 안 찍힘 | Beat 프로세스 미기동, 또는 timezone 불일치. `enable_utc=False`, `timezone="Asia/Seoul"` 확인 |
| 메일이 스팸함으로 감 | 발신자 도메인 신뢰도 문제. MVP 단계에선 정상 동작 증명만 목표 |

## MVP 범위 (이 컴포넌트 기준)

- [x] Celery Beat 30분 주기 디스패처
- [x] Redis 큐 (broker + result backend)
- [x] SMTP 이메일 1건 실제 발송 (재시도 포함)
- [ ] 사용자별 하루 5건 즉시 알림 제한 (v0.5)
- [ ] 일일 요약 배치 (v0.5)
- [ ] 카카오 알림톡 연동 (v1)
- [ ] FCM 푸시 (v2)
