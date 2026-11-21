import test from "node:test";
import assert from "node:assert/strict";
import { applyFreeUnlimitedUi } from "../web/apply-free-unlimited.mjs";

test("account and post-scan counters are replaced by an unlimited free label", () => {
  const input = [
    "quota.textContent = data.premium ? 'Pro active' : '5 free scans';",
    "quota.textContent = payload.usage.premium ? 'Pro active' : '5 free scans';",
  ].join("\n");
  const output = applyFreeUnlimitedUi(input);
  assert.equal((output.match(/Free plan · unlimited scans/g) || []).length, 2);
  assert.equal(output.includes("Pro active"), false);
});

test("the Mini App patch is idempotent", () => {
  const input = [
    "quota.textContent = data.premium ? 'Pro active' : '5 free scans';",
    "quota.textContent = payload.usage.premium ? 'Pro active' : '5 free scans';",
  ].join("\n");
  const once = applyFreeUnlimitedUi(input);
  assert.equal(applyFreeUnlimitedUi(once), once);
});
