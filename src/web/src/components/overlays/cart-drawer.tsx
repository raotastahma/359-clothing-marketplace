"use client";

import { Minus, Plus, ShoppingBag, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/src/components/ui/button";
import { Price } from "@/src/components/price";
import { useCart, type CartItem } from "@/src/components/providers/cart-context";
import { useScrollLock } from "@/src/hooks/use-scroll-lock";
import { pluralize } from "@/src/lib/pluralize";

interface BrandGroup {
  brand: string;
  items: CartItem[];
}

function groupByBrand(items: CartItem[]): BrandGroup[] {
  const groups = new Map<string, CartItem[]>();

  items.forEach((item) => {
    const brandItems = groups.get(item.product.brand) ?? [];
    brandItems.push(item);
    groups.set(item.product.brand, brandItems);
  });

  return Array.from(groups, ([brand, brandItems]) => ({ brand, items: brandItems }));
}

function getProductImage(product: CartItem["product"]): string | undefined {
  return product.images[0];
}

export function CartDrawer() {
  const {
    cartItems,
    cartCount,
    cartTotal,
    isCartOpen,
    removeFromCart,
    setCartOpen,
    updateQuantity,
  } = useCart();
  const [wasOpen, setWasOpen] = useState<boolean>(false);
  const brandGroups = useMemo(() => groupByBrand(cartItems), [cartItems]);
  const brandNames = useMemo(() => brandGroups.map((group) => group.brand), [brandGroups]);

  useScrollLock(isCartOpen);

  useEffect(() => {
    if (!isCartOpen || wasOpen) return;

    const timer = window.setTimeout(() => setWasOpen(true), 0);
    return () => window.clearTimeout(timer);
  }, [isCartOpen, wasOpen]);

  useEffect(() => {
    if (!isCartOpen) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setCartOpen(false);
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isCartOpen, setCartOpen]);

  if (!wasOpen && !isCartOpen) return null;

  return (
    <div
      className={`fixed inset-0 z-50 transition ${
        isCartOpen ? "pointer-events-auto" : "pointer-events-none"
      }`}
      aria-hidden={!isCartOpen}
    >
      <button
        className={`absolute inset-0 bg-black/40 transition-opacity ${
          isCartOpen ? "opacity-100" : "opacity-0"
        }`}
        onClick={() => setCartOpen(false)}
        aria-label="Закрыть корзину"
      />
      <aside
        className={`absolute top-0 right-0 flex h-full w-full max-w-sm flex-col bg-white shadow-2xl transition-transform duration-300 ${
          isCartOpen ? "translate-x-0" : "translate-x-full"
        }`}
        role="dialog"
        aria-modal="true"
        aria-label="Корзина"
      >
        <div className="flex items-center justify-between border-b border-black/10 px-5 py-4">
          <h2 className="text-sm tracking-[2px] uppercase">
            Корзина ({cartCount})
          </h2>
          <button
            className="p-2 transition-opacity hover:opacity-60"
            onClick={() => setCartOpen(false)}
            aria-label="Закрыть"
          >
            <X size={18} strokeWidth={1.5} />
          </button>
        </div>

        {cartItems.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center px-8 text-center">
            <ShoppingBag size={42} strokeWidth={1.2} className="mb-5 text-black/35" />
            <p className="text-base font-medium">Корзина пуста</p>
            <Button asChild className="mt-6 w-full bg-black text-white">
              <Link href="/shop" onClick={() => setCartOpen(false)}>
                Продолжить покупки
              </Link>
            </Button>
          </div>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto px-5 py-5">
              <div className="space-y-7">
                {brandGroups.map((group) => (
                  <section key={group.brand} className="space-y-4">
                    <h3 className="text-[11px] tracking-[2px] text-black/45 uppercase">
                      {group.brand}
                    </h3>
                    <div className="space-y-5">
                      {group.items.map((item) => (
                        <article
                          key={`${item.product.id}-${item.size}`}
                          className="grid grid-cols-[5rem_1fr] gap-4 border-b border-black/10 pb-5"
                        >
                          <div
                            className="h-24 w-20 bg-black/5 bg-cover bg-center"
                            style={{
                              backgroundImage: getProductImage(item.product)
                                ? `url(${getProductImage(item.product)})`
                                : undefined,
                            }}
                            aria-label={item.product.name}
                          />
                          <div className="min-w-0">
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className="text-[11px] tracking-[1.5px] text-black/45 uppercase">
                                  {item.product.brand}
                                </p>
                                <p className="mt-1 text-sm leading-snug">{item.product.name}</p>
                                <p className="mt-1 text-xs text-black/50">Размер: {item.size}</p>
                              </div>
                              <Price
                                amount={item.product.price * item.quantity}
                                className="shrink-0 text-sm"
                              />
                            </div>

                            <div className="mt-4 flex items-center justify-between">
                              <div className="flex h-8 items-center border border-black/15">
                                <button
                                  className="flex h-8 w-8 items-center justify-center transition-colors hover:bg-black hover:text-white"
                                  onClick={() =>
                                    updateQuantity(
                                      item.product.id,
                                      item.size,
                                      item.quantity - 1,
                                    )
                                  }
                                  aria-label="Уменьшить количество"
                                >
                                  <Minus size={14} strokeWidth={1.5} />
                                </button>
                                <span className="w-8 text-center text-sm">{item.quantity}</span>
                                <button
                                  className="flex h-8 w-8 items-center justify-center transition-colors hover:bg-black hover:text-white"
                                  onClick={() =>
                                    updateQuantity(
                                      item.product.id,
                                      item.size,
                                      item.quantity + 1,
                                    )
                                  }
                                  aria-label="Увеличить количество"
                                >
                                  <Plus size={14} strokeWidth={1.5} />
                                </button>
                              </div>
                              <button
                                className="text-xs text-black/45 underline-offset-4 transition-colors hover:text-black hover:underline"
                                onClick={() => removeFromCart(item.product.id, item.size)}
                              >
                                Удалить
                              </button>
                            </div>
                          </div>
                        </article>
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            </div>

            <div className="space-y-4 border-t border-black/10 px-5 py-5">
              <div className="space-y-2 text-sm">
                <div>
                  <p className="text-xs tracking-[1.5px] text-black/45 uppercase">
                    Бренды в заказе
                  </p>
                  <p className="mt-1 text-sm">{brandNames.join(", ")}</p>
                </div>
                <div className="flex items-center justify-between">
                  <span>Доставка</span>
                  <span className="flex items-center gap-2">
                    <span className="bg-black px-2 py-0.5 text-[10px] tracking-[1px] text-white uppercase">
                      Бесплатно
                    </span>
                    <Price amount={0} />
                  </span>
                </div>
                <div className="flex items-center justify-between text-base font-medium">
                  <span>Итого</span>
                  <Price amount={cartTotal} />
                </div>
                <p className="text-xs text-black/45">
                  {pluralize(cartCount, "товар", "товара", "товаров")}
                </p>
              </div>
              <Button asChild className="h-12 w-full bg-black text-white">
                <Link href="/checkout" onClick={() => setCartOpen(false)}>
                  Оформить заказ
                </Link>
              </Button>
            </div>
          </>
        )}
      </aside>
    </div>
  );
}
