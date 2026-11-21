export function removeWalletConnectSources({ main, html, css, packageJson }) {
  let nextMain = main
    .replace(/^import\s+\{\s*TonConnectUI\s*\}\s+from\s+['"]@tonconnect\/ui['"];\r?\n/m, "")
    .replace(/^import\s+\{\s*installWalletPolicyNotice\s*\}\s+from\s+['"]\.\/wallet-policy-note\.js['"];\r?\ninstallWalletPolicyNotice\(\);\r?\n/m, "")
    .replace(/^const walletStatus = document\.getElementById\(['"]wallet-status['"]\);\r?\n/m, "");

  nextMain = nextMain.replace(
    /function shortAddress\(address\) \{[\s\S]*?(?=\nfunction renderResult)/,
    "",
  );

  let nextCss = css
    .replace(/#ton-connect\s*\{[^}]*\}\s*/g, "")
    .replace(/\.wallet-policy-note(?:\s+strong|\s+p)?\s*\{[^}]*\}\s*/g, "");

  let nextHtml = html
    .replace(/^\s*<div id="ton-connect"><\/div>\r?\n/m, "")
    .replace(/^\s*<p id="wallet-status"[^>]*>[\s\S]*?<\/p>\r?\n/m, "");

  // Telegram's Android WebView can retain an old HTML document while its
  // hashed CSS asset has already been replaced by a new deployment. Embed
  // the exact production stylesheet in the document so the theme cannot
  // disappear when that external asset is stale or unavailable.
  const inlineTheme = `<style id="asg-inline-theme">\\n${nextCss}\\n</style>`;
  if (nextHtml.includes('<style id="asg-inline-theme">')) {
    nextHtml = nextHtml.replace(
      /<style id="asg-inline-theme">[\\s\\S]*?<\\/style>/,
      inlineTheme,
    );
  } else {
    if (!nextHtml.includes("</head>")) throw new Error("Could not locate the Mini App document head");
    nextHtml = nextHtml.replace("</head>", inlineTheme + "\\n</head>");
  }

  const parsedPackage = JSON.parse(packageJson);
  if (parsedPackage.dependencies) {
    delete parsedPackage.dependencies["@tonconnect/ui"];
    if (Object.keys(parsedPackage.dependencies).length === 0) {
      delete parsedPackage.dependencies;
    }
  }

  const checks = [
    [nextMain, /TonConnectUI|walletStatus|tonconnect-manifest|wallet-policy-note/i, "Mini App JavaScript"],
    [nextHtml, /ton-connect|wallet-status|connect wallet/i, "Mini App HTML"],
    [nextCss, /#ton-connect|wallet-policy-note/i, "Mini App CSS"],
    [JSON.stringify(parsedPackage), /@tonconnect\/ui/i, "Mini App dependencies"],
  ];
  for (const [source, pattern, label] of checks) {
    if (pattern.test(source)) throw new Error("TON Connect reference remains in " + label);
  }

  return {
    main: nextMain,
    html: nextHtml,
    css: nextCss,
    packageJson: JSON.stringify(parsedPackage, null, 2) + "\n",
  };
}
