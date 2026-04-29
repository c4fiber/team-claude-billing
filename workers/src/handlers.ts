/**
 * Discord Interaction 핸들러.
 *
 * 두 가지 종류:
 * - APPLICATION_COMMAND (type=2): 슬래시 커맨드 (/현황, /환율 등)
 * - MESSAGE_COMPONENT (type=3): 버튼 클릭
 */

import {
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
}

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
      return await handleMarkPaid(store, user.id, user.global_name ?? user.username);
    }
    if (customId === 'unmark_paid') {
      return await handleUnmarkPaid(store, user.id);
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

async function handleMarkPaid(
  store: DepositStore,
  userId: string,
  username: string,
): Promise<Response> {
  const monthKey = getCurrentMonthKey();
  await store.markPaid(monthKey, userId, username);

  return jsonResponse({
    type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
    data: {
      content: `✅ **${username}** 님 ${monthKey} 입금 확인되었습니다.`,
      flags: MessageFlags.EPHEMERAL, // 본인에게만
    },
  });
}

async function handleUnmarkPaid(store: DepositStore, userId: string): Promise<Response> {
  const monthKey = getCurrentMonthKey();
  await store.unmarkPaid(monthKey, userId);

  return jsonResponse({
    type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
    data: {
      content: `↩️ ${monthKey} 입금 체크가 취소되었습니다.`,
      flags: MessageFlags.EPHEMERAL,
    },
  });
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
  // 환율은 외부 API 호출이 필요하므로 DEFERRED 응답 후 follow-up
  // 단순화를 위해 여기서는 안내 메시지만 반환.
  // (실제 환율 알림은 GitHub Actions의 정기 실행에서 발송)
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
