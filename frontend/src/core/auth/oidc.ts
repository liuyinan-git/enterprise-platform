// OIDC 授权码 + PKCE 流程（手写，零额外依赖）
export interface OidcConfig {
  enabled: boolean
  issuer: string
  authorize_url: string
  token_url: string
  client_id: string
  redirect_uri: string
  scopes: string
}

const TOKEN_KEY = 'enterprise_platform.access_token'
const PKCE_VERIFIER_KEY = 'enterprise_platform.pkce_verifier'
const OIDC_STATE_KEY = 'enterprise_platform.oidc_state'

function base64url(bytes: Uint8Array): string {
  let s = ''
  for (const b of bytes) s += String.fromCharCode(b)
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function randomBytes(len: number): Uint8Array {
  const arr = new Uint8Array(len)
  crypto.getRandomValues(arr)
  return arr
}

async function sha256Base64url(plain: string): Promise<string> {
  const data = new TextEncoder().encode(plain)
  const digest = await crypto.subtle.digest('SHA-256', data)
  return base64url(new Uint8Array(digest))
}

export async function generatePkce(): Promise<{ verifier: string; challenge: string }> {
  const verifier = base64url(randomBytes(64))
  const challenge = await sha256Base64url(verifier)
  return { verifier, challenge }
}

export function buildAuthorizeUrl(config: OidcConfig, challenge: string, state: string): string {
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: config.client_id,
    redirect_uri: config.redirect_uri,
    scope: config.scopes || 'openid profile',
    code_challenge: challenge,
    code_challenge_method: 'S256',
    state,
  })
  return `${config.authorize_url}?${params.toString()}`
}

export async function exchangeCode(
  config: OidcConfig,
  code: string,
  verifier: string,
): Promise<Record<string, unknown>> {
  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    code,
    redirect_uri: config.redirect_uri,
    client_id: config.client_id,
    code_verifier: verifier,
  })
  const resp = await fetch(config.token_url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  })
  if (!resp.ok) {
    const text = await resp.text().catch(() => '')
    throw new Error(`token exchange failed: ${resp.status} ${text.slice(0, 200)}`)
  }
  return await resp.json()
}

// --- access_token 存储 ---
export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}
export function setAccessToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}
export function clearAccessToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

// --- PKCE 临时状态（登录跳转期间） ---
export function savePkce(verifier: string, state: string): void {
  sessionStorage.setItem(PKCE_VERIFIER_KEY, verifier)
  sessionStorage.setItem(OIDC_STATE_KEY, state)
}
export function loadPkce(): { verifier: string; state: string } | null {
  const verifier = sessionStorage.getItem(PKCE_VERIFIER_KEY)
  const state = sessionStorage.getItem(OIDC_STATE_KEY)
  return verifier && state ? { verifier, state } : null
}
export function clearPkce(): void {
  sessionStorage.removeItem(PKCE_VERIFIER_KEY)
  sessionStorage.removeItem(OIDC_STATE_KEY)
}
