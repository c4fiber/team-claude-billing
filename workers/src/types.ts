/**
 * Discord Interactions API에서 사용하는 타입과 enum.
 * 전체 타입은 discord-api-types 패키지에 있지만, 우리에게 필요한 것만 정의.
 */

export const InteractionType = {
  PING: 1,
  APPLICATION_COMMAND: 2,
  MESSAGE_COMPONENT: 3,
} as const;

export const InteractionResponseType = {
  PONG: 1,
  CHANNEL_MESSAGE_WITH_SOURCE: 4,
  DEFERRED_CHANNEL_MESSAGE: 5,
  DEFERRED_UPDATE_MESSAGE: 6,
  UPDATE_MESSAGE: 7,
} as const;

export const MessageFlags = {
  EPHEMERAL: 64, // 본인에게만 보이는 메시지
} as const;

export const ButtonStyle = {
  PRIMARY: 1,
  SECONDARY: 2,
  SUCCESS: 3,
  DANGER: 4,
  LINK: 5,
} as const;

export interface DiscordUser {
  id: string;
  username: string;
  global_name?: string;
}

export interface DiscordInteraction {
  type: number;
  id: string;
  token: string;
  application_id: string;
  data?: {
    name?: string;
    custom_id?: string;
    options?: Array<{ name: string; value: unknown }>;
  };
  member?: {
    user: DiscordUser;
  };
  user?: DiscordUser;
  guild_id?: string;
  channel_id?: string;
  message?: {
    id: string;
    content: string;
    components?: unknown[];
  };
}
