/**
 * Discord Interaction 서명 검증
 *
 * Discord는 모든 Interactions Endpoint 요청에 Ed25519 서명을 첨부합니다.
 * 검증하지 않으면 Discord가 봇을 비활성화시킵니다.
 *
 * Web Crypto API를 사용 — Workers 네이티브, 외부 라이브러리 불필요.
 */

export interface VerificationResult {
  valid: boolean;
  body: string;
}

export async function verifyDiscordRequest(
  request: Request,
  publicKey: string,
): Promise<VerificationResult> {
  const signature = request.headers.get('X-Signature-Ed25519');
  const timestamp = request.headers.get('X-Signature-Timestamp');
  const body = await request.text();

  if (!signature || !timestamp) {
    return { valid: false, body };
  }

  try {
    const key = await crypto.subtle.importKey(
      'raw',
      hexToBytes(publicKey),
      { name: 'Ed25519' },
      false,
      ['verify'],
    );

    const valid = await crypto.subtle.verify(
      'Ed25519',
      key,
      hexToBytes(signature),
      new TextEncoder().encode(timestamp + body),
    );

    return { valid, body };
  } catch (err) {
    console.error('Signature verification failed:', err);
    return { valid: false, body };
  }
}

function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = parseInt(hex.substr(i * 2, 2), 16);
  }
  return bytes;
}
