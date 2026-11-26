export default {
  mutate: ['src/tenant.ts'],
  testRunner: 'vitest',
  plugins: ['@stryker-mutator/vitest-runner'],
  reporters: ['clear-text', 'html'],
  thresholds: { high: 90, low: 80, break: 70 },
  vitest: { configFile: 'vitest.config.ts', related: true },
  concurrency: 2,
};
