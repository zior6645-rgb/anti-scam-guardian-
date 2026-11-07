// Shared by initial account loading and post-scan usage updates.
export function formatQuota(data = {}) {
  const pro = data.premium === true;
  const used = data.scans_used_today ?? data.used_today;
  const limit = pro
    ? (data.pro_scans_per_day ?? data.pro_limit)
    : (data.free_scans_per_day ?? data.free_limit);
  const label = pro ? 'Pro' : 'Free';
  if (!Number.isSafeInteger(used) || used < 0 || !Number.isSafeInteger(limit) || limit < 0) {
    return `${label} plan · usage status unavailable`;
  }
  return `${label}: ${used}/${limit} scans today · ${Math.max(0, limit - used)} remaining · resets at 00:00 UTC`;
}
