import { buildScanReportText } from './result-metadata.js';

export function reportText(result, scannedAt = '') {
  return buildScanReportText(result, scannedAt || new Date())
    + '\n\nReport status: unsigned temporary export.';
}

export function appendReportDownload(container, result, scannedAt = '') {
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'Save report to Downloads (.txt)';
  const note = document.createElement('p');
  note.className = 'muted';
  note.setAttribute('role', 'status');
  note.setAttribute('aria-live', 'polite');
  note.textContent = 'The report is generated from this scan. To save it in the phone’s Downloads folder, it opens in your external browser. The temporary server copy expires after two minutes and is not sent to a third party.';

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
      // Telegram's native downloadFile API does not let the Mini App choose
      // Android's public Downloads directory. Open the attachment in the
      // external browser instead, so Android's browser download manager saves it.
      if (telegram && typeof telegram.openLink === 'function') {
        telegram.openLink(downloadUrl.href);
        note.textContent = 'The report was opened in your browser. Check the notification area or the Downloads folder. If asked, choose Download.';
        button.textContent = 'Opened in browser';
        return;
      }

      if (typeof File !== 'undefined' && typeof navigator.share === 'function'
        && typeof navigator.canShare === 'function') {
        const file = new File([contents], filename, { type: 'text/plain' });
        if (navigator.canShare({ files: [file] })) {
          await navigator.share({ files: [file], title: 'AntiScam Guardian report' });
          note.textContent = 'Choose Files or Save to device, then select Downloads.';
          button.textContent = 'Choose save location';
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
      note.textContent = 'The browser was asked to download the report. Check Downloads.';
      button.textContent = 'Download requested';
    } catch (error) {
      note.textContent = 'Download failed: ' + String(error?.message || error) + '. Use Copy scan report as a fallback.';
      button.textContent = 'Retry download';
    } finally {
      button.disabled = false;
    }
  });

  container.append(button, note);
}
