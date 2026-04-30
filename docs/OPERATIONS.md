# 운영 가이드

시스템 운영 중 자주 사용하는 명령어 모음.

셋업은 [SETUP.md](./SETUP.md)를 참고하세요.

---

## ⚠️ 모든 KV 명령어에 `--remote` 필수

wrangler v3부터 `wrangler kv` 명령어의 기본값은 **로컬 시뮬레이터**입니다.
production Cloudflare KV에 영향을 주려면 **반드시 `--remote` 플래그**가 필요합니다.

또한 값 조회 시 **`--text` 플래그**가 없으면 출력이 보이지 않습니다.

```bash
# 잘못된 예 (로컬 시뮬레이터만 변경됨, 출력도 안 보임)
npx wrangler kv key get --namespace-id="$KV_ID" "config:standard_seats"

# 올바른 예 (production KV + 텍스트 출력)
npx wrangler kv key get --namespace-id="$KV_ID" "config:standard_seats" --remote --text
```

이 문서의 모든 KV 명령어는 `--remote` (+조회 시 `--text`)를 포함합니다.

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

### 4개 핵심 도메인 키

| 키 | 의미 | 예시 값 |
|---|------|---------|
| `config:standard_seats` | Standard 시트 수 | `"3"` |
| `config:premium_seats` | Premium 시트 수 | `"2"` |
| `config:standard_price_usd` | Standard 시트 월 USD | `"25"` |
| `config:premium_price_usd` | Premium 시트 월 USD | `"125"` |

### 시트 구성 변경 (`config:standard_seats` / `config:premium_seats`)

가장 자주 발생하는 운영 작업.

```bash
cd workers
KV_ID=$(grep '^id =' wrangler.toml | cut -d'"' -f2)

# 예: Standard 3 + Premium 2로 변경
npx wrangler kv key put --namespace-id="$KV_ID" "config:standard_seats" "3" --remote
npx wrangler kv key put --namespace-id="$KV_ID" "config:premium_seats" "2" --remote

# 검증
npx wrangler kv key get --namespace-id="$KV_ID" "config:standard_seats" --remote --text
npx wrangler kv key get --namespace-id="$KV_ID" "config:premium_seats" --remote --text
```

**변경 즉시 반영**:
- Workers: 다음 버튼 클릭부터 새 값 사용 (총 인원 표시)
- Notifier: 다음 cron 실행부터 새 값 사용 (계산 + 메시지)

**Workers 재배포 불필요**, **GitHub Actions yml 변경 불필요**.

### 시트별 가격 변경 (Anthropic 가격 정책 변동 시)

Anthropic이 가격을 인상/조정하면:

```bash
# 예: Standard $25 → $28
npx wrangler kv key put --namespace-id="$KV_ID" "config:standard_price_usd" "28" --remote

# 예: Premium $125 → $130
npx wrangler kv key put --namespace-id="$KV_ID" "config:premium_price_usd" "130" --remote
```

### 시트 변경 시점의 주의사항

⚠️ Anthropic은 **시트 변경 시 prorated 청구**를 합니다:
- 결제 사이클 중간에 변경 → 잔여 일수만큼 일할 계산
- 우리 시스템은 그 달 전체 가격으로 계산하므로 **첫 달은 차이가 발생**

대응:
1. 시트 변경 후 첫 결제일에 카드 명세서 확인
2. 실 청구액을 `data/surplus.json`에 기록
3. 다음 달 자동으로 잉여금/부족분 보정

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

`jq`로 보기 좋게:

```bash
npx wrangler kv key get --namespace-id="$KV_ID" "deposits:$MONTH" --remote --text | jq .
```

### 잘못된 입금 체크 수정 (관리자)

친구가 실수로 누른 후 취소 버튼을 못 찾는 경우, 또는 결제 실패 후 정리 시:

```bash
# 1. 현재 데이터 백업 (production KV에서)
KV_ID=$(grep '^id =' wrangler.toml | cut -d'"' -f2)
MONTH=$(date +%Y-%m)
npx wrangler kv key get --namespace-id="$KV_ID" "deposits:$MONTH" --remote --text > /tmp/deposits_backup.json

# 2. 수동 편집 후 다시 저장
jq '.["USER_ID"].paid = false' /tmp/deposits_backup.json > /tmp/deposits_fixed.json

# 3. KV에 다시 등록 (production)
npx wrangler kv key put --namespace-id="$KV_ID" "deposits:$MONTH" --path=/tmp/deposits_fixed.json --remote
```

⚠️ 매뉴얼 편집은 신중하게. 백업 후 진행.

### 특정 월 데이터 완전 삭제 (재시작)

```bash
KV_ID=$(grep '^id =' wrangler.toml | cut -d'"' -f2)
npx wrangler kv key delete --namespace-id="$KV_ID" "deposits:2026-04" --remote
```

---

## 잉여금 정정 (실 결제 후)

매월 실제 카드 청구액을 확인하면 `data/surplus.json`에 기록.

```bash
cd ~/workbench/team-claude-billing
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

### 알림에 잘못된 시트 구성이 표시됨

```bash
# 1. KV 값 확인 (--remote --text 필수!)
KV_ID=$(grep '^id =' wrangler.toml | cut -d'"' -f2)
npx wrangler kv key get --namespace-id="$KV_ID" "config:standard_seats" --remote --text
npx wrangler kv key get --namespace-id="$KV_ID" "config:premium_seats" --remote --text

# 2. GH Actions Variables에 옛 환경변수 흔적 확인 (있으면 안 됨, 삭제)
# Settings → Secrets and variables → Actions → Variables 탭
# - MEMBERS_COUNT (KV의 config:*_seats로 이동됨)
# - USD_PER_SEAT (KV의 config:*_price_usd로 이동됨)

# 3. Notifier dry-run으로 검증
# GH Actions → Billing Notifier → Run workflow → mode: dry-run
```

### Workers의 메시지 갱신이 안 됨 또는 X / N 카운트가 이상함

```bash
# Workers 로그 확인
cd workers
npx wrangler tail
```

흔한 원인:
- KV에 `config:standard_seats` 또는 `config:premium_seats`가 production이 아닌 로컬에만 등록됨 (`--remote` 누락)
- 키 이름 오타 (예: `config:standard_seats`가 아니라 `config:standard_seat`)

### 한국수출입은행 API 인증 실패

```bash
# Notifier 로그에서 "환율 API 에러 응답: result=3" 확인
# 새 키 발급: https://www.koreaexim.go.kr/ir/HPHKIR020M01?apino=2&viewtype=C
# GitHub Secret 갱신: Settings → Secrets → KOREAEXIM_API_KEY → Update
```

---

## 정기 점검 체크리스트

### 매월 결제 후
- [ ] 실 청구액을 `data/surplus.json`에 기록
- [ ] 잉여금이 합리적인지 (보통 +몇백원~+몇천원)
- [ ] 시트 변경한 달이라면 prorated 청구액 확인

### 분기별
- [ ] 환율 API 키 만료일 확인 (1년)
- [ ] Cloudflare API 토큰 만료일 확인 (TTL 설정 시)
- [ ] GitHub Actions cron 정상 동작

### 연 1회
- [ ] Discord Bot Token 회전
- [ ] 사용량 검토 (Workers/GH Actions 무료 한도)
- [ ] Anthropic 가격 정책 확인 (`config:*_price_usd` 갱신 필요 여부)

---

## 주요 파일 위치 빠른 참조

| 항목 | 위치 |
|------|------|
| 시트 구성/가격 (도메인 핵심) | KV의 `config:*` (production, `--remote`로 접근) |
| 입금 상태 | KV의 `deposits:YYYY-MM` (production, `--remote`로 접근) |
| 잉여금 이력 | git의 `data/surplus.json` |
| 운영 파라미터 (VAT, 마진 등) | GitHub Variables |
| 비밀값 | GitHub Secrets + Cloudflare Secrets |
| Workers 코드 | `workers/src/` |
| Notifier 코드 | `notifier/src/` |