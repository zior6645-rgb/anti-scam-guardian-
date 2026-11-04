import { readFile, writeFile } from "node:fs/promises";

const mainPath = "src/main.js";
const cssPath = "src/style.css";
let main = await readFile(mainPath, "utf8");

const importAnchor = "import './style.css';";
const metadataImport = "import { appendResultMetadata } from './result-metadata.js';";
if (!main.includes(metadataImport)) {
  if (!main.includes(importAnchor)) {
    throw new Error("Could not find the main.js CSS import anchor");
  }
  main = main.replace(importAnchor, importAnchor + "\n" + metadataImport);
}

const appendAnchor = "  resultBox.append(title, subject, flagsTitle, list, provider, disclaimer);";
const appendCall = "  appendResultMetadata(resultBox, result);";
if (!main.includes(appendCall)) {
  if (!main.includes(appendAnchor)) {
    throw new Error("Could not find the renderResult() append anchor");
  }
  main = main.replace(appendAnchor, appendAnchor + "\n" + appendCall);
}
await writeFile(mainPath, main);

const css = await readFile(cssPath, "utf8");
const cssMarker = ".result-metadata";
if (!css.includes(cssMarker)) {
  const metadataStyles = `

.result-metadata {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #263b59;
}
.result-metadata h4 {
  margin: 0 0 9px;
  color: #c5d3e8;
  font-size: 13px;
}
.metadata-grid {
  display: grid;
  grid-template-columns: minmax(110px, .75fr) minmax(0, 1.25fr);
  gap: 8px 12px;
  margin: 0;
}
.metadata-grid dt {
  color: #91a2ba;
  font-size: 12px;
}
.metadata-grid dd {
  margin: 0;
  color: #e1ebf8;
  font-size: 12px;
  overflow-wrap: anywhere;
}
`;
  await writeFile(cssPath, css + metadataStyles);
}
console.log("Mini App metadata renderer patched successfully.");
