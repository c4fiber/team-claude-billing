/**
 * Discord Interaction 핸들러.
 *
 * 두 가지 종류:
 * - APPLICATION_COMMAND (type=2): 슬래시 커맨드 (/현황, /환율 등)
 * - MESSAGE_COMPONENT (type=3): 버튼 클릭
 *
 * 버튼 클릭 시 원본 메시지의 "현재 입금 현황" 필드를 갱신합니다 (UPDATE_MESSAGE).
 */

import {
  DiscordEmbed,
  DiscordInteraction,
  InteractionResponseType,
  InteractionType,
  MessageFlags,
} from './types';
import { DepositStore, getCurrentMonthKey, DepositMap } from './store';

export interface Env {
  DISCORD_PUBLIC_KEY: string;
  DISCORD_BOT_TOKEN: string;
  DISCORD_APP_ID: string;
  DEPOSITS_KV: KVNamespace;
  TIMEZONE?: string;
  MEMBERS_COUNT?: string;  // wrangler.toml의 [vars]에서 주입. 기본값 "5".
}

const DEPOSIT_STATUS_FIELD_NAME = '현재 입금 현황';

export async function handleInteraction(
  interaction: DiscordInteraction,
  env: Env,
): Promise<Response> {
  const store = new DepositStore(env.DEPOSITS_KV);
  const user = interaction.member?.user ?? interaction.user;

  if (!user) {
    return jsonResponse({
      type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
      data: { content: '사용자 정보를 찾을 수 없습니다.', flags: MessageFlags.EPHEMERAL },
    });
  }

  // 슬래시 커맨드
  if (interaction.type === InteractionType.APPLICATION_COMMAND) {
    const cmdName = interaction.data?.name;

    if (cmdName === 'status') {
      return await handleStatus(store);
    }
    if (cmdName === 'rate') {
      return await handleRate();
    }
    if (cmdName === 'help') {
      return await handleHelp();
    }
  }

  // 버튼 클릭
  if (interaction.type === InteractionType.MESSAGE_COMPONENT) {
    const customId = interaction.data?.custom_id;

    if (customId === 'mark_paid') {
      return await handlePaidToggle(store, interaction, user.id, user.global_name ?? user.username, true, env);
    }
    if (customId === 'unmark_paid') {
      return await handlePaidToggle(store, interaction, user.id, user.global_name ?? user.username, false, env);
    }
    if (customId === 'show_status') {
      return await handleStatus(store);
    }
  }

  return jsonResponse({
    type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
    data: { content: '알 수 없는 명령입니다.', flags: MessageFlags.EPHEMERAL },
  });
}

/**
 * 입금 체크/취소를 처리하고 원본 메시지를 갱신합니다.
 *
 * 흐름:
 * 1. KV에 상태 변경 저장
 * 2. 갱신된 KV 데이터로 "현재 입금 현황" 필드 재계산
 * 3. 원본 embed의 해당 필드만 교체 (다른 필드는 그대로)
 * 4. UPDATE_MESSAGE로 응답 → Discord가 원본 메시지를 새 embed로 교체
 */
async function handlePaidToggle(
  store: DepositStore,
  interaction: DiscordInteraction,
  userId: string,
  username: string,
  paid: boolean,
  env: Env,
): Promise<Response> {
  const monthKey = getCurrentMonthKey();
  const updatedData = paid
    ? await store.markPaid(monthKey, userId, username)
    : await store.unmarkPaid(monthKey, userId);

  const membersCount = parseInt(env.MEMBERS_COUNT ?? '5', 10);

  // 원본 메시지에 embed가 없거나 message 자체가 없으면 fallback (ephemeral 응답)
  const originalEmbed = interaction.message?.embeds?.[0];
  if (!originalEmbed) {
    return jsonResponse({
      type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
      data: {
        content: paid
          ? `✅ ${username}님 ${monthKey} 입금 확인되었습니다.`
          : `↩️ ${monthKey} 입금 체크가 취소되었습니다.`,
        flags: MessageFlags.EPHEMERAL,
      },
    });
  }

  const updatedEmbed = updateDepositField(originalEmbed, updatedData, membersCount);

  return jsonResponse({
    type: InteractionResponseType.UPDATE_MESSAGE,
    data: {
      embeds: [updatedEmbed],
      // components는 명시하지 않으면 Discord가 원본 그대로 유지함
    },
  });
}

/**
 * embed의 "현재 입금 현황" 필드를 갱신합니다.
 * 다른 필드와 메타정보(title, description, color 등)는 모두 보존.
 */
function updateDepositField(
  embed: DiscordEmbed,
  data: DepositMap,
  membersCount: number,
): DiscordEmbed {
  const fields = embed.fields ?? [];
  const newFields = fields.map((field) => {
    if (field.name === DEPOSIT_STATUS_FIELD_NAME) {
      return { ...field, value: renderDepositStatusValue(data, membersCount) };
    }
    return field;
  });

  return { ...embed, fields: newFields };
}

/**
 * "현재 입금 현황" 필드의 value를 렌더링합니다.
 * notifier의 _render_deposit_status와 출력 형식이 일치해야 함.
 */
function renderDepositStatusValue(data: DepositMap, membersCount: number): string {
  const paidUsers = Object.values(data)
    .filter((d) => d.paid)
    .map((d) => d.username);

  if (paidUsers.length === 0) {
    return `⬜ 0 / ${membersCount} (아직 입금 체크 없음)`;
  }

  const lines = [`✅ ${paidUsers.length} / ${membersCount}`];
  for (const name of paidUsers) {
    lines.push(`  • ${name}`);
  }
  return lines.join('\n');
}

async function handleStatus(store: DepositStore): Promise<Response> {
  const monthKey = getCurrentMonthKey();
  const data = await store.getMonth(monthKey);
  const content = renderStatusMessage(monthKey, data);

  return jsonResponse({
    type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
    data: { content },
  });
}

async function handleRate(): Promise<Response> {
  return jsonResponse({
    type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
    data: {
      content:
        '💡 환율 정보는 매월 1일 자동 발송됩니다.\nD-7, D-3 알림에 그 시점의 적용 환율이 포함됩니다.',
      flags: MessageFlags.EPHEMERAL,
    },
  });
}

async function handleHelp(): Promise<Response> {
  const content = [
    '📖 **사용 가능한 명령어**',
    '',
    '`/status` — 이번 달 입금 현황 조회',
    '`/rate` — 환율 안내',
    '`/help` — 이 도움말',
    '',
    '결제 알림 메시지의 **[✅ 입금완료]** 버튼을 누르면 본인을 입금자로 표시합니다.',
    '잘못 누른 경우 **[↩️ 취소]** 버튼으로 롤백 가능합니다.',
  ].join('\n');

  return jsonResponse({
    type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
    data: { content, flags: MessageFlags.EPHEMERAL },
  });
}

function renderStatusMessage(monthKey: string, data: DepositMap): string {
  const entries = Object.values(data);

  if (entries.length === 0) {
    return `📊 ${monthKey} 입금 현황\n\n아직 입금 체크한 사람이 없습니다.`;
  }

  const paid = entries.filter((d) => d.paid);
  const unpaid = entries.filter((d) => !d.paid);

  const lines = [`📊 **${monthKey} 입금 현황**`, ''];

  if (paid.length > 0) {
    lines.push('**입금 완료**');
    paid.forEach((d) => lines.push(`✅ ${d.username}`));
    lines.push('');
  }

  if (unpaid.length > 0) {
    lines.push('**입금 취소됨**');
    unpaid.forEach((d) => lines.push(`⬜ ${d.username}`));
  }

  return lines.join('\n');
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
  });
}
