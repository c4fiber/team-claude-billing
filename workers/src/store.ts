/**
 * 입금 상태 저장소.
 *
 * 키 형식: "deposits:YYYY-MM"
 * 값 형식: { [userId]: { username, paid, timestamp, history[] } }
 *
 * 친구 5명 규모에서는 KV의 eventual consistency가 문제되지 않습니다.
 * (동일 사용자가 1초 안에 두 번 누르는 경우는 거의 없음)
 *
 * 더 엄격한 일관성이 필요하면 D1 (SQLite)로 마이그레이션 가능.
 */

export interface DepositRecord {
  username: string;
  paid: boolean;
  timestamp: number;
  history: Array<{
    action: 'mark_paid' | 'unmark_paid';
    timestamp: number;
  }>;
}

export type DepositMap = Record<string, DepositRecord>;

export class DepositStore {
  constructor(private readonly kv: KVNamespace) {}

  async getMonth(monthKey: string): Promise<DepositMap> {
    const raw = await this.kv.get(this.key(monthKey));
    return raw ? (JSON.parse(raw) as DepositMap) : {};
  }

  async markPaid(
    monthKey: string,
    userId: string,
    username: string,
  ): Promise<DepositMap> {
    const data = await this.getMonth(monthKey);
    const now = Date.now();
    const existing = data[userId];

    data[userId] = {
      username,
      paid: true,
      timestamp: now,
      history: [
        ...(existing?.history ?? []),
        { action: 'mark_paid', timestamp: now },
      ],
    };

    await this.kv.put(this.key(monthKey), JSON.stringify(data));
    return data;
  }

  async unmarkPaid(monthKey: string, userId: string): Promise<DepositMap> {
    const data = await this.getMonth(monthKey);
    const existing = data[userId];
    if (!existing) return data;

    const now = Date.now();
    data[userId] = {
      ...existing,
      paid: false,
      timestamp: now,
      history: [
        ...existing.history,
        { action: 'unmark_paid', timestamp: now },
      ],
    };

    await this.kv.put(this.key(monthKey), JSON.stringify(data));
    return data;
  }

  private key(monthKey: string): string {
    return `deposits:${monthKey}`;
  }
}

/**
 * 현재 한국 시간 기준 "YYYY-MM" 반환.
 * Workers는 UTC로 실행되므로 KST = UTC+9 보정.
 */
export function getCurrentMonthKey(): string {
  const now = new Date();
  const kstOffset = 9 * 60 * 60 * 1000;
  const kst = new Date(now.getTime() + kstOffset);
  const year = kst.getUTCFullYear();
  const month = String(kst.getUTCMonth() + 1).padStart(2, '0');
  return `${year}-${month}`;
}
