const HISTORY_HELPERS = `async function deleteHistoryItem(scanId) {
  if (!window.confirm('Delete this scan from your history?')) return;
  try {
    const response = await fetch('/api/history/' + encodeURIComponent(scanId), {
      method: 'DELETE',
      headers,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || 'Could not delete this scan.');
    showMessage('Scan deleted from your history.', 'success');
    await loadHistory();
  } catch (error) {
    showMessage(error.message, 'warning');
  }
}

async function deleteAllHistory() {
  if (!window.confirm('Permanently delete all of your scan history? This cannot be undone.')) return;
  try {
    const response = await fetch('/api/history', { method: 'DELETE', headers });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || 'Could not delete your history.');
    showMessage('Deleted ' + (payload.deleted_count || 0) + ' history item(s).', 'success');
    await loadHistory();
  } catch (error) {
    showMessage(error.message, 'warning');
  }
}

`;

export function applyHistoryManagement(source) {
  if (source.includes('async function deleteAllHistory()')) return source;

  const renderAnchor = 'function renderHistory(items) {\n  historyBox.replaceChildren();';
  const renderReplacement = `function renderHistory(items) {
  historyBox.replaceChildren();
  if (items?.length) {
    const toolbar = document.createElement('div');
    toolbar.className = 'history-actions';
    const deleteAllButton = document.createElement('button');
    deleteAllButton.type = 'button';
    deleteAllButton.className = 'history-delete-all';
    deleteAllButton.textContent = 'Delete all history';
    deleteAllButton.addEventListener('click', deleteAllHistory);
    toolbar.append(deleteAllButton);
    historyBox.append(toolbar);
  }`;
  if (source.split(renderAnchor).length !== 2) {
    throw new Error('Could not uniquely locate renderHistory() for deletion controls');
  }
  source = source.replace(renderAnchor, renderReplacement);

  const cardAnchor = '    card.append(heading, subject, time);';
  const cardReplacement = `    const actions = document.createElement('div');
    actions.className = 'history-actions';
    const deleteButton = document.createElement('button');
    deleteButton.type = 'button';
    deleteButton.className = 'history-delete-button';
    deleteButton.textContent = 'Delete';
    deleteButton.setAttribute('aria-label', 'Delete this scan from history');
    deleteButton.addEventListener('click', () => deleteHistoryItem(entry.id));
    actions.append(deleteButton);
    card.append(heading, subject, time, actions);`;
  if (source.split(cardAnchor).length !== 2) {
    throw new Error('Could not uniquely locate history card rendering for delete button');
  }
  source = source.replace(cardAnchor, cardReplacement);

  const helperAnchor = 'function renderHistory(items) {';
  if (source.split(helperAnchor).length !== 2) {
    throw new Error('Could not uniquely locate renderHistory() helper insertion point');
  }
  source = source.replace(helperAnchor, HISTORY_HELPERS + helperAnchor);
  return source;
}

export function applyHistoryStyles(source) {
  const marker = '/* AntiScam Guardian history deletion controls */';
  if (source.includes(marker)) return source;
  return source + `

${marker}
.history-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.65rem;
}
.history-delete-button,
.history-delete-all {
  border: 1px solid rgba(255, 120, 120, 0.45);
  border-radius: 0.65rem;
  padding: 0.45rem 0.75rem;
  background: rgba(160, 45, 55, 0.14);
  color: inherit;
  font: inherit;
  cursor: pointer;
}
.history-delete-all {
  font-size: 0.9rem;
}
.history-delete-button:disabled,
.history-delete-all:disabled {
  opacity: 0.55;
  cursor: wait;
}
`;
}
