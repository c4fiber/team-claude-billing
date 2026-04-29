/**
 * Discord 슬래시 커맨드 등록.
 *
 * 봇 초대 후 1회만 실행하면 됩니다. 명령어를 추가/수정한 경우 재실행.
 *
 * 사용법:
 *   환경변수 설정 후
 *   npm run register-commands
 *
 * 필요한 환경 변수:
 *   DISCORD_APP_ID    — Developer Portal에서 확인
 *   DISCORD_BOT_TOKEN — Bot 탭에서 발급
 *   DISCORD_GUILD_ID  — (선택) 특정 서버에만 등록 시 사용. 즉시 반영됨.
 *                       비우면 글로벌 등록 (반영까지 최대 1시간).
 *
 * 보안:
 *   .env 파일에 토큰을 두고 .gitignore에 추가하세요.
 *   또는 export DISCORD_BOT_TOKEN=xxx 처럼 셸 환경변수로 주입.
 */

// 이 파일은 Workers 런타임이 아닌 로컬 Node 스크립트로 실행됩니다 (tsx).
declare const process: { env: Record<string, string | undefined>; exit: (code: number) => void };

const APP_ID = process.env.DISCORD_APP_ID;
const BOT_TOKEN = process.env.DISCORD_BOT_TOKEN;
const GUILD_ID = process.env.DISCORD_GUILD_ID;

if (!APP_ID || !BOT_TOKEN) {
  console.error('DISCORD_APP_ID와 DISCORD_BOT_TOKEN 환경변수가 필요합니다.');
  process.exit(1);
}

const commands = [
  {
    name: 'status',
    description: '이번 달 입금 현황을 조회합니다.',
  },
  {
    name: 'rate',
    description: '환율 정보 안내.',
  },
  {
    name: 'help',
    description: '사용 가능한 명령어 안내.',
  },
];

const url = GUILD_ID
  ? `https://discord.com/api/v10/applications/${APP_ID}/guilds/${GUILD_ID}/commands`
  : `https://discord.com/api/v10/applications/${APP_ID}/commands`;

const response = await fetch(url, {
  method: 'PUT',
  headers: {
    Authorization: `Bot ${BOT_TOKEN}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(commands),
});

if (!response.ok) {
  const text = await response.text();
  console.error(`등록 실패 (${response.status}):`, text);
  process.exit(1);
}

await response.json();
console.log('✅ 슬래시 커맨드 등록 완료');
console.log(`   ${commands.length}개 명령어:`, commands.map((c) => c.name).join(', '));
console.log(
  `   대상: ${GUILD_ID ? `Guild ${GUILD_ID} (즉시 반영)` : '글로벌 (최대 1시간 소요)'}`,
);

export {};
