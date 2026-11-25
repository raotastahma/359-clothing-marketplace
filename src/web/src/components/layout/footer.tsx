"use client";

import { ArrowRight, Facebook, Instagram, Twitter, Youtube } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

function TikTokIcon({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-2.88 2.5 2.89 2.89 0 0 1-2.89-2.89 2.89 2.89 0 0 1 2.89-2.89c.28 0 .54.04.79.1V9.01a6.33 6.33 0 0 0-.79-.05 6.34 6.34 0 0 0-6.34 6.34 6.34 6.34 0 0 0 6.34 6.34 6.34 6.34 0 0 0 6.33-6.34V8.75a8.18 8.18 0 0 0 4.78 1.52V6.82a4.85 4.85 0 0 1-1.01-.13z" />
    </svg>
  );
}

const FOOTER_LINKS = {
  КАТАЛОГ: [
    { label: "Женское", href: "/shop?gender=Women" },
    { label: "Мужское", href: "/shop?gender=Men" },
    { label: "Новинки", href: "/shop?badge=New" },
    { label: "Sale", href: "/shop?badge=Sale" },
    { label: "Все товары", href: "/shop" },
  ],
  ДИЗАЙНЕРЫ: [
    { label: "Stone Island", href: "/shop" },
    { label: "Off-White", href: "/shop" },
    { label: "Moncler", href: "/shop" },
    { label: "Represent", href: "/shop" },
    { label: "Amiri", href: "/shop" },
    { label: "Palm Angels", href: "/shop" },
  ],
  КОМПАНИЯ: [
    { label: "О нас", href: "#" },
    { label: "Карьера", href: "#" },
    { label: "Пресса", href: "#" },
    { label: "Устойчивое развитие", href: "#" },
    { label: "Наши магазины", href: "#" },
  ],
  ПОМОЩЬ: [
    { label: "Вопросы и ответы", href: "#" },
    { label: "Доставка и возврат", href: "#" },
    { label: "Связаться с нами", href: "#" },
    { label: "Размерная таблица", href: "#" },
    { label: "Отследить заказ", href: "#" },
  ],
  ПРАВОВОЕ: [
    { label: "Политика конфиденциальности", href: "#" },
    { label: "Условия использования", href: "#" },
    { label: "Политика cookies", href: "#" },
    { label: "Доступность", href: "#" },
  ],
} as const;

const SOCIAL_LINKS = [
  { label: "Instagram", href: "#", Icon: Instagram },
  { label: "TikTok", href: "#", Icon: TikTokIcon },
  { label: "Twitter / X", href: "#", Icon: Twitter },
  { label: "YouTube", href: "#", Icon: Youtube },
  { label: "Facebook", href: "#", Icon: Facebook },
] as const;

export function Footer() {
  const [email, setEmail] = useState<string>("");
  const [subscribed, setSubscribed] = useState<boolean>(false);
  const [hasLogoError, setHasLogoError] = useState<boolean>(false);

  return (
    <footer className="bg-black text-white">
      <div className="border-b border-white/10">
        <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-6 px-6 py-12 md:flex-row md:items-center md:px-10">
          <div>
            <h3 className="mb-1 text-white" style={{ fontSize: "20px", fontWeight: 400 }}>
              Будьте в курсе
            </h3>
            <p className="text-[12px] tracking-wide text-white/50">
              Узнавайте первыми о новых коллекциях, эксклюзивных дропах и закрытых распродажах.
            </p>
          </div>

          {subscribed ? (
            <p className="text-[12px] tracking-[1px] uppercase text-white/60">Спасибо за подписку.</p>
          ) : (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                if (!email.trim()) return;
                setSubscribed(true);
                setEmail("");
              }}
              className="flex w-full items-stretch md:w-auto"
            >
              <input
                type="email"
                required
                placeholder="Введите email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="flex-1 border border-white/30 bg-transparent px-4 py-3 text-[12px] text-white placeholder:text-white/30 focus:border-white/60 focus:outline-none md:w-72"
              />
              <button
                type="submit"
                className="flex items-center gap-2 whitespace-nowrap bg-white px-5 py-3 text-[11px] tracking-[1.5px] text-black uppercase transition-colors hover:bg-white/90"
              >
                Подписаться <ArrowRight size={12} />
              </button>
            </form>
          )}
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-6 py-12 md:px-10">
        <div className="mb-12 grid grid-cols-2 gap-8 md:grid-cols-3 lg:grid-cols-6">
          <div className="col-span-2 md:col-span-3 lg:col-span-1">
            <Link href="/" className="mb-6 inline-block">
              {hasLogoError ? (
                <span className="text-xl tracking-[6px]">359</span>
              ) : (
                <Image
                  src="/logo-white.svg"
                  alt="359"
                  width={85}
                  height={32}
                  className="h-8 w-auto"
                  onError={() => setHasLogoError(true)}
                />
              )}
            </Link>
            <p className="mb-6 max-w-[180px] text-[11px] leading-relaxed text-white/40">
              Гардеробные основы премиум-класса для настоящих ценителей.
            </p>
            <div className="flex flex-wrap gap-4">
              {SOCIAL_LINKS.map(({ label, href, Icon }) => (
                <a
                  key={label}
                  href={href}
                  aria-label={label}
                  className="text-white/40 transition-colors hover:text-white"
                >
                  <Icon size={17} />
                </a>
              ))}
            </div>
          </div>

          {Object.entries(FOOTER_LINKS).map(([section, links]) => (
            <div key={section}>
              <p className="mb-4 text-[10px] tracking-[2px] text-white/40 uppercase">{section}</p>
              <ul className="space-y-2.5">
                {links.map(({ label, href }) => (
                  <li key={label}>
                    <Link href={href} className="text-[12px] text-white/60 transition-colors hover:text-white">
                      {label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="flex flex-col items-center justify-between gap-4 border-t border-white/10 pt-6 sm:flex-row">
          <p className="text-[11px] text-white/30">
            © {new Date().getFullYear()} 359 Clothing. Все права защищены.
          </p>
          <div className="flex items-center gap-6">
            <Link href="#" className="text-[11px] text-white/30 transition-colors hover:text-white/60">
              Конфиденциальность
            </Link>
            <Link href="#" className="text-[11px] text-white/30 transition-colors hover:text-white/60">
              Условия
            </Link>
            <Link href="#" className="text-[11px] text-white/30 transition-colors hover:text-white/60">
              Cookies
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
