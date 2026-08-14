/**
 * 도메인 설정 저장소 (Single Source of Truth).
 *
 * 키 형식: "config:KEY"
 * 값 형식: 문자열
 *
 * KV 키 구조 (전체):
 *   config:standard_seats     — Standard 시트 수 (예: "3")
 *   config:premium_seats      — Premium 시트 수 (예: "2")
 *   config:standard_price_usd — Standard 시트 월 USD (예: "25")
 *   config:premium_price_usd  — Premium 시트 월 USD (예: "125")
 *   fx:latest_rate            — 환율 텍스트 스냅샷 JSON (Notifier 갱신)
 *   fx:rate_graph             — 30일 환율 그래프 PNG base64 (Notifier 갱신)
 *
 * Notifier (Python)도 같은 KV에서 같은 키를 읽습니다 → SSoT.
 */

const CONFIG_PREFIX = 'config:';

export interface FxRateSnapshot {
  rate: number;
  avg_30d: number;
  high_30d: number;
  low_30d: number;
  updated_at: string;
  data_points: number;
}

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

  /**
   * 최신 환율 스냅샷을 가져옵니다. Python notifier의 rate-graph/monthly-report 실행 후 갱신.
   * 데이터가 없거나 파싱 실패 시 null 반환.
   */
  async getFxLatestRate(): Promise<FxRateSnapshot | null> {
    const raw = await this.kv.get('fx:latest_rate');
    if (!raw) return null;
    try {
      return JSON.parse(raw) as FxRateSnapshot;
    } catch {
      return null;
    }
  }

  /**
   * 사전 생성된 환율 그래프 PNG를 가져옵니다.
   * Python notifier의 rate-graph 실행 시 base64로 저장됨.
   * 데이터가 없으면 null 반환.
   */
  async getRateGraph(): Promise<Uint8Array | null> {
    const b64 = await this.kv.get('fx:rate_graph');
    if (!b64) return null;
    try {
      const binary = atob(b64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      return bytes;
    } catch {
      return null;
    }
  }

  private fullKey(key: string): string {
    return `${CONFIG_PREFIX}${key}`;
  }
}
