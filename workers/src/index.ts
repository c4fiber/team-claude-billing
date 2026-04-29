/**
 * Cloudflare Workers 메인 엔트리포인트.
 * Discord Interactions Endpoint URL로 등록되는 위치.
 *
 * Discord 설정:
 *   Developer Portal → 앱 → General Information
 *   → "Interactions Endpoint URL" 에 배포된 Workers URL 입력
 *   (예: https://team-claude-billing.YOUR-SUBDOMAIN.workers.dev)
 */

import { verifyDiscordRequest } from './verify';
import { handleInteraction } from './handlers';
import {
  DiscordInteraction,
  InteractionResponseType,
  InteractionType,
} from './types';
import type { Env } from './handlers';

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // 헬스체크용 GET (선택적)
    if (request.method === 'GET') {
      return new Response('Team Claude Billing Bot is running.', {
        headers: { 'Content-Type': 'text/plain; charset=utf-8' },
      });
    }

    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405 });
    }

    // 1. Discord 서명 검증 (필수)
    const { valid, body } = await verifyDiscordRequest(
      request,
      env.DISCORD_PUBLIC_KEY,
    );

    if (!valid) {
      return new Response('Invalid request signature', { status: 401 });
    }

    let interaction: DiscordInteraction;
    try {
      interaction = JSON.parse(body) as DiscordInteraction;
    } catch {
      return new Response('Invalid JSON', { status: 400 });
    }

    // 2. PING 응답 (Discord 헬스체크)
    if (interaction.type === InteractionType.PING) {
      return Response.json({ type: InteractionResponseType.PONG });
    }

    // 3. 실제 인터랙션 처리
    try {
      return await handleInteraction(interaction, env);
    } catch (err) {
      console.error('Handler error:', err);
      return Response.json({
        type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
        data: {
          content: '⚠️ 처리 중 오류가 발생했습니다. 다시 시도해주세요.',
          flags: 64,
        },
      });
    }
  },
} satisfies ExportedHandler<Env>;
