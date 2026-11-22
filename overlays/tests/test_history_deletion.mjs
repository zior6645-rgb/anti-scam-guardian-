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
  assert.match(output, /deleteHistoryItem\(entry\.id\)/);
  assert.match(output, /method: 'DELETE'/);
  assert.match(output, /Permanently delete all of your scan history/);
});

test('history UI patch is idempotent', () => {
  const once = applyHistoryManagement(source);
  assert.equal(applyHistoryManagement(once), once);
});

test('history deletion styles are appended only once', () => {
  const once = applyHistoryStyles('');
  assert.match(once, /history-delete-all/);
  assert.equal(applyHistoryStyles(once), once);
});
