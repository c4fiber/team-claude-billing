# Team Claude Billing Bot

Claude Team Plan 공동 결제를 위한 Discord 알림 + 셀프 입금 추적 시스템.

## 아키텍처 한눈에

```
┌─────────────── Push 경로 (시스템 → 사용자) ─────────────────────┐
│                                                                  │
│  GitHub Actions cron  →  Python notifier  →  Discord (봇 토큰)  │
│  (D-7, D-3, 매월 1일)     (환율 + 계산)       (버튼 메시지)      │
│  (rate-graph 수동 실행)    (30일 그래프 생성)  (PNG 이미지 첨부)  │
│                                ↓                                 │
│                         Cloudflare KV                            │
│                         (fx:latest_rate 갱신)                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌─────────────── Pull 경로 (사용자 → 시스템) ───────────────┐
│                                                            │
│  사용자 버튼/커맨드  →  Cloudflare Workers  →  Workers KV  │
│  /status, /rate, /help   (서명 검증 + 라우팅)  (입금 상태) │
│  [✅ 입금완료]                                 (환율 스냅샷) │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

## 디렉토리

- `workers/` — Cloudflare Workers (TypeScript). Discord Interactions Endpoint.
- `notifier/` — Python 정기 알림 발송기. GitHub Actions로 실행.
- `.github/workflows/` — cron 스케줄.
- `docs/SETUP.md` — 0부터 운영까지 단계별 셋업 가이드.
- `docs/OPERATIONS.md` — 운영 중 자주 사용하는 명령어 (인원수 변경, 데이터 정리 등).

## 빠른 시작

1. `docs/SETUP.md`를 따라가며 Discord 앱 + Cloudflare 계정 준비.
2. `workers/` 배포: `cd workers && npm install && npx wrangler deploy`
3. 슬래시 커맨드 등록: `cd workers && npm run register-commands`
4. KV에 도메인 설정 등록 (시트 구성 + 가격, 4개 키 — `docs/SETUP.md` 2-3 참고)
5. GitHub Repo Secrets 설정 후 push → 자동 cron 시작.

운영 중 자주 쓰는 명령어는 `docs/OPERATIONS.md`.

## 주요 기능

| 기능 | 실행 방법 | 설명 |
|------|-----------|------|
| 결제 알림 (D-7, D-3) | 자동 cron | 인당 입금액 + 입금 버튼 |
| 월간 환율 리포트 | 매월 1일 자동 | 30일 환율 추이 + 다음 달 예상액 |
| **30일 환율 그래프** | **workflow_dispatch → `rate-graph`** | PNG 차트를 Discord에 직접 발송 |
| `/rate` 커맨드 | Discord 슬래시 커맨드 | KV에 저장된 최신 환율 스냅샷 표시 |
| `/status` 커맨드 | Discord 슬래시 커맨드 | 이번 달 입금 현황 조회 |

## 핵심 설계 원칙

1. **Push와 Pull 경로 분리**. 알림(Python/Actions)과 인터랙션(TS/Workers)은 다른 사이클로 동작.
2. **셀프 보고 SSoT**. 입금 자동 감지가 불가능하므로 친구들의 자가 보고가 임시 진실. 실 결제 시점이 최종 검증.
3. **도메인 설정 KV로 통합 (SSoT)**. 도메인 핵심 값(시트 구성, 가격, 환율 스냅샷)은 KV 단일 관리. Workers와 Notifier 자동 반영.
4. **5% 안전 마진**. 환율 변동 + 카드 수수료를 커버. 잉여금은 다음 달 이월.
5. **무료 운영**. Workers 무료 티어 + GitHub Actions 무료 티어로 평생 무료.

## 라이선스

개인 친구 모임용. 자유롭게 수정해서 사용하세요.