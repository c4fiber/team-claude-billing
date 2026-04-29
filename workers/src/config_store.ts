/**
 * 도메인 설정 저장소 (Single Source of Truth).
 *
 * 키 형식: "config:KEY"
 * 값 형식: 문자열
 *
 * 현재 사용:
 *   config:members_count = "5"  (또는 운영 중 변경된 값)
 *
 * 이 저장소는 KV namespace를 인프라가 아닌 도메인 데이터로 활용합니다.
 * 환경변수와의 핵심 차이:
 *   - 환경변수: 배포 시점 결정, 변경 시 재배포 필요
 *   - KV config: 런타임 결정, 변경 시 즉시 반영
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
   * 모임 인원수. 친구 모임의 도메인 핵심 값.
   * 변경은 다음 명령으로:
   *   npx wrangler kv key put --namespace-id=<KV_ID> "config:members_count" "6"
   */
  async getMembersCount(): Promise<number> {
    return this.getInt('members_count', 5); // fallback 5
  }

  private fullKey(key: string): string {
    return `${CONFIG_PREFIX}${key}`;
  }
}
