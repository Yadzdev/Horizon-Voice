const API = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');

export async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const queryTenant = new URLSearchParams(window.location.search).get('tenant');
  const suffix = '.voice-horizon.online';
  const host = window.location.hostname.toLowerCase();
  const hostTenant = host.endsWith(suffix) ? host.slice(0, -suffix.length) : '';
  const tenant = queryTenant || hostTenant;
  if (tenant && tenant !== 'api' && tenant !== 'media') headers.set('X-Tenant-Slug', tenant);
  const response = await fetch(`${API}${path}`, { ...options, headers, credentials: 'include', cache: 'no-store' });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || body.message || `Falha HTTP ${response.status}`);
  return body as T;
}

export const post = <T>(path: string, body?: unknown, token?: string) => request<T>(path, {
  method: 'POST', body: body === undefined ? undefined : JSON.stringify(body),
}, token);
