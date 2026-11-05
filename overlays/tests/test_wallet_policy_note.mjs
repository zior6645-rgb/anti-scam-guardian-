import test from 'node:test';
import assert from 'node:assert/strict';
import { installWalletPolicyNotice } from '../web/src/wallet-policy-note.js';

function element(tagName) {
  return {
    tagName,
    className: '',
    textContent: '',
    children: [],
    attributes: {},
    setAttribute(name, value) { this.attributes[name] = value; },
    append(...nodes) { this.children.push(...nodes); },
    prepend(node) { this.children.unshift(node); },
  };
}

test('wallet notice explains that connection is not a crypto deposit or Pro checkout', () => {
  const mount = element('main');
  globalThis.document = {
    body: mount,
    querySelector: (selector) => selector === '#app' ? mount : null,
    createElement: element,
  };
  try {
    installWalletPolicyNotice();
    assert.equal(mount.children.length, 1);
    const notice = mount.children[0];
    assert.equal(notice.className, 'wallet-policy-note');
    const text = notice.children.map((child) => child.textContent).join(' ');
    assert.match(text, /optional/i);
    assert.match(text, /does not send a payment/i);
    assert.match(text, /does not accept TON or USDT deposits/i);
    assert.match(text, /Telegram Stars \(XTR\)/i);
    assert.doesNotMatch(text, /send your seed phrase/i);
  } finally {
    delete globalThis.document;
  }
});

test('wallet notice does not duplicate when installed twice', () => {
  const mount = element('main');
  globalThis.document = {
    body: mount,
    querySelector: () => mount,
    createElement: element,
  };
  try {
    installWalletPolicyNotice();
    installWalletPolicyNotice();
    assert.equal(mount.children.length, 1);
  } finally {
    delete globalThis.document;
  }
});
