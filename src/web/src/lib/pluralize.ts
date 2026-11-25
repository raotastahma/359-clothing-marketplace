export function pluralize(
  count: number,
  one: string,
  few: string,
  many: string,
): string {
  if (count % 100 >= 11 && count % 100 <= 19) return `${count} ${many}`;
  if (count % 10 === 1) return `${count} ${one}`;
  if (count % 10 >= 2 && count % 10 <= 4) return `${count} ${few}`;
  return `${count} ${many}`;
}
