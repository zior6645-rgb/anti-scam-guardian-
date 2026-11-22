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
  assert.match(output, /Delete all history/);
  assert.match(output, /deleteHistoryItem\\(entry\\.id\\)/);
  assert.match(output, /method: 'DELETE'/);
  assert.match(output, /Permanently delete all of your scan history/);
});

test('history UI adds safe local search and risk filters', () => {
  const output = applyHistoryManagement(source);
  assert.match(output, /history-search/);
  assert.match(output, /Search address, URL, token or result/);
  assert.match(output, /history-risk-filter/);
  assert.match(output, /High risk/);
  assert.match(output, /applyHistoryFilters/);
  assert.match(output, /card\\.dataset\\.historySearch = JSON\\.stringify\\(entry \\|\\| \\{\\}\\)\\.toLowerCase\\(\\)/);
  assert.match(output, /card\\.dataset\\.historyRisk/);
});

test('history export is user-triggered JSON download and includes no third-party upload', () => {
  const output = applyHistoryManagement(source);
  assert.match(output, /Export history \\(JSON\\)/);
  assert.match(output, /JSON\\.stringify\\(items \\|\\| \\[\\], null, 2\\)/);
  assert.match(output, /antiscam-guardian-history\\.json/);
  assert.match(output, /URL\\.createObjectURL/);
  assert.doesNotMatch(output, /fetch\\([^)]*history.*export/i);
});

test('history UI patch is idempotent', () => {
  const once = applyHistoryManagement(source);
  assert.equal(applyHistoryManagement(once), once);
});

test('history deletion and filtering styles are appended only once', () => {
  const once = applyHistoryStyles('');
  assert.match(once, /history-delete-all/);
  assert.match(once, /history-filter-summary/);
  assert.match(once, /\\[data-history-entry\\]\\[hidden\\]/);
  assert.equal(applyHistoryStyles(once), once);
});
