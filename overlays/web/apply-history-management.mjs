import { readFile, writeFile } from "node:fs/promises";
import { applyHistoryManagement, applyHistoryStyles } from "./src/history-management.js";

const mainPath = new URL("./src/main.js", import.meta.url);
const stylePath = new URL("./src/style.css", import.meta.url);
const mainSource = await readFile(mainPath, "utf8");
const styleSource = await readFile(stylePath, "utf8");
const patchedMain = applyHistoryManagement(mainSource);
const patchedStyle = applyHistoryStyles(styleSource);

if (patchedMain !== mainSource) {
  await writeFile(mainPath, patchedMain, "utf8");
  process.stdout.write("PATCHED Mini App individual and bulk history deletion controls\n");
} else {
  process.stdout.write("Mini App history deletion controls already present\n");
}
if (patchedStyle !== styleSource) {
  await writeFile(stylePath, patchedStyle, "utf8");
}
