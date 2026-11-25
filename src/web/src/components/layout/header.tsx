"use client";

import { Heart, Menu, ShoppingBag, User, X } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { useCart } from "@/src/components/providers/cart-context";
import { useUser } from "@/src/components/providers/user-context";

const NAV_LINKS = [
  { label: "Женское", href: "/shop?gender=Women", gender: "Women" },
  { label: "Мужское", href: "/shop?gender=Men", gender: "Men" },
] as const;

interface HeaderIconsProps {
  favCount: number;
  cartCount: number;
  onCartOpen: () => void;
}

function HeaderIcons({ favCount, cartCount, onCartOpen }: HeaderIconsProps) {
  return (
    <div className="flex items-center gap-1">
      <Link
        href="/favorites"
        className="relative p-2 transition-opacity hover:opacity-60"
        aria-label="Избранное"
      >
        <Heart size={18} strokeWidth={1.5} />
        {favCount > 0 ? (
          <span className="absolute top-1 right-1 flex h-3.5 w-3.5 items-center justify-center bg-black text-[9px] text-white">
            {favCount}
          </span>
        ) : null}
      </Link>

      <button
        onClick={onCartOpen}
        className="relative p-2 transition-opacity hover:opacity-60"
        aria-label="Корзина"
      >
        <ShoppingBag size={18} strokeWidth={1.5} />
        {cartCount > 0 ? (
          <span className="absolute top-1 right-1 flex h-3.5 w-3.5 items-center justify-center bg-black text-[9px] text-white">
            {cartCount}
          </span>
        ) : null}
      </button>

      <Link
        href="/profile"
        className="p-2 transition-opacity hover:opacity-60"
        aria-label="Профиль"
      >
        <User size={18} strokeWidth={1.5} />
      </Link>
    </div>
  );
}

function Logo() {
  const [hasLogoError, setHasLogoError] = useState<boolean>(false);

  if (hasLogoError) return <span className="text-xl tracking-[6px]">359</span>;

  return (
    <Image
      src="/logo.svg"
      alt="359"
      width={74}
      height={28}
      className="h-7 w-auto"
      onError={() => setHasLogoError(true)}
      priority
    />
  );
}

export function Header() {
  const { cartCount, setCartOpen } = useCart();
  const { favorites } = useUser();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState<boolean>(false);

  const currentGender = useMemo(
    () => (pathname === "/shop" ? searchParams.get("gender") : null),
    [pathname, searchParams],
  );

  return (
    <header className="fixed top-0 right-0 left-0 z-50 border-b border-black/10 bg-white">
      <div className="relative hidden h-14 items-center px-6 md:flex">
        <nav className="flex items-center gap-8">
          {NAV_LINKS.map(({ label, href, gender }) => (
            <Link
              key={label}
              href={href}
              className={`text-[11px] tracking-[2.5px] uppercase transition-colors ${
                currentGender === gender ? "text-black" : "text-black/50 hover:text-black"
              }`}
              style={{ fontWeight: 500 }}
            >
              {label}
            </Link>
          ))}
        </nav>

        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
          <Link href="/" className="flex-shrink-0">
            <Logo />
          </Link>
        </div>

        <div className="ml-auto">
          <HeaderIcons
            favCount={favorites.length}
            cartCount={cartCount}
            onCartOpen={() => setCartOpen(true)}
          />
        </div>
      </div>

      <div className="relative flex h-14 items-center px-4 md:hidden">
        <button
          className="p-2 transition-opacity hover:opacity-60"
          onClick={() => setIsMobileMenuOpen((prev) => !prev)}
          aria-label="Меню"
        >
          {isMobileMenuOpen ? (
            <X size={20} strokeWidth={1.5} />
          ) : (
            <Menu size={20} strokeWidth={1.5} />
          )}
        </button>

        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
          <Link href="/">
            <Logo />
          </Link>
        </div>

        <div className="ml-auto">
          <HeaderIcons
            favCount={favorites.length}
            cartCount={cartCount}
            onCartOpen={() => setCartOpen(true)}
          />
        </div>
      </div>

      {isMobileMenuOpen ? (
        <div className="border-t border-black/10 bg-white md:hidden">
          <nav className="flex flex-col gap-4 px-6 py-4">
            {NAV_LINKS.map(({ label, href }) => (
              <Link
                key={label}
                href={href}
                onClick={() => setIsMobileMenuOpen(false)}
                className="py-1 text-[11px] tracking-[2.5px] uppercase text-black/60 transition-colors hover:text-black"
                style={{ fontWeight: 500 }}
              >
                {label}
              </Link>
            ))}
          </nav>
        </div>
      ) : null}
    </header>
  );
}
