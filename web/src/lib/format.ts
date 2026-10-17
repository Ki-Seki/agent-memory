export const DAY = 864e5;
const sameYear = (d: Date) => d.getFullYear() === new Date().getFullYear();

/** 12 Oct, or 12 Oct 2025 outside this year. */
export function day(iso: string | undefined): string {
  const t = Date.parse(iso || "");
  if (!t) return "";
  const d = new Date(t);
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: sameYear(d) ? undefined : "numeric" });
}
export function longDay(iso: string | undefined): string {
  const t = Date.parse(iso || "");
  return t ? new Date(t).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "";
}
export const plural = (n: number, one: string, many = one + "s") => `${n} ${n === 1 ? one : many}`;
/** YYYY-MM-DD in local time. */
export function ymd(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
export const localDay = (iso: string) => { const t = Date.parse(iso || ""); return t ? ymd(new Date(t)) : ""; };
/** A place key shown short: its last folder. */
export const placeShort = (key: string) => key.split("/").filter(Boolean).pop() || key;
