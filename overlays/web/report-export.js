// Local-only export: no analytics, upload, or external report service.
export function reportText(result, scannedAt = '') {
  const r = result || {};
  return [
    'AntiScam Guardian — screening report',
    scannedAt ? `Scan recorded: ${scannedAt}` : 'Scan time: not supplied',
    `Subject: ${r.subject || r.address || r.token_name || 'Not supplied'}`,
    `Risk indicator: ${r.risk_level || 'unknown'}`,
    `Method: ${r.method || 'Not supplied'}`,
    '', 'Observed indicators:',
    ...(Array.isArray(r.flags) && r.flags.length ? r.flags.map(x => `- ${String(x)}`) : ['- No indicator returned; this is not proof of safety.']),
    '', 'Provider evidence:',
    `PhishTank: ${r.threat_intelligence?.status || 'Not supplied'}`,
    `TONAPI verification: ${r.verification || 'Not supplied'}`,
    '', 'Next steps:',
    '- Confirm the exact domain or contract using an independent official source.',
    '- Never share a recovery phrase or private key, or sign a transaction you do not understand.',
    '- Missing provider data is not a clean result. Stop if the source cannot be verified.',
    '', 'Limitations:',
    r.disclaimer || 'Limited automated indicators only; not a security audit or guarantee of safety.',
    'This is a local, unsigned report. It is not proof of authenticity or current safety.',
  ].join('\\n');
}

export function appendReportDownload(container, result, scannedAt = '') {
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'Download report (.txt)';
  button.addEventListener('click', async () => {
    const contents = reportText(result, scannedAt);
    const filename = 'antiscam-screening-report.txt';

    // Android browsers and embedded WebViews may block the HTML download attribute.
    // Offer the native share sheet with the File itself when supported; the user can
    // choose a local save destination without uploading the report to our server.
    if (typeof File !== 'undefined' && typeof navigator !== 'undefined'
      && typeof navigator.share === 'function' && typeof navigator.canShare === 'function') {
      const file = new File([contents], filename, { type: 'text/plain' });
      if (navigator.canShare({ files: [file] })) {
        try {
          await navigator.share({ files: [file], title: 'AntiScam Guardian report' });
          return;
        } catch (error) {
          // A user cancellation is intentional; do not unexpectedly start another flow.
          if (error?.name === 'AbortError') return;
          // Continue to the standard browser download if native sharing fails.
        }
      }
    }

    // Standard browser fallback. Keep the object URL alive long enough for Android
    // WebView download handlers to consume it instead of revoking it after 1 second.
    const url = URL.createObjectURL(new Blob([contents], { type: 'text/plain;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.rel = 'noopener';
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  });
  const note = document.createElement('p');
  note.className = 'muted';
  note.textContent = 'Generated on your device. If direct download is unavailable, use the share sheet to save the .txt file locally. Reports may contain private URLs or addresses; review before sharing.';
  container.append(button, note);
}
