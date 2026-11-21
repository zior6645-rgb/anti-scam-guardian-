import { readFile, writeFile } from "node:fs/promises";
import { applyFreeUnlimitedUi } from "./src/free-unlimited.js";

const target = new URL("./src/main.js", import.meta.url);
const source = await readFile(target, "utf8");
const patched = applyFreeUnlimitedUi(source);
if (patched !== source) {
  await writeFile(target, patched, "utf8");
  process.stdout.write("PATCHED Mini App quota labels to free/unlimited\n");
} else {
  process.stdout.write("Mini App quota labels already free/unlimited\n");
}
