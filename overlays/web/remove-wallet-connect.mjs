import { readFile, writeFile, unlink } from "node:fs/promises";
import { removeWalletConnectSources } from "./src/wallet-removal.js";

const targets = {
  main: new URL("./src/main.js", import.meta.url),
  html: new URL("./index.html", import.meta.url),
  css: new URL("./src/style.css", import.meta.url),
  packageJson: new URL("./package.json", import.meta.url),
};

const source = {};
for (const [key, path] of Object.entries(targets)) {
  source[key] = await readFile(path, "utf8");
}
const output = removeWalletConnectSources(source);

for (const [key, path] of Object.entries(targets)) {
  if (output[key] !== source[key]) {
    await writeFile(path, output[key], "utf8");
  }
}

await unlink(new URL("./src/wallet-policy-note.js", import.meta.url)).catch((error) => {
  if (error.code !== "ENOENT") throw error;
});

process.stdout.write("Removed TON Connect UI, SDK dependency and wallet manifest bootstrap\n");
