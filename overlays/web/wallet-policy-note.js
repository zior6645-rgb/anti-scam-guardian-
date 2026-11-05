export function installWalletPolicyNotice() {
  const mount = document.querySelector('#app') || document.body;
  if (!mount) return;

  const children = Array.from(mount.children || []);
  if (children.some((child) => child.className === 'wallet-policy-note')) return;

  const notice = document.createElement('aside');
  notice.className = 'wallet-policy-note';
  notice.setAttribute('role', 'note');

  const heading = document.createElement('strong');
  heading.textContent = 'Wallet connection is optional';

  const paragraph = document.createElement('p');
  paragraph.textContent =
    'Connecting a TON wallet does not send a payment or create a deposit balance. ' +
    'This Mini App does not accept TON or USDT deposits. Pro access, when billing is enabled, ' +
    'is purchased with Telegram Stars (XTR). Never share your recovery phrase or private key.';

  notice.append(heading, paragraph);
  mount.prepend(notice);
}
