/**
 * Cloudflare Email Routing REST API 클라이언트.
 *
 * 필요한 API 토큰 권한:
 *   Zone > Email Routing Rules > Edit
 *   Zone > Zone > Read
 *
 * 참고: 목적지 주소 등록 시 Cloudflare가 인증 이메일을 발송합니다.
 * 인증 완료 후 라우팅 규칙이 활성화됩니다.
 */

const CF_API = 'https://api.cloudflare.com/client/v4';

export interface EmailRoutingResult {
  success: boolean;
  alreadyExists?: boolean;
  message?: string;
}

/**
 * 목적지 이메일 주소를 Cloudflare에 등록합니다.
 * 신규 등록 시 CF가 인증 이메일을 발송합니다.
 * 이미 등록된 주소면 alreadyExists: true를 반환합니다.
 */
export async function addDestinationAddress(
  zoneId: string,
  apiToken: string,
  email: string,
): Promise<EmailRoutingResult> {
  const resp = await fetch(`${CF_API}/zones/${zoneId}/email/routing/addresses`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email }),
  });

  const data = (await resp.json()) as { success: boolean; errors?: Array<{ message: string; code: number }> };

  if (!data.success) {
    const err = data.errors?.[0];
    const msg = err?.message ?? '알 수 없는 오류';
    // code 10020: already exists
    if (err?.code === 10020 || msg.toLowerCase().includes('already')) {
      return { success: true, alreadyExists: true };
    }
    return { success: false, message: msg };
  }

  return { success: true, alreadyExists: false };
}

/**
 * 이메일 라우팅 규칙을 생성합니다.
 * fromAddress → toEmail 로 전달하는 규칙.
 */
export async function createRoutingRule(
  zoneId: string,
  apiToken: string,
  fromAddress: string,
  toEmail: string,
): Promise<EmailRoutingResult> {
  const resp = await fetch(`${CF_API}/zones/${zoneId}/email/routing/rules`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      name: `Route ${fromAddress}`,
      enabled: true,
      matchers: [{ field: 'to', type: 'literal', value: fromAddress }],
      actions: [{ type: 'forward', value: [toEmail] }],
      priority: 0,
    }),
  });

  const data = (await resp.json()) as { success: boolean; errors?: Array<{ message: string; code: number }> };

  if (!data.success) {
    const err = data.errors?.[0];
    const msg = err?.message ?? '알 수 없는 오류';
    if (err?.code === 10020 || msg.toLowerCase().includes('already')) {
      return { success: true, alreadyExists: true };
    }
    return { success: false, message: msg };
  }

  return { success: true };
}
