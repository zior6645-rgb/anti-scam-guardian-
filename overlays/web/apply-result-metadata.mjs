import { readFile, writeFile } from "node:fs/promises";

const mainPath = "src/main.js";
const cssPath = "src/style.css";
let main = await readFile(mainPath, "utf8");

const importAnchor = "import './style.css';";
const metadataImport = "import { appendResultMetadata } from './result-metadata.js';";
const walletNoticeImport = "import { installWalletPolicyNotice } from './wallet-policy-note.js';";
if (!main.includes(metadataImport)) {
  if (!main.includes(importAnchor)) {
    throw new Error("Could not find the main.js CSS import anchor");
  }
  main = main.replace(importAnchor, importAnchor + "\n" + metadataImport);
}
if (!main.includes(walletNoticeImport)) {
  const currentMetadataImport = "import { appendResultMetadata } from './result-metadata.js';";
  if (!main.includes(currentMetadataImport)) {
    throw new Error("Could not find the result-metadata import anchor");
  }
  main = main.replace(currentMetadataImport, currentMetadataImport + "\n" + walletNoticeImport);
}
const walletInstallCall = "installWalletPolicyNotice();";
if (!main.includes(walletInstallCall)) {
  const currentWalletImport = "import { installWalletPolicyNotice } from './wallet-policy-note.js';";
  if (!main.includes(currentWalletImport)) {
    throw new Error("Could not find the wallet policy import anchor");
  }
  main = main.replace(currentWalletImport, currentWalletImport + "\n" + walletInstallCall);
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

const updatedCss = await readFile(cssPath, "utf8");
if (!updatedCss.includes(".wallet-policy-note")) {
  const policyStyles = `

.wallet-policy-note {
  margin: 0 0 16px;
  padding: 13px 14px;
  border: 1px solid #38516f;
  border-radius: 12px;
  background: #111d2e;
  color: #dce8f7;
  font-size: 13px;
  line-height: 1.5;
}
.wallet-policy-note strong {
  display: block;
  color: #f0f5fc;
  font-size: 13px;
}
.wallet-policy-note p {
  margin: 6px 0 0;
  color: #b8c8dc;
}
`;
  await writeFile(cssPath, updatedCss + policyStyles);
}
console.log("Mini App metadata renderer and wallet policy notice patched successfully.");
