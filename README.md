# Team Claude Billing Bot

Claude Team Plan 공동 결제를 위한 Discord 알림 + 셀프 입금 추적 시스템.

## 아키텍처 한눈에

```
┌─────────────── Push 경로 (시스템 → 사용자) ───────────────┐
│                                                            │
│  GitHub Actions cron → Python notifier → Discord (봇 토큰) │
│  (D-7, D-3, 매월 1일)    (환율 + 계산)      (버튼 메시지)  │
│                                                            │
└────────────────────────────────────────────────────────────┘

┌─────────────── Pull 경로 (사용자 → 시스템) ───────────────┐
│                                                            │
│  사용자 버튼 클릭 → Cloudflare Workers → Workers KV       │
│  /현황, /환율      (서명 검증 + 라우팅)   (입금 상태)     │
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
4. KV에 도메인 설정 등록: `npx wrangler kv key put --namespace-id="$KV_ID" "config:members_count" "5"`
5. GitHub Repo Secrets 설정 후 push → 자동 cron 시작.

운영 중 자주 쓰는 명령어는 `docs/OPERATIONS.md`.

## 핵심 설계 원칙

1. **Push와 Pull 경로 분리**. 알림(Python/Actions)과 인터랙션(TS/Workers)은 다른 사이클로 동작.
2. **셀프 보고 SSoT**. 입금 자동 감지가 불가능하므로 친구들의 자가 보고가 임시 진실. 실 결제 시점이 최종 검증.
3. **도메인 설정 KV로 통합 (SSoT)**. 인원수 같은 도메인 핵심 값은 KV의 `config:*` 키에서 단일 관리. 변경 시 한 명령으로 끝, 두 시스템(Workers/Notifier) 자동 반영.
4. **5% 안전 마진**. 환율 변동 + 카드 수수료를 커버. 잉여금은 다음 달 이월.
5. **무료 운영**. Workers 무료 티어 + GitHub Actions 무료 티어로 평생 무료.

## 라이선스

개인 친구 모임용. 자유롭게 수정해서 사용하세요.
