import test from "node:test";
import assert from "node:assert/strict";
import { appendResultMetadata, buildScanReportText } from "../web/src/result-metadata.js";

function makeElement(tagName) {
  return {
    tagName,
    className: "",
    textContent: "",
    value: "",
    disabled: false,
    children: [],
    listeners: {},
    attributes: {},
    style: {},
    setAttribute(name, value) { this.attributes[name] = value; },
    append(...nodes) { this.children.push(...nodes); },
    addEventListener(name, handler) { this.listeners[name] = handler; },
    async click() { if (this.listeners.click) await this.listeners.click(); },
    select() {},
    remove() {},
  };
}

test("report clearly labels a no-obvious-flags result as not proof of safety", () => {
  const report = buildScanReportText({
    kind: "url",
    subject: "example.com",
    risk_level: "no_obvious_flags",
    flags: [],
    method: "local_heuristics",
    disclaimer: "Screening only.",
  }, new Date("2026-11-05T12:00:00.000Z"));

  assert.match(report, /No obvious flags detected — not proof of safety/);
  assert.match(report, /Target: example.com/);
  assert.match(report, /Scanned at \(UTC\): 2026-11-05T12:00:00.000Z/);
  assert.match(report, /Never share a seed phrase or private key/);
  assert.match(report, /Screening only\./);
});

test("report includes provider provenance and flags without claiming a clean audit", () => {
  const report = buildScanReportText({
    kind: "token",
    token_name: "Example",
    address: "EQexample",
    risk_level: "not_assessed",
    flags: ["Provider has not marked this token as a scam"],
    method: "tonapi_public_metadata",
    threat_intelligence: { provider: "TONAPI", status: "not_assessed" },
    provider_is_scam: false,
  });

  assert.match(report, /Not assessed as safe/);
  assert.match(report, /TONAPI — not_assessed/);
  assert.match(report, /Not currently flagged; this is not a safety guarantee/);
  assert.match(report, /Provider has not marked this token as a scam/);
});

test("copy report button is available even when a URL scan has no additional metadata", async () => {
  const root = makeElement("div");
  const copied = [];
  Object.defineProperty(globalThis, "document", {
    configurable: true,
    value: { createElement: makeElement, body: makeElement("body"), execCommand: () => false },
  });
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: { clipboard: { writeText: async (value) => copied.push(value) } },
  });

  try {
    appendResultMetadata(root, {
      kind: "url",
      subject: "example.com",
      risk_level: "caution",
      flags: ["Newly registered domain signal"],
    });
    assert.equal(root.children.length, 1);
    const section = root.children[0];
    const button = section.children.find((child) => child.tagName === "button");
    assert.ok(button);
    await button.click();
    assert.equal(button.textContent, "Report copied");
    assert.equal(copied.length, 1);
    assert.match(copied[0], /Newly registered domain signal/);
    assert.match(copied[0], /Caution — review these indicators/);
  } finally {
    delete globalThis.document;
    delete globalThis.navigator;
  }
});

test("untrusted provider metadata is assigned as text, never parsed as HTML", () => {
  const root = makeElement("div");
  Object.defineProperty(globalThis, "document", {
    configurable: true,
    value: { createElement: makeElement, body: makeElement("body"), execCommand: () => false },
  });
  try {
    appendResultMetadata(root, {
      kind: "token",
      token_name: "Example",
      description: "<img src=x onerror=alert(1)>",
    });
    const section = root.children[0];
    const definitionList = section.children.find((child) => child.tagName === "dl");
    assert.ok(definitionList);
    const values = definitionList.children.filter((_, index) => index % 2 === 1);
    assert.ok(values.some((node) => node.textContent === "<img src=x onerror=alert(1)>"));
    assert.ok(values.every((node) => !("innerHTML" in node)));
  } finally {
    delete globalThis.document;
  }
});
