export function applyFreeUnlimitedUi(source) {
  const lines = source.split(/\r?\n/);
  const markers = [
    "quota.textContent = data.premium ?",
    "quota.textContent = payload.usage.premium ?",
  ];

  for (const marker of markers) {
    const matches = lines.map((line, index) => ({line, index})).filter(item => item.line.includes(marker));
    if (matches.length === 0) continue;
    if (matches.length !== 1) throw new Error("Expected one quota source line for " + marker + ", found " + matches.length);
    lines[matches[0].index] = "    quota.textContent = 'Free plan · unlimited scans';";
  }

  const output = lines.join("\n");
  if (output.includes("Pro active") || output.includes("free scans today")) {
    throw new Error("Paid or capped scan label remains in Mini App source");
  }
  return output;
}
