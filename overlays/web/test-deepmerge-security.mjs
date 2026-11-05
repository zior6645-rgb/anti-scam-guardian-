import assert from "node:assert/strict";
import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import fs from "node:fs";

const require = createRequire(import.meta.url);
const resolved = require.resolve("deepmerge");
let root = path.dirname(resolved);
while (root !== path.dirname(root)) {
  const manifestPath = path.join(root, "package.json");
  if (fs.existsSync(manifestPath) && JSON.parse(fs.readFileSync(manifestPath, "utf8")).name === "deepmerge") break;
  root = path.dirname(root);
}
const manifest = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
const entrypoints = [...new Set(["main", "module", "browser"]
  .map((field) => manifest[field])
  .filter((value) => typeof value === "string" && value.endsWith(".js"))
  .map((value) => path.resolve(root, value)))];

if (!entrypoints.includes(path.resolve(resolved))) entrypoints.unshift(path.resolve(resolved));
for (const file of entrypoints) {
  let merge;
  if (file === path.resolve(manifest.module || "")) {
    const imported = await import(pathToFileURL(file).href);
    merge = imported.default || imported;
  } else {
    const loaded = require(file);
    merge = loaded.default || loaded;
  }
  assert.equal(typeof merge, "function", "deepmerge entrypoint must export a function: " + file);

  const malicious = JSON.parse('{"__proto__":{"isAdmin":true}}');
  const fromNullPrototype = merge(Object.create(null), malicious);
  assert.equal(Object.getPrototypeOf(fromNullPrototype), Object.prototype);
  assert.equal(fromNullPrototype.isAdmin, undefined);

  const nested = merge({ session: null }, JSON.parse('{"session":{"__proto__":{"isAdmin":true}}}'));
  assert.equal(Object.getPrototypeOf(nested.session), Object.prototype);
  assert.equal(nested.session.isAdmin, undefined);

  const targetOwnProto = JSON.parse('{"__proto__":{"isAdmin":true}}');
  const fromTarget = merge(targetOwnProto, { safe: true });
  assert.equal(Object.getPrototypeOf(fromTarget), Object.prototype);
  assert.equal(fromTarget.isAdmin, undefined);
  assert.equal(fromTarget.safe, true);

  const arrayClone = merge({}, { items: [malicious] });
  assert.equal(Object.getPrototypeOf(arrayClone.items[0]), Object.prototype);
  assert.equal(arrayClone.items[0].isAdmin, undefined);
  assert.equal(Object.prototype.isAdmin, undefined);
}
console.log("DEEPMERGE_PROTOTYPE_POISONING_REGRESSION_OK entrypoints=" + entrypoints.length);
