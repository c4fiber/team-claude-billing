# 셋업 가이드

0부터 운영까지 약 30~45분 소요.

## 0. 사전 준비물

- GitHub 계정 (이 repo를 fork 또는 본인 계정에 새 repo로 push)
- Discord 계정 + 친구 모임 서버 관리 권한
- Cloudflare 계정 (무료, 신용카드 불필요)
- Node.js 20+ 로컬 설치
- Python 3.11+ 로컬 설치 (테스트용, 선택)

---

## 1. Discord 애플리케이션 생성 (5분)

1. https://discord.com/developers/applications → **New Application**
2. 이름: `team-claude-billing` (자유)
3. **General Information** 탭에서 다음 값들 메모:
   - `Application ID`
   - `Public Key`
4. **Bot** 탭으로 이동
5. **Reset Token** 클릭 → 토큰 복사 (1번만 보임, 안전한 곳에 저장)
6. **Privileged Gateway Intents** 섹션은 모두 OFF (사용 안 함)
7. **OAuth2 → URL Generator** 탭
   - Scopes: `bot`, `applications.commands` 체크
   - Bot Permissions: `Send Messages`, `Read Message History` 체크
   - 생성된 URL을 브라우저에서 열고 친구 모임 서버에 봇 초대

### 1-1. 채널 ID 확인

알림이 발송될 Discord 채널의 ID가 필요합니다.

1. Discord 설정 → 고급 → **개발자 모드** ON
2. 알림 채널을 우클릭 → **ID 복사**

---

## 2. Cloudflare Workers 배포 (15분)

### 2-1. 계정 및 wrangler CLI 준비

```bash
cd workers
npm install
npx wrangler login
```

### 2-2. KV 네임스페이스 생성

```bash
npx wrangler kv:namespace create DEPOSITS_KV
```

⚠️ wrangler 버전에 따라 명령어가 다릅니다:
- v3 이전: `kv:namespace create` (콜론)
- v3 이후: `kv namespace create` (공백)

출력된 `id`를 `wrangler.toml`의 `REPLACE_WITH_KV_NAMESPACE_ID` 자리에 붙여넣기.

### 2-3. 도메인 설정 등록 (시트 구성 + 가격)

KV는 입금 상태뿐 아니라 **도메인 설정의 SSoT** 역할도 합니다.
시트 구성과 가격은 Workers와 Notifier 양쪽이 같은 KV 값을 읽으므로 단일 관리됩니다.

4개 핵심 키를 등록합니다:

```bash
# wrangler.toml에 등록한 KV id를 변수로
KV_ID=$(grep '^id =' wrangler.toml | cut -d'"' -f2)

# 시트 구성 (예: Standard 3 + Premium 2)
npx wrangler kv key put --namespace-id="$KV_ID" "config:standard_seats" "3" --remote
npx wrangler kv key put --namespace-id="$KV_ID" "config:premium_seats" "2" --remote

# 시트별 월 가격 USD (현재 기준)
npx wrangler kv key put --namespace-id="$KV_ID" "config:standard_price_usd" "25" --remote
npx wrangler kv key put --namespace-id="$KV_ID" "config:premium_price_usd" "125" --remote

# 검증 (--text 플래그 필수, 안 그러면 출력이 안 보임)
npx wrangler kv key get --namespace-id="$KV_ID" "config:standard_seats" --remote --text
# → 3
npx wrangler kv key get --namespace-id="$KV_ID" "config:premium_seats" --remote --text
# → 2
```

⚠️ **`--remote` 없이 실행하면 로컬 시뮬레이터에만 등록되고 production Workers는 이 값을 못 봅니다.** 자세한 내용은 [OPERATIONS.md](./OPERATIONS.md)의 "모든 KV 명령어에 `--remote` 필수" 섹션 참고.

> 향후 시트 구성 변경 시 같은 명령을 다시 실행하면 됩니다. Workers 재배포 불필요.
> 자세한 운영 명령은 [OPERATIONS.md](./OPERATIONS.md) 참고.

### 2-4. 비밀 값 등록

```bash
npx wrangler secret put DISCORD_PUBLIC_KEY
# → 1번에서 메모한 Public Key 붙여넣기

npx wrangler secret put DISCORD_BOT_TOKEN
# → 1번에서 메모한 Bot Token

npx wrangler secret put DISCORD_APP_ID
# → 1번에서 메모한 Application ID
```

### 2-5. 배포

```bash
npx wrangler deploy
```

배포 후 출력되는 URL을 메모합니다.
예: `https://team-claude-billing.your-subdomain.workers.dev`

### 2-6. Discord에 Interactions Endpoint 등록

1. Developer Portal → 앱 → **General Information**
2. **Interactions Endpoint URL**에 위 Workers URL 붙여넣기
3. **Save Changes** 클릭

> Discord가 즉시 PING 요청을 보내 검증합니다. 검증 실패 시 저장되지 않습니다.
> 실패하면 `npx wrangler tail`로 실시간 로그를 보며 디버깅.

### 2-7. 슬래시 커맨드 등록

```bash
# .env 파일을 workers/에 만들거나 export로 환경변수 설정
export DISCORD_APP_ID=...
export DISCORD_BOT_TOKEN=...
export DISCORD_GUILD_ID=...   # 친구 모임 서버 ID (Discord에서 우클릭 복사)

npm run register-commands
```

> Guild ID를 지정하면 즉시 반영. 비우면 글로벌 등록이지만 최대 1시간 지연.

이제 Discord에서 `/status`, `/rate`, `/help`가 보입니다.

---

## 3. GitHub Actions 셋업 (10분)

### 3-1. Cloudflare API 토큰 발급

매일 cron이 KV의 입금 현황을 읽기 위해 필요.

1. https://dash.cloudflare.com/profile/api-tokens
2. **Create Token** → "Edit Cloudflare Workers" 템플릿
3. 권한 섹션에서 다음만 남김:
   - **Workers KV Storage**: Read
   - 그 외 권한은 모두 제거 가능
4. Account Resources: 본인 계정만
5. 생성 후 토큰 복사

### 3-2. Cloudflare Account ID 확인

대시보드 우측 사이드바에 있음.

### 3-3. 한국수출입은행 API 키 발급

https://www.koreaexim.go.kr/ir/HPHKIR020M01?apino=2&viewtype=C
이메일 입력 후 즉시 발급 (무료).

### 3-4. GitHub Repo Secrets/Variables 등록

본인의 repo → **Settings → Secrets and variables → Actions**

**Secrets** (민감 정보):
| Name | Value |
|------|-------|
| `DISCORD_BOT_TOKEN` | 1번에서 메모 |
| `DISCORD_CHANNEL_ID` | 1-1번 |
| `CF_ACCOUNT_ID` | 3-2번 |
| `CF_KV_NAMESPACE_ID` | 2-2번 |
| `CF_API_TOKEN` | 3-1번 |
| `KOREAEXIM_API_KEY` | 3-3번 |

**Variables** (공개 가능, 선택):
| Name | Default | 설명 |
|------|---------|------|
| `VAT_RATE` | `0.10` | 한국 부가세 |
| `SAFETY_MARGIN` | `0.05` | 안전 마진 |
| `BILLING_DAY` | `15` | 매월 결제일 |

> **참고**: 시트 구성과 가격(Standard/Premium 시트 수, 시트별 USD)은 GitHub Variables가 아닌 **KV의 `config:*` 키**에서 읽습니다 (2-3 단계에서 등록). Workers와 Notifier가 같은 KV 값을 참조하는 SSoT 구조입니다. 시트 변경(예: Standard ↔ Premium) 운영은 [OPERATIONS.md](./OPERATIONS.md) 참고.

### 3-5. 첫 dry-run 테스트

1. GitHub repo의 **Actions** 탭
2. **Billing Notifier** 워크플로우 선택
3. **Run workflow** → mode를 `dry-run`으로 선택 → 실행
4. 로그에서 계산 결과 확인

---

## 4. 실 운영 시작

### 첫 결제 사이클

1. 결제일 7일 전이 되면 자동으로 D-7 알림 발송
2. 친구들에게 알림이 가면 카톡/Discord에 다음 안내:
   > "**[✅ 입금완료]** 버튼은 본인이 입금한 후에 눌러주세요. 잘못 누르면 **[↩️ 취소]** 버튼으로 롤백 가능합니다."

### 결제 후 정산

1. 실제 카드 청구액(KRW)이 명세서에 찍히면 다음 명령으로 잉여금 기록:
   ```bash
   # data/surplus.json을 직접 편집해 actual_charge_krw 추가
   # 다음 달 자동 차감됨
   ```
2. 또는 별도 admin 슬래시 커맨드를 추가해도 됨 (확장 과제)

---

## 5. 트러블슈팅

### Discord에 봇이 보이지 않음
→ 1번 OAuth URL로 다시 초대. Bot 권한 누락 가능성.

### "Invalid request signature" 401
→ `DISCORD_PUBLIC_KEY`가 잘못 등록됨. `wrangler secret put`으로 재등록.

### Interactions Endpoint URL 저장 실패
→ Workers가 PING 요청에 응답하지 못함. 로그 확인:
```bash
cd workers && npx wrangler tail
```

### 슬래시 커맨드가 안 나타남
→ Guild ID 없이 글로벌 등록한 경우 최대 1시간 지연.
→ `register-commands.ts` 재실행, Guild ID 명시.

### GitHub Actions 워크플로우 실행 안 됨
→ cron은 fork된 repo에서는 60일 비활성 시 멈춤. workflow_dispatch로 가끔 수동 실행.

### KV에 입금 데이터가 안 쌓임
→ `wrangler tail`로 버튼 클릭 시 로그 확인. 서명 검증 통과 여부 점검.

---

## 6. 운영 모드 권장

처음 1~2개월은 다음과 같이 권장:

1. `dry-run` 모드로 D-7, D-3에 수동 발송해보며 계산 확인
2. 첫 정상 결제 후 실 청구액을 `surplus.json`에 기록
3. 5% 마진이 충분한지 검증 (보통 충분, 환율 급변동기에만 모자랄 수 있음)
4. 친구들 피드백 받아 메시지 디자인 다듬기