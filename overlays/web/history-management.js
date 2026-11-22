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

function applyHistoryFilters() {
  const search = (document.getElementById('history-search')?.value || '').trim().toLowerCase();
  const risk = document.getElementById('history-risk-filter')?.value || 'all';
  const cards = Array.from(historyBox.querySelectorAll('[data-history-entry]'));
  let visible = 0;
  for (const card of cards) {
    const matchesSearch = !search || (card.dataset.historySearch || '').includes(search);
    const matchesRisk = risk === 'all' || card.dataset.historyRisk === risk;
    const show = matchesSearch && matchesRisk;
    card.hidden = !show;
    if (show) visible += 1;
  }
  const summary = document.getElementById('history-filter-summary');
  if (summary) summary.textContent = visible + ' of ' + cards.length + ' scans shown';
}

async function exportHistoryJson(items) {
  const json = JSON.stringify(items || [], null, 2);
  const filename = 'antiscam-guardian-history.json';

  // Telegram's Android WebView may ignore a programmatic anchor click.
  // Prefer the native Android share sheet when file sharing is supported.
  try {
    const file = new File([json], filename, { type: 'application/json' });
    if (navigator.share && navigator.canShare?.({ files: [file] })) {
      await navigator.share({ files: [file], title: 'AntiScam Guardian scan history' });
      showMessage('History file shared. Choose a save destination if prompted.', 'success');
      return;
    }
  } catch (error) {
    // A deliberate user cancellation should not create a second download flow.
    if (error?.name === 'AbortError') return;
    // Continue to the explicit download-link fallback.
  }

  const previous = historyBox.querySelector('.history-export-download');
  if (previous?.dataset.objectUrl) URL.revokeObjectURL(previous.dataset.objectUrl);

  const blob = new Blob([json], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.rel = 'noopener';
  link.className = 'history-export-download';
  link.dataset.objectUrl = url;
  link.textContent = 'Tap here to download JSON';
  link.setAttribute('aria-label', 'Tap to download scan history JSON file');

  const toolbar = historyBox.querySelector('.history-actions');
  if (toolbar) {
    toolbar.querySelector('.history-export-download')?.remove();
    toolbar.append(link);
  } else {
    historyBox.append(link);
  }
  showMessage('Tap “Tap here to download JSON” to save the file on your device.', 'success');
}

`;

export function applyHistoryManagement(source) {
  const alreadyPatched = source.includes('async function deleteAllHistory()');
  if (!alreadyPatched) {
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

    const cardAnchor = '    historyBox.append(card);';
    const cardReplacement = `    const actions = document.createElement('div');
    actions.className = 'history-actions';
    const deleteButton = document.createElement('button');
    deleteButton.type = 'button';
    deleteButton.className = 'history-delete-button';
    deleteButton.textContent = 'Delete';
    deleteButton.setAttribute('aria-label', 'Delete this scan from history');
    deleteButton.addEventListener('click', () => deleteHistoryItem(entry.id));
    actions.append(deleteButton);
    card.append(actions);
    historyBox.append(card);`;
    if (source.split(cardAnchor).length !== 2) {
      throw new Error('Could not uniquely locate history card append for delete button');
    }
    source = source.replace(cardAnchor, cardReplacement);

    const helperAnchor = 'function renderHistory(items) {';
    if (source.split(helperAnchor).length !== 2) {
      throw new Error('Could not uniquely locate renderHistory() helper insertion point');
    }
    source = source.replace(helperAnchor, HISTORY_HELPERS + helperAnchor);
  }

  return applyHistoryEnhancements(source);
}

function applyHistoryEnhancements(source) {
  const cardAnchor = '    card.append(actions);';
  const cardReplacement = `    card.dataset.historyEntry = 'true';
    card.dataset.historySearch = JSON.stringify(entry || {}).toLowerCase();
    card.dataset.historyRisk = String(entry?.result?.risk_level || entry?.risk_level || 'unknown').toLowerCase();
    card.append(actions);`;
  if (!source.includes("card.dataset.historyEntry = 'true';")) {
    if (source.split(cardAnchor).length !== 2) {
      throw new Error('Could not uniquely locate history card metadata insertion point');
    }
    source = source.replace(cardAnchor, cardReplacement);
  }

  const toolbarAnchor = `    toolbar.append(deleteAllButton);
    historyBox.append(toolbar);`;
  const toolbarReplacement = `    toolbar.append(deleteAllButton);

    const search = document.createElement('input');
    search.id = 'history-search';
    search.type = 'search';
    search.placeholder = 'Search address, URL, token or result…';
    search.setAttribute('aria-label', 'Search scan history');
    search.addEventListener('input', applyHistoryFilters);

    const riskFilter = document.createElement('select');
    riskFilter.id = 'history-risk-filter';
    riskFilter.setAttribute('aria-label', 'Filter scan history by risk');
    for (const [value, label] of [
      ['all', 'All results'],
      ['high', 'High risk'],
      ['critical', 'Critical'],
      ['caution', 'Caution'],
      ['suspicious', 'Suspicious'],
      ['no_obvious_flags', 'No obvious flags'],
      ['unknown', 'Unknown / not assessed'],
    ]) {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = label;
      riskFilter.append(option);
    }
    riskFilter.addEventListener('change', applyHistoryFilters);

    const exportButton = document.createElement('button');
    exportButton.type = 'button';
    exportButton.className = 'history-export';
    exportButton.textContent = 'Export history (JSON)';
    exportButton.addEventListener('click', () => { void exportHistoryJson(items); });

    const summary = document.createElement('p');
    summary.id = 'history-filter-summary';
    summary.className = 'history-filter-summary';
    toolbar.append(search, riskFilter, exportButton, summary);
    historyBox.append(toolbar);`;
  if (!source.includes("id = 'history-search'")) {
    if (source.split(toolbarAnchor).length !== 2) {
      throw new Error('Could not uniquely locate history toolbar enhancement point');
    }
    source = source.replace(toolbarAnchor, toolbarReplacement);
  }
  if (!source.includes('function applyHistoryFilters()')) {
    const helperAnchor = 'function renderHistory(items) {';
    if (source.split(helperAnchor).length !== 2) {
      throw new Error('Could not uniquely locate history filter helper insertion point');
    }
    source = source.replace(helperAnchor, HISTORY_HELPERS + helperAnchor);
  }
  if (!source.includes('.history-filter-summary')) {
    // Styling is added by applyHistoryStyles below.
  }
  return source;
}

export function applyHistoryStyles(source) {
  const marker = '/* AntiScam Guardian history deletion and filtering controls */';
  if (source.includes(marker)) return source;
  return source + `

${marker}
.history-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.65rem;
}
.history-actions input,
.history-actions select {
  min-width: 0;
  max-width: 100%;
  flex: 1 1 150px;
  border: 1px solid #38516f;
  border-radius: 0.65rem;
  padding: 0.55rem 0.7rem;
  background: #111d2e;
  color: inherit;
  font: inherit;
}
.history-delete-button,
.history-delete-all,
.history-export {
  border: 1px solid rgba(255, 120, 120, 0.45);
  border-radius: 0.65rem;
  padding: 0.45rem 0.75rem;
  background: rgba(160, 45, 55, 0.14);
  color: inherit;
  font: inherit;
  cursor: pointer;
}
.history-export {
  border-color: #38516f;
  background: #17283d;
}
.history-export-download {\n  display: inline-flex;\n  align-items: center;\n  border: 1px solid #38516f;\n  border-radius: 0.65rem;\n  padding: 0.55rem 0.75rem;\n  color: #b9d8ff;\n  text-decoration: underline;\n  font: inherit;\n}\n.history-filter-summary {
  flex: 1 1 100%;
  margin: 0;
  color: #91a2ba;
  font-size: 0.8rem;
}
.history-delete-button:disabled,
.history-delete-all:disabled,
.history-export:disabled {
  opacity: 0.55;
  cursor: wait;
}
[data-history-entry][hidden] {
  display: none !important;
}
`;
}
