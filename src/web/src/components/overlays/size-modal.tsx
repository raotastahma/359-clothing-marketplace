"use client";

import { Heart, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Price } from "@/src/components/price";
import { useCart } from "@/src/components/providers/cart-context";
import { useUser } from "@/src/components/providers/user-context";
import { useScrollLock } from "@/src/hooks/use-scroll-lock";
import { cn } from "@/src/lib/utils";
import type { Product } from "@/src/types/product";

interface SizeModalProps {
  product: Product;
  open: boolean;
  onClose: () => void;
}

export function SizeModal({ product, open, onClose }: SizeModalProps) {
  const [selectedSize, setSelectedSize] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isAdding, setAdding] = useState(false);
  const { addToCart } = useCart();
  const { favorites, toggleFavorite } = useUser();
  const isFavorite = favorites.includes(product.id);

  useScrollLock(open);

  useEffect(() => {
    if (!open) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setSelectedSize("");
        onClose();
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  function handleClose() {
    setSelectedSize("");
    setError(null);
    onClose();
  }

  async function handleAddToCart() {
    if (!selectedSize) return;
    setAdding(true);
    setError(null);

    try {
      await addToCart(product, selectedSize);
      handleClose();
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : "Не удалось добавить товар в корзину.",
      );
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 md:hidden">
      <button
        className="absolute inset-0 bg-black/40"
        onClick={handleClose}
        aria-label="Закрыть выбор размера"
      />
      <div className="absolute right-0 bottom-0 left-0 flex justify-center">
        <div
          className="w-full max-w-lg border-t border-black/10 bg-white shadow-2xl"
          role="dialog"
          aria-modal="true"
          aria-label="Выберите размер"
        >
          <div className="flex justify-center pt-3 pb-1">
            <div className="h-1 w-10 bg-black/20" />
          </div>

          <div className="flex items-center justify-between border-b border-black/10 px-5 py-3">
            <span className="text-sm">Выберите размер</span>
            <button
              onClick={handleClose}
              className="p-1 transition-opacity hover:opacity-60"
              aria-label="Закрыть"
            >
              <X size={18} strokeWidth={1.5} />
            </button>
          </div>

          <div className="px-5 py-4">
            <div className="grid grid-cols-3 gap-2">
              {product.sizes.map((size) => {
                const isDisabled = !product.inStock;
                return (
                  <button
                    key={size}
                    onClick={() => setSelectedSize(size)}
                    disabled={isDisabled}
                    className={cn(
                      "h-12 border text-sm transition-colors",
                      selectedSize === size
                        ? "border-black bg-black text-white"
                        : "border-black/20 text-black hover:border-black",
                      isDisabled && "cursor-not-allowed opacity-30",
                    )}
                  >
                    {size}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="px-5 pb-6">
            <p className="mb-3 text-xs text-black/50">
              {selectedSize ? `Размер ${selectedSize} выбран` : <Price amount={product.price} />}
            </p>
            {error ? <p className="mb-3 text-xs text-destructive">{error}</p> : null}

            <div className="flex gap-2">
              <button
                onClick={() => toggleFavorite(product.id, product.apiId, product)}
                className={cn(
                  "flex h-12 w-12 shrink-0 items-center justify-center border transition-colors",
                  isFavorite ? "border-black bg-black" : "border-black/30 hover:border-black",
                )}
                aria-label={isFavorite ? "Убрать из избранного" : "В избранное"}
              >
                <Heart
                  size={18}
                  className={isFavorite ? "fill-white text-white" : "text-black"}
                />
              </button>

              <button
                onClick={handleAddToCart}
                disabled={!selectedSize || isAdding}
                className={cn(
                  "h-12 flex-1 bg-black text-[11px] tracking-[2.5px] text-white uppercase transition-colors",
                  (!selectedSize || isAdding) && "cursor-not-allowed bg-black/20 text-black/40",
                )}
              >
                {isAdding ? "Добавляем" : selectedSize ? "В корзину" : "Выберите размер"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
