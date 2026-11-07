import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const source = await readFile(new URL('../web/src/report-export.js', import.meta.url), 'utf8')
  .catch(() => readFile(new URL('../web/report-export.js', import.meta.url), 'utf8'));
const { reportText } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
test('export includes observed evidence, original timestamp and limitations', () => {
  const text = reportText({ subject: 'example.org', risk_level: 'high', flags: ['Suspicious domain'], threat_intelligence: { status: 'unavailable' } }, '2026-01-01T00:00:00Z');
  for (const value of ['example.org', 'high', 'Suspicious domain', 'unavailable', '2026-01-01T00:00:00Z', 'not a security audit', 'unsigned']) assert.ok(text.includes(value));
});
test('missing evidence does not become a safe result or invented timestamp', () => {
  const text = reportText(null);
  assert.match(text, /Risk indicator: unknown/);
  assert.match(text, /Scan time: not supplied/);
  assert.match(text, /not proof of safety/);
});
test('untrusted subjects remain plain text and export excludes account secrets', () => {
  const text = reportText({ subject: '<script>alert(1)</script>', initData: 'SECRET', telegram_id: 123 });
  assert.ok(text.includes('<script>alert(1)</script>'));
  assert.ok(!text.includes('SECRET'));
  assert.ok(!text.includes('telegram_id'));
});
