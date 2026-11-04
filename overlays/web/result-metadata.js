function formatUnits(rawValue, decimalsValue) {
  if (rawValue === null || rawValue === undefined || rawValue === "") return "";
  const raw = String(rawValue).trim();
  if (!/^-?\d+$/.test(raw)) return raw;

  const decimals = Number(decimalsValue);
  if (!Number.isInteger(decimals) || decimals < 0 || decimals > 30) {
    return `${raw} base units`;
  }

  try {
    const value = BigInt(raw);
    const divisor = 10n ** BigInt(decimals);
    const whole = value / divisor;
    const remainder = value % divisor;
    if (decimals === 0 || remainder === 0n) return whole.toString();
    const fraction = remainder.toString().padStart(decimals, "0").replace(/0+$/, "");
    return `${whole.toString()}.${fraction}`;
  } catch {
    return raw;
  }
}

function formatNanoton(value) {
  return formatUnits(value, 9);
}

function formatLastActivity(value) {
  if (value === null || value === undefined || value === "") return "";
  const numeric = Number(value);
  if (Number.isFinite(numeric) && numeric > 1_000_000_000) {
    const date = new Date(numeric * 1000);
    if (!Number.isNaN(date.getTime())) return date.toLocaleString();
  }
  return String(value);
}

export function appendResultMetadata(root, result) {
  const entries = [];
  const add = (label, value) => {
    if (value === null || value === undefined || value === "") return;
    entries.push([label, String(value)]);
  };

  if (result.kind === "token") {
    add("Token name", result.token_name);
    add("Token symbol", result.token_symbol);
    add("Decimals", result.decimals);
    if (result.total_supply !== null && result.total_supply !== undefined && result.total_supply !== "") {
      const supply = formatUnits(result.total_supply, result.decimals);
      add("Total supply", result.token_symbol ? `${supply} ${result.token_symbol}` : supply);
    }
    if (typeof result.mintable === "boolean") add("Mintable", result.mintable ? "Yes" : "No");
    if (result.holders_count !== null && result.holders_count !== undefined) {
      const count = Number(result.holders_count);
      add("Holders", Number.isFinite(count) ? count.toLocaleString() : result.holders_count);
    }
    add("TONAPI verification", result.verification);
    if (typeof result.provider_is_scam === "boolean") {
      add("TONAPI scam indicator", result.provider_is_scam ? "Flagged by TONAPI" : "Not currently flagged by TONAPI");
    }
    if (result.description) add("Description", String(result.description).slice(0, 400));
  } else if (result.kind === "wallet") {
    add("Account status", result.account_status);
    add("Account name", result.account_name);
    if (result.balance_nanograms !== null && result.balance_nanograms !== undefined) {
      add("Balance (TON)", formatNanoton(result.balance_nanograms));
    }
    add("Last activity", formatLastActivity(result.last_activity));
    if (typeof result.account_is_wallet === "boolean") {
      add("Wallet account", result.account_is_wallet ? "Yes" : "No");
    }
    if (Array.isArray(result.account_interfaces) && result.account_interfaces.length) {
      add("Interfaces", result.account_interfaces.join(", "));
    }
    if (typeof result.provider_is_scam === "boolean") {
      add("TONAPI scam indicator", result.provider_is_scam ? "Flagged by TONAPI" : "Not currently flagged by TONAPI");
    }
  }

  if (!entries.length) return;

  const section = document.createElement("section");
  section.className = "result-metadata";
  const heading = document.createElement("h4");
  heading.textContent = "Additional public metadata";
  const definitionList = document.createElement("dl");
  definitionList.className = "metadata-grid";

  for (const [label, value] of entries) {
    const term = document.createElement("dt");
    term.textContent = label;
    const description = document.createElement("dd");
    description.textContent = value;
    definitionList.append(term, description);
  }

  section.append(heading, definitionList);
  root.append(section);
}
