import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('../web/src/report-export.js', import.meta.url), 'utf8')
  .catch(() => readFile(new URL('../web/report-export.js', import.meta.url), 'utf8'));
const { reportText } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

test('export uses the canonical report builder and preserves scan evidence', () => {
  const text = reportText({
    kind: 'url',
    subject: 'example.org',
    risk_level: 'high',
    flags: ['Suspicious domain'],
    threat_intelligence: { provider: 'PhishTank', status: 'unavailable' },
    disclaimer: 'Limited screening result, not a security audit.',
  }, '2026-01-01T00:00:00Z');
  for (const value of ['example.org', 'High-risk indicators found', 'Suspicious domain', 'unavailable', '2026-01-01T00:00:00.000Z', 'not a security audit', 'unsigned']) {
    assert.ok(text.includes(value), 'missing report content: ' + value);
  }
});

test('missing evidence remains unknown and the report is not signed', () => {
  const text = reportText(null, '2026-01-01T00:00:00Z');
  assert.match(text, /Verdict: unknown/);
  assert.match(text, /No indicator was returned/);
  assert.match(text, /unsigned temporary export/);
});

test('Telegram native download uses the temporary first-party HTTPS report endpoint', () => {
  assert.ok(source.includes("fetch('/api/reports'"));
  assert.ok(source.includes("window.Telegram?.WebApp"));
  assert.ok(source.includes('telegram.downloadFile({ url: downloadUrl.href, file_name: filename }'));
  assert.ok(source.includes("downloadUrl.protocol !== 'https:'"));
  assert.ok(source.includes('credentials: \'same-origin\''));
});

test('fallbacks remain available when Telegram native download is unavailable', () => {
  assert.ok(source.includes('navigator.canShare({ files: [file] })'));
  assert.ok(source.includes('navigator.share({ files: [file], title:'));
  assert.ok(source.includes('link.download = filename'));
  assert.ok(source.includes('URL.revokeObjectURL(blobUrl), 60000'));
});
