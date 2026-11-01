export type ClassValue = string | false | null | undefined;

/** Join class names and drop the false branches. */
export function cx(...values: ClassValue[]): string {
  return values.filter(Boolean).join(" ");
}
