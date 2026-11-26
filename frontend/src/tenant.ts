const RESERVED_TENANTS = new Set(['www', 'api', 'media', 'turn', 'docs', 'status', 'admin']);

export function getTenant(location: Pick<Location, 'hostname' | 'search'> = window.location): string {
  const query = new URLSearchParams(location.search).get('tenant');
  const host = location.hostname.toLowerCase();
  const suffix = '.voice-horizon.online';
  const candidate = (query || (host.endsWith(suffix) ? host.slice(0, -suffix.length) : '')).trim().toLowerCase();
  if (!/^[a-z0-9](?:[a-z0-9-]{1,48}[a-z0-9])$/.test(candidate)) return '';
  if (RESERVED_TENANTS.has(candidate)) return '';
  return candidate;
}
