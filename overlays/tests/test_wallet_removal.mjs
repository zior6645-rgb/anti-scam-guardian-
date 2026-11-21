import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { removeWalletConnectSources } from "../web/src/wallet-removal.js";

const root = new URL("../web/", import.meta.url);
const input = {
  main: await readFile(new URL("src/main.js", root), "utf8"),
  html: await readFile(new URL("index.html", root), "utf8"),
  css: await readFile(new URL("src/style.css", root), "utf8"),
  packageJson: await readFile(new URL("package.json", root), "utf8"),
};

test("TON Connect bootstrap, button, status and SDK dependency are removed", () => {
  const output = removeWalletConnectSources(input);
  assert.doesNotMatch(output.main, /TonConnectUI|walletStatus|tonconnect-manifest|wallet-policy-note/i);
  assert.doesNotMatch(output.html, /ton-connect|wallet-status|connect wallet/i);
  assert.match(output.html, /<style id="asg-inline-theme">/);
  assert.match(output.html, /\.shell\s*\{/);
  assert.match(output.html, /\.panel\s*\{/);
  assert.match(output.html, /\.brand-mark\s*\{/);
  assert.match(output.html, /background:\s*radial-gradient/);
  assert.doesNotMatch(output.css, /#ton-connect|wallet-policy-note/i);
  assert.equal(JSON.parse(output.packageJson).dependencies?.["@tonconnect/ui"], undefined);
});

test("manual TON wallet address scanning remains available without wallet connection", () => {
  const output = removeWalletConnectSources(input);
  assert.match(output.html, /<option value="wallet">TON wallet address<\/option>/);
  assert.match(output.html, /id="value"/);
  assert.match(output.main, /\/api\/scan/);
});

test("wallet removal transformation is idempotent", () => {
  const once = removeWalletConnectSources(input);
  const twice = removeWalletConnectSources(once);
  assert.deepEqual(twice, once);
});
