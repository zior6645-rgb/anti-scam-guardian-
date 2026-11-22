import { buildScanReportText } from './result-metadata.js';

export function reportText(result, scannedAt = '') {
  return buildScanReportText(result, scannedAt || new Date())
    + '\n\nReport status: unsigned temporary export.';
}

export function appendReportDownload(container, result, scannedAt = '') {
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'Download report (.txt)';
  const note = document.createElement('p');
  note.className = 'muted';
  note.setAttribute('role', 'status');
  note.setAttribute('aria-live', 'polite');
  note.textContent = 'The report is generated from this scan. A temporary copy is held on the bot server for up to two minutes to let Telegram download it; it is not sent to a third-party service.';

  button.addEventListener('click', async () => {
    if (button.disabled) return;
    button.disabled = true;
    button.textContent = 'Preparing report…';
    note.textContent = 'Preparing secure download…';
    const contents = reportText(result, scannedAt);
    const filename = 'antiscam-screening-report.txt';
    try {
      const response = await fetch('/api/reports', {
        method: 'POST',
        headers: { 'Content-Type': 'text/plain;charset=utf-8' },
        body: contents,
        cache: 'no-store',
        credentials: 'same-origin',
      });
      if (!response.ok) throw new Error('Report upload endpoint returned HTTP ' + response.status);
      const payload = await response.json();
      const downloadUrl = new URL(payload.url, window.location.href);
      if (downloadUrl.protocol !== 'https:' || downloadUrl.origin !== window.location.origin) {
        throw new Error('The temporary download URL was not a trusted HTTPS URL');
      }

      const telegram = window.Telegram?.WebApp;
      if (telegram && typeof telegram.downloadFile === 'function') {
        telegram.downloadFile({ url: downloadUrl.href, file_name: filename }, (accepted) => {
          note.textContent = accepted
            ? 'Telegram accepted the download request. Check your Downloads folder.'
            : 'Download cancelled in Telegram.';
        });
        button.textContent = 'Download requested';
        return;
      }

      if (typeof File !== 'undefined' && typeof navigator.share === 'function'
        && typeof navigator.canShare === 'function') {
        const file = new File([contents], filename, { type: 'text/plain' });
        if (navigator.canShare({ files: [file] })) {
          await navigator.share({ files: [file], title: 'AntiScam Guardian report' });
          note.textContent = 'Choose a local save destination in the share sheet.';
          button.textContent = 'Report shared';
          return;
        }
      }

      const blobUrl = URL.createObjectURL(new Blob([contents], { type: 'text/plain;charset=utf-8' }));
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = filename;
      link.rel = 'noopener';
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
      note.textContent = 'If the file did not appear, open this Mini App in an external browser and retry.';
      button.textContent = 'Download attempted';
    } catch (error) {
      note.textContent = 'Download failed: ' + String(error?.message || error) + '. Use Copy scan report as a fallback.';
      button.textContent = 'Retry download';
    } finally {
      button.disabled = false;
    }
  });

  container.append(button, note);
}
