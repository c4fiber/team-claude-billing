# UX 개선 + Members Count SSoT 통합 패치

이 패치는 두 가지를 한 번에 적용합니다:

## 변경 1: UX 개선 — 메시지 본체 갱신
버튼 클릭 시 원본 메시지의 "현재 입금 현황" 필드가 즉시 갱신됩니다.

## 변경 2: Members Count SSoT
`MEMBERS_COUNT`가 KV의 `config:members_count`로 통합됩니다.
- **Before**: GitHub Variables + wrangler.toml [vars] 두 곳에 중복
- **After**: KV에 한 곳만, Workers와 Notifier가 같은 키 참조

## 변경 파일

### Workers (TypeScript)
- `workers/src/handlers.ts` — UPDATE_MESSAGE 응답 + ConfigStore 사용
- `workers/src/types.ts` — DiscordEmbed 타입 추가
- `workers/src/config_store.ts` — **신규** — KV의 config:* 키 읽는 모듈
- `workers/wrangler.toml` — `MEMBERS_COUNT` 제거

### Notifier (Python)
- `notifier/src/kv_reader.py` — `fetch_config_int` 함수 추가, 공통 KV 호출 추출
- `notifier/src/config.py` — `members_count`를 KV에서 읽음

### GitHub Actions
- `.github/workflows/notify.yml` — `MEMBERS_COUNT` 환경변수 라인 제거


## 적용 방법

### 1. 파일 복사

zip 압축 해제 후 본인 repo로:

```bash
cd ~/workbench/team-claude-billing
unzip -o ~/Downloads/ssot_improvement.zip -d /tmp/

cp /tmp/ssot_patch/workers/src/handlers.ts workers/src/
cp /tmp/ssot_patch/workers/src/types.ts workers/src/
cp /tmp/ssot_patch/workers/src/config_store.ts workers/src/
cp /tmp/ssot_patch/workers/wrangler.toml workers/
cp /tmp/ssot_patch/notifier/src/kv_reader.py notifier/src/
cp /tmp/ssot_patch/notifier/src/config.py notifier/src/
cp /tmp/ssot_patch/.github/workflows/notify.yml .github/workflows/

# 변경 확인
git status
git diff
```

### 2. KV에 초기값 등록 (중요)

운영 시작 전에 KV에 `config:members_count` 키를 만들어야 합니다.
없어도 fallback=5로 동작하지만, 명시적 등록을 권장합니다.

```bash
cd workers

# wrangler.toml의 KV id 확인
KV_ID=$(grep '^id =' wrangler.toml | cut -d'"' -f2)

# 인원수 등록 (현재 6명이면 "6")
npx wrangler kv key put --namespace-id="$KV_ID" "config:members_count" "6"

# 검증
npx wrangler kv key get --namespace-id="$KV_ID" "config:members_count"
# 출력: 6
```

### 3. Workers 재배포

```bash
cd workers
npx tsc --noEmit          # 타입 체크 통과 확인
npx wrangler deploy       # 배포
```

### 4. GitHub Variables 정리 (선택)

GitHub repo → Settings → Secrets and variables → Actions → Variables 탭
- `MEMBERS_COUNT` 삭제 (더 이상 사용 안 함)

이 단계를 안 해도 시스템은 동작합니다. 단, 깔끔함을 위해 정리 권장.

### 5. Notifier 검증

GitHub Actions → Billing Notifier → Run workflow → mode: `dry-run`

로그에서 "USD: $137.50 (=$25.0 × 6명 × VAT 10%)"처럼 6명이 반영되는지 확인.

### 6. 인터랙션 검증

새 알림 발송:
- mode: `billing-alert`, force_days: `7`

새 알림 메시지에서 [✅ 입금완료] 버튼 클릭:
- 메시지 본체의 "현재 입금 현황" 필드가 "✅ 1 / 6"으로 즉시 갱신되는지 확인
- (X / 6에서 6은 KV에서 가져온 값)


## 인원수 변경 운영 시나리오 (향후)

만약 또 인원이 변경되면 (예: 6 → 7):

```bash
cd workers
KV_ID=$(grep '^id =' wrangler.toml | cut -d'"' -f2)
npx wrangler kv key put --namespace-id="$KV_ID" "config:members_count" "7"
```

**한 줄로 끝납니다.** Workers 재배포 불필요. Notifier도 다음 실행에서 자동으로 7을 사용.


## 향후 확장 가능성

KV의 `config:*` prefix는 다른 도메인 설정도 받아들일 수 있는 구조입니다:

```
config:members_count = "6"
config:billing_account_number = "1234-56-789012"  (예시)
config:safety_margin_percent = "5"  (현재는 환경변수)
```

추가 설정값을 KV로 옮기고 싶을 때 같은 패턴 적용.


## Trade-off 인지

이 변경의 비용:
- Notifier가 cron 1회 실행마다 KV 호출 1번 추가 (~100ms 지연)
- Workers는 인터랙션 1회당 KV 호출 1번 추가 (~5ms)
- 코드 라인 약 50줄 추가

이득:
- MEMBERS_COUNT 변경 시 단일 명령으로 끝남 (DRY)
- 두 시스템의 카운트 불일치 silent 버그 가능성 0
- 도메인 설정의 일관된 위치 (KV의 config:*)
- 향후 다른 설정도 같은 패턴으로 확장 가능
