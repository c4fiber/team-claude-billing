# 운영 가이드

시스템 운영 중 자주 사용하는 명령어 모음.

셋업은 [SETUP.md](./SETUP.md)를 참고하세요.

---

## ⚠️ 모든 KV 명령어에 `--remote` 필수

wrangler v3부터 `wrangler kv` 명령어의 기본값은 **로컬 시뮬레이터**입니다.
production Cloudflare KV에 영향을 주려면 **반드시 `--remote` 플래그**가 필요합니다.

```bash
# 잘못된 예 (로컬 시뮬레이터만 변경됨 — production은 영향 없음)
npx wrangler kv key put --namespace-id="$KV_ID" "config:members_count" "6"

# 올바른 예 (실제 production KV 변경)
npx wrangler kv key put --namespace-id="$KV_ID" "config:members_count" "6" --remote
```

이 문서의 모든 KV 명령어는 `--remote`를 포함합니다. 직접 추가 명령어를 만들 때 잊지 마세요.

---

## 도메인 설정 (KV의 `config:*`)

도메인 설정은 Cloudflare Workers KV에 저장됩니다 (Workers와 Notifier가 공유하는 SSoT).

키 prefix: `config:`

### 현재 등록된 키 확인

```bash
cd workers
KV_ID=$(grep '^id =' wrangler.toml | cut -d'"' -f2)

# config:* 키 모두 보기 (production)
npx wrangler kv key list --namespace-id="$KV_ID" --prefix="config:" --remote
```

### 인원수 변경 (`config:members_count`)

가장 자주 발생하는 운영 작업.

```bash
cd workers
KV_ID=$(grep '^id =' wrangler.toml | cut -d'"' -f2)

# 변경 (production KV 직접 수정)
npx wrangler kv key put --namespace-id="$KV_ID" "config:members_count" "6" --remote

# 검증
npx wrangler kv key get --namespace-id="$KV_ID" "config:members_count" --remote --text
# → 6
```

**변경 즉시 반영**:
- Workers: 다음 버튼 클릭부터 새 값 사용
- Notifier: 다음 cron 실행 (또는 `Run workflow`)부터 새 값 사용

**Workers 재배포 불필요**, **GitHub Actions yml 변경 불필요**.

### 새 도메인 설정 추가

향후 다른 설정값도 같은 패턴으로 KV로 옮길 수 있습니다.

```bash
# 예시: 안전 마진을 KV로 이동
npx wrangler kv key put --namespace-id="$KV_ID" "config:safety_margin_pct" "5" --remote
```

이렇게 하려면 코드에서 해당 값을 읽는 부분을 KV 호출로 변경해야 합니다.
- Workers: `workers/src/config_store.ts`에 메서드 추가
- Notifier: `notifier/src/config.py`에서 `fetch_config_int`/`fetch_config_str` 호출

---

## 입금 데이터 운영

### 특정 월 입금 현황 조회

```bash
KV_ID=$(grep '^id =' wrangler.toml | cut -d'"' -f2)

# 이번 달
MONTH=$(date +%Y-%m)
npx wrangler kv key get --namespace-id="$KV_ID" "deposits:$MONTH" --remote --text

# 특정 월
npx wrangler kv key get --namespace-id="$KV_ID" "deposits:2026-04" --remote --text
```

출력은 JSON. `jq`로 보기 좋게 (text 미사용 시):

```bash
npx wrangler kv key get --namespace-id="$KV_ID" "deposits:$MONTH" --remote | jq .
```

### 잘못된 입금 체크 수정 (관리자)

친구가 실수로 누른 후 취소 버튼을 못 찾는 경우, 또는 결제 실패 후 정리 시:

```bash
# 1. 현재 데이터 백업 (production KV에서 가져오기)
KV_ID=$(grep '^id =' wrangler.toml | cut -d'"' -f2)
MONTH=$(date +%Y-%m)
npx wrangler kv key get --namespace-id="$KV_ID" "deposits:$MONTH" --remote > /tmp/deposits_backup.json

# 2. 수동 편집 후 다시 저장
# (예: jq로 특정 사용자의 paid 값을 false로)
jq '.["USER_ID"].paid = false' /tmp/deposits_backup.json > /tmp/deposits_fixed.json

# 3. KV에 다시 등록 (production)
npx wrangler kv key put --namespace-id="$KV_ID" "deposits:$MONTH" --path=/tmp/deposits_fixed.json --remote
```

⚠️ 매뉴얼 편집은 신중하게. 백업 후 진행.

### 특정 월 데이터 완전 삭제 (재시작)

테스트 또는 데이터 오염 시:

```bash
KV_ID=$(grep '^id =' wrangler.toml | cut -d'"' -f2)
npx wrangler kv key delete --namespace-id="$KV_ID" "deposits:2026-04" --remote
```

---

## 잉여금 정정 (실 결제 후)

매월 실제 카드 청구액을 확인하면 `data/surplus.json`에 기록.

```bash
cd ~/workbench/team-claude-billing

# 편집기로 열기
nano data/surplus.json
```

형식:
```json
{
  "2026-04": {
    "per_person": 39900,
    "needed": 199238,
    "fx": 1380.5,
    "collected_krw": 199500,
    "actual_charge_krw": 192340
  }
}
```

`actual_charge_krw`를 채우면 다음 달 자동 차감됩니다.

```bash
git add data/surplus.json
git commit -m "chore: 2026-04 실 청구액 기록"
git push
```

---

## 트러블슈팅

### Notifier가 잘못된 인원수를 사용하는 것 같음

```bash
# 1. KV 값 확인 (--remote 필수!)
KV_ID=$(grep '^id =' wrangler.toml | cut -d'"' -f2)
npx wrangler kv key get --namespace-id="$KV_ID" "config:members_count" --remote --text

# 2. GH Actions Variables에서 MEMBERS_COUNT 흔적 확인 (있으면 안 됨)
# GitHub repo → Settings → Secrets and variables → Actions → Variables 탭
# MEMBERS_COUNT가 보이면 삭제 (지금은 KV가 SSoT)

# 3. Notifier dry-run으로 검증
# GH Actions → Billing Notifier → Run workflow → mode: dry-run
# 로그에서 "× N명" 확인
```

### Workers의 메시지 갱신이 안 됨

```bash
# 1. Workers 로그 확인
cd workers
npx wrangler tail

# 2. 다른 터미널에서 버튼 클릭 → tail에 어떤 에러가 찍히는지 확인
```

흔한 원인:
- `MEMBERS_COUNT` 환경변수에 의존하던 옛 코드가 남아있음 (이번 패치 적용 누락)
- KV에 `config:members_count`가 production이 아닌 로컬에만 등록됨 (`--remote` 누락)
- KV 권한 문제 (Workers는 자동 권한이지만 fail 시 로그 확인)

### 한국수출입은행 API 인증 실패

```bash
# 키 만료 또는 잘못된 키
# Notifier 로그에서 "환율 API 에러 응답: result=3" 확인

# 새 키 발급:
# https://www.koreaexim.go.kr/ir/HPHKIR020M01?apino=2&viewtype=C

# GitHub Secret 갱신:
# Settings → Secrets → KOREAEXIM_API_KEY → Update
```

---

## 정기 점검 체크리스트

운영 중 가끔 확인하면 좋은 항목.

### 매월 결제 후
- [ ] 실 청구액을 `data/surplus.json`에 기록
- [ ] 잉여금이 합리적인지 (보통 +몇백원~+몇천원)
- [ ] 다음 달 인당 입금액이 친구들에게 부담스럽지 않은지

### 분기별
- [ ] 환율 API 키 만료일 확인 (1년)
- [ ] Cloudflare API 토큰 만료일 확인 (TTL 설정 시)
- [ ] GitHub Actions cron 정상 동작 (실행 이력 확인)

### 연 1회
- [ ] Discord Bot Token 회전 (보안 위생)
- [ ] 사용량 검토 (Workers 무료 한도, GH Actions 무료 한도)
- [ ] Node.js / Python 버전 업데이트 점검 (deprecated actions 등)

---

## 주요 파일 위치 빠른 참조

| 항목 | 위치 |
|------|------|
| 도메인 설정 (인원수 등) | KV의 `config:*` (production, `--remote`로 접근) |
| 입금 상태 | KV의 `deposits:YYYY-MM` (production, `--remote`로 접근) |
| 잉여금 이력 | git의 `data/surplus.json` |
| 운영 파라미터 (USD, VAT 등) | GitHub Variables |
| 비밀값 | GitHub Secrets + Cloudflare Secrets |
| Workers 코드 | `workers/src/` |
| Notifier 코드 | `notifier/src/` |