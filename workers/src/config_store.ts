/**
 * 도메인 설정 저장소 (Single Source of Truth).
 *
 * 키 형식: "config:KEY"
 * 값 형식: 문자열
 *
 * 현재 사용:
 *   config:standard_seats     — Standard 시트 수 (예: "3")
 *   config:premium_seats      — Premium 시트 수 (예: "2")
 *   config:standard_price_usd — Standard 시트 월 USD (예: "25")
 *   config:premium_price_usd  — Premium 시트 월 USD (예: "125")
 *
 * Notifier (Python)도 같은 KV에서 같은 키를 읽습니다 → SSoT.
 */

const CONFIG_PREFIX = 'config:';

export class ConfigStore {
  // 인터랙션 1회 내 캐싱 — 같은 인터랙션에서 여러 번 호출되어도 KV는 1번만
  private cache = new Map<string, string | null>();

  constructor(private readonly kv: KVNamespace) {}

  /**
   * 설정값을 가져옵니다. 키가 없으면 null.
   */
  async get(key: string): Promise<string | null> {
    if (this.cache.has(key)) {
      return this.cache.get(key)!;
    }
    const value = await this.kv.get(this.fullKey(key));
    this.cache.set(key, value);
    return value;
  }

  /**
   * 설정값을 정수로 가져옵니다. 키가 없거나 파싱 실패 시 fallback 반환.
   */
  async getInt(key: string, fallback: number): Promise<number> {
    const raw = await this.get(key);
    if (raw === null) return fallback;
    const parsed = parseInt(raw, 10);
    return Number.isNaN(parsed) ? fallback : parsed;
  }

  /**
   * 전체 시트 수 (Standard + Premium).
   * 메시지 갱신 시 "X / N" 표시에 사용.
   *
   * 변경: docs/OPERATIONS.md 참고
   *   npx wrangler kv key put --namespace-id=<KV_ID> "config:standard_seats" "3" --remote
   *   npx wrangler kv key put --namespace-id=<KV_ID> "config:premium_seats" "2" --remote
   */
  async getTotalSeats(): Promise<number> {
    const standard = await this.getInt('standard_seats', 5);
    const premium = await this.getInt('premium_seats', 0);
    return standard + premium;
  }

  private fullKey(key: string): string {
    return `${CONFIG_PREFIX}${key}`;
  }
}
