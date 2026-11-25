"use client";

import { Mail, Send, X } from "lucide-react";

import { useScrollLock } from "@/src/hooks/use-scroll-lock";
import { useContact } from "@/src/components/providers/contact-context";

export function ContactModal() {
  const { isContactOpen, setContactOpen } = useContact();
  useScrollLock(isContactOpen);

  if (!isContactOpen) return null;

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center bg-black/50 px-4">
      <button
        className="absolute inset-0"
        onClick={() => setContactOpen(false)}
        aria-label="Закрыть контакты"
      />
      <div
        className="relative w-full max-w-lg bg-white p-6 pb-8"
        role="dialog"
        aria-modal="true"
        aria-label="Связаться с нами"
      >
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-sm tracking-[2px] uppercase">Связаться с нами</h2>
          <button
            className="p-2 transition-opacity hover:opacity-60"
            onClick={() => setContactOpen(false)}
            aria-label="Закрыть"
          >
            <X size={18} />
          </button>
        </div>
        <div className="space-y-3">
          <a
            href="https://t.me/"
            className="flex items-center justify-between border border-black/10 p-4 transition-colors hover:bg-black hover:text-white"
            target="_blank"
            rel="noreferrer"
          >
            <span className="flex items-center gap-3">
              <Send size={18} strokeWidth={1.5} />
              Telegram
            </span>
            <span className="text-sm opacity-60">Telegram</span>
          </a>
          <a
            href="mailto:hello@example.invalid"
            className="flex items-center justify-between border border-black/10 p-4 transition-colors hover:bg-black hover:text-white"
          >
            <span className="flex items-center gap-3">
              <Mail size={18} strokeWidth={1.5} />
              Email
            </span>
            <span className="text-sm opacity-60">hello@example.invalid</span>
          </a>
        </div>
      </div>
    </div>
  );
}
