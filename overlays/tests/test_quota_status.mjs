import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

// Use a data URL so the same test works before and after source reconstruction.
const source = await readFile(new URL('../web/src/quota-status.js', import.meta.url), 'utf8')
  .catch(() => readFile(new URL('../web/quota-status.js', import.meta.url), 'utf8'));
const { formatQuota } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

test('Free account displays usage, remaining quota and reset time', () => {
  assert.equal(formatQuota({ premium: false, scans_used_today: 2, free_scans_per_day: 5 }),
    'Free: 2/5 scans today · 3 remaining · resets at 00:00 UTC');
});
test('Pro account displays the configured limit rather than unlimited access', () => {
  assert.equal(formatQuota({ premium: true, scans_used_today: 24, pro_scans_per_day: 100 }),
    'Pro: 24/100 scans today · 76 remaining · resets at 00:00 UTC');
});
test('Post-scan response matches initial account display for both plans', () => {
  for (const premium of [false, true]) {
    assert.equal(
      formatQuota({ premium, used_today: 3, free_limit: 5, pro_limit: 150 }),
      formatQuota({ premium, scans_used_today: 3, free_scans_per_day: 5, pro_scans_per_day: 150 }),
    );
  }
});
test('Exhausted and reduced quotas never show negative remaining scans', () => {
  for (const used_today of [5, 8]) {
    assert.match(formatQuota({ used_today, free_limit: 5 }), /0 remaining/);
  }
  assert.match(formatQuota({ used_today: 0, free_limit: 0 }), /Free: 0\/0/);
});
test('Missing and malformed quota data does not invent an allowance', () => {
  for (const data of [{}, { premium: true }, { used_today: -1, free_limit: 5 },
    { used_today: 1, free_limit: '5' }, { used_today: Infinity, free_limit: 5 }]) {
    assert.match(formatQuota(data), /usage status unavailable/);
  }
});
