import { readFile, writeFile } from "node:fs/promises";

const target = new URL("./src/main.js", import.meta.url);

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

const source = await readFile(target, "utf8");
const patched = applyFreeUnlimitedUi(source);
if (patched !== source) {
  await writeFile(target, patched, "utf8");
  process.stdout.write("PATCHED Mini App quota labels to free/unlimited\n");
} else {
  process.stdout.write("Mini App quota labels already free/unlimited\n");
}
