import test from 'node:test';
import assert from 'node:assert/strict';
import { applyHistoryManagement, applyHistoryStyles } from '../web/src/history-management.js';

const source = `function renderHistory(items) {
  historyBox.replaceChildren();
  if (!items?.length) {
    return;
  }
  for (const entry of items) {
    const card = document.createElement('article');
    card.append(heading, subject, time);
    historyBox.append(card);
  }
}
`;

test('history UI exposes individual and delete-all controls', () => {
  const output = applyHistoryManagement(source);
  assert.ok(output.includes('Delete all history'));
  assert.ok(output.includes('deleteHistoryItem(entry.id)'));
  assert.ok(output.includes("method: 'DELETE'"));
  assert.ok(output.includes('Permanently delete all of your scan history'));
});

test('history UI adds safe local search and risk filters', () => {
  const output = applyHistoryManagement(source);
  assert.ok(output.includes('history-search'));
  assert.ok(output.includes('Search address, URL, token or result'));
  assert.ok(output.includes('history-risk-filter'));
  assert.ok(output.includes('High risk'));
  assert.ok(output.includes('applyHistoryFilters'));
  assert.ok(output.includes('card.dataset.historySearch = JSON.stringify(entry || {}).toLowerCase()'));
  assert.ok(output.includes('card.dataset.historyRisk'));
});

test('history export is user-triggered JSON download and uses no export upload endpoint', () => {
  const output = applyHistoryManagement(source);
  assert.ok(output.includes('Export history (JSON)'));
  assert.ok(output.includes('JSON.stringify(items || [], null, 2)'));
  assert.ok(output.includes('antiscam-guardian-history.json'));
  assert.ok(output.includes('URL.createObjectURL'));\n  assert.ok(output.includes('navigator.canShare?.({ files: [file] })'));\n  assert.ok(output.includes('navigator.share({ files: [file], title:'));\n  assert.ok(output.includes('history-export-download'));\n  assert.ok(output.includes('Tap here to download JSON'));\n  assert.ok(!output.includes('link.click()'));
  assert.ok(!output.includes('/api/history/export'));
});

test('history UI patch is idempotent', () => {
  const once = applyHistoryManagement(source);
  assert.equal(applyHistoryManagement(once), once);
});

test('history deletion and filtering styles are appended only once', () => {
  const once = applyHistoryStyles('');
  assert.ok(once.includes('history-delete-all'));
  assert.ok(once.includes('history-filter-summary'));
  assert.ok(once.includes('[data-history-entry][hidden]'));
  assert.equal(applyHistoryStyles(once), once);
});
