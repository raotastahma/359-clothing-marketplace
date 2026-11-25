import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function isRemoteImageUrl(value: string): boolean {
  return /^https?:\/\//i.test(value);
}
