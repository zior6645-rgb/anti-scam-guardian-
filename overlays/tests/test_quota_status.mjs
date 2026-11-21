import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(new URL("../web/src/quota-status.js", import.meta.url), "utf8");
const { formatQuota } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));

test("every account sees the same free unlimited allowance", () => {
  assert.equal(formatQuota({premium: false, scans_used_today: 3, free_scans_per_day: 5}), "Free plan · unlimited scans");
  assert.equal(formatQuota({premium: true, scans_used_today: 900, pro_scans_per_day: 100}), "Free plan · unlimited scans");
  assert.equal(formatQuota({}), "Free plan · unlimited scans");
});
