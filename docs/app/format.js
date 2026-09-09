// Shared formatting helpers (spec section 5.1).

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export function formatPeriod(period) {
  // period is "YYYYMM" as a string, per PPRS (spec section 6).
  if (!/^\d{6}$/.test(period)) return period;
  const year = period.slice(0, 4);
  const month = parseInt(period.slice(4, 6), 10);
  return `${MONTH_NAMES[month - 1]} ${year} (period ${period})`;
}

export function formatPeriodShort(period) {
  if (!/^\d{6}$/.test(period)) return period;
  const year = period.slice(0, 4);
  const month = parseInt(period.slice(4, 6), 10);
  return `${MONTH_NAMES[month - 1].slice(0, 3)} ${year}`;
}

export function formatBuiltAt(builtAt) {
  const date = new Date(builtAt);
  if (Number.isNaN(date.getTime())) return builtAt;
  return date.toISOString().replace("T", " ").replace(/\.\d+Z$/, " UTC");
}

// Must match etl/transform.py's slugify() exactly - same algorithm, same
// output, since the frontend needs to derive an operator's slug from its
// display name to fetch operators/{slug}.json (or look it up in the
// embedded operators.json index).
export function slugify(name) {
  return String(name ?? "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
