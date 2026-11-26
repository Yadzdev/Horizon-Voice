import { describe, expect, it } from 'vitest';
import { getTenant } from './tenant';

describe('getTenant', () => {
  it('reads a server slug from its subdomain', () => {
    expect(getTenant({ hostname: 'terra-smp.voice-horizon.online', search: '' })).toBe('terra-smp');
  });

  it('allows the explicit tenant query on a shared domain', () => {
    expect(getTenant({ hostname: 'voice-horizon.online', search: '?tenant=Terra-SMP' })).toBe('terra-smp');
  });

  it('does not treat reserved service subdomains as Minecraft servers', () => {
    expect(getTenant({ hostname: 'api.voice-horizon.online', search: '' })).toBe('');
    expect(getTenant({ hostname: 'www.voice-horizon.online', search: '' })).toBe('');
  });

  it('rejects invalid slugs instead of forwarding arbitrary host input', () => {
    expect(getTenant({ hostname: 'bad_name.voice-horizon.online', search: '' })).toBe('');
    expect(getTenant({ hostname: 'voice-horizon.online', search: '?tenant=bad%2Fslug' })).toBe('');
  });

  it('returns no tenant for the main site', () => {
    expect(getTenant({ hostname: 'voice-horizon.online', search: '' })).toBe('');
  });
});
