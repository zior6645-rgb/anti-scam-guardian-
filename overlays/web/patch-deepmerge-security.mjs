import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const entry = require.resolve("deepmerge");
let packageRoot = path.dirname(entry);
while (packageRoot !== path.dirname(packageRoot)) {
  const manifest = path.join(packageRoot, "package.json");
  if (fs.existsSync(manifest)) {
    const parsed = JSON.parse(fs.readFileSync(manifest, "utf8"));
    if (parsed.name === "deepmerge") break;
  }
  packageRoot = path.dirname(packageRoot);
}
const manifestPath = path.join(packageRoot, "package.json");
if (!fs.existsSync(manifestPath)) throw new Error("Could not locate deepmerge package.json");
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
if (manifest.name !== "deepmerge") throw new Error("Resolved package is not deepmerge");

function versionTuple(value) {
  const match = /^(\d+)\.(\d+)\.(\d+)/.exec(value || "");
  return match ? match.slice(1).map(Number) : null;
}
function compareVersion(a, b) {
  for (let i = 0; i < 3; i++) {
    if (a[i] !== b[i]) return a[i] - b[i];
  }
  return 0;
}
const version = versionTuple(manifest.version);
if (!version) throw new Error("Unrecognized deepmerge version: " + manifest.version);
const vulnerable = compareVersion(version, [4, 2, 0]) >= 0 && compareVersion(version, [4, 3, 1]) <= 0;

const entryFiles = ["main", "module", "browser"]
  .map((field) => manifest[field])
  .filter((value) => typeof value === "string" && value.endsWith(".js"))
  .map((value) => path.resolve(packageRoot, value));
const candidates = new Set([...entryFiles, path.join(packageRoot, "index.js")]);
const dist = path.join(packageRoot, "dist");
function collectJavaScript(directory) {
  if (!fs.existsSync(directory)) return;
  for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
    const full = path.join(directory, item.name);
    if (item.isDirectory()) collectJavaScript(full);
    else if (item.isFile() && item.name.endsWith(".js")) candidates.add(full);
  }
}
collectJavaScript(dist);

if (vulnerable) {
  let patchedCount = 0;
  for (const file of candidates) {
    if (!fs.existsSync(file)) continue;
    const original = fs.readFileSync(file, "utf8");
    if (!original.includes("function propertyIsUnsafe") || !original.includes("function mergeObject")) continue;
    if (original.includes("function propertyIsForbidden")) {
      if (!original.includes("propertyIsForbidden(key) || propertyIsUnsafe(target, key)")) {
        throw new Error("deepmerge contains a partial or unexpected patch: " + file);
      }
      continue;
    }

    let source = original;
    const helperAnchor = "function propertyIsUnsafe(target, key) {";
    if (source.split(helperAnchor).length !== 2) {
      throw new Error("Unexpected propertyIsUnsafe implementation in " + file);
    }
    source = source.replace(
      helperAnchor,
      "function propertyIsForbidden(key) {\n\treturn key === '__proto__'\n}\n\n" + helperAnchor,
    );

    const targetLoop = /getKeys\(target\)\.forEach\(function\(key\)\s*\{/g;
    const targetMatches = [...source.matchAll(targetLoop)];
    if (targetMatches.length !== 1) throw new Error("Expected one target-copy loop in " + file);
    const targetIndex = targetMatches[0].index + targetMatches[0][0].length;
    source = source.slice(0, targetIndex) +
      "\n\t\t\tif (propertyIsForbidden(key)) {\n\t\t\t\treturn\n\t\t\t}" +
      source.slice(targetIndex);

    const sourceGuard = "if (propertyIsUnsafe(target, key)) {";
    if (source.split(sourceGuard).length !== 2) {
      throw new Error("Expected one source merge guard in " + file);
    }
    source = source.replace(sourceGuard, "if (propertyIsForbidden(key) || propertyIsUnsafe(target, key)) {");

    if (!source.includes("propertyIsForbidden(key) || propertyIsUnsafe(target, key)")) {
      throw new Error("Source key guard was not installed in " + file);
    }
    const targetCheck = /getKeys\(target\)\.forEach\(function\(key\)\s*\{\s*if \(propertyIsForbidden\(key\)\)/;
    if (!targetCheck.test(source)) throw new Error("Target key guard was not installed in " + file);

    fs.writeFileSync(file, source);
    patchedCount++;
  }
  if (patchedCount === 0) throw new Error("No deepmerge distribution files were patched");
}

for (const file of entryFiles) {
  if (!fs.existsSync(file)) throw new Error("Declared deepmerge entrypoint is missing: " + file);
  const source = fs.readFileSync(file, "utf8");
  if (vulnerable && !source.includes("function propertyIsForbidden")) {
    throw new Error("A declared deepmerge entrypoint remains unpatched: " + file);
  }
}
console.log(
  "DEEPMERGE_SECURITY_PATCH_OK version=" + manifest.version +
  " vulnerable_range=" + vulnerable +
  " package=" + path.relative(process.cwd(), packageRoot),
);
