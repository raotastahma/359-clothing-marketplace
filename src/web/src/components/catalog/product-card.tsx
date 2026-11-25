"use client";

import { Heart } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { memo } from "react";

import { Price } from "@/src/components/price";
import { isRemoteImageUrl } from "@/src/lib/utils";
import { BADGE_LABELS, type Product } from "@/src/types/product";

interface ProductCardProps {
  product: Product;
  compact?: boolean;
  isFav: boolean;
  onToggleFavorite: (productId: string, productApiId?: string, product?: Product) => void;
}

export const ProductCard = memo(function ProductCard({
  product,
  compact = false,
  isFav,
  onToggleFavorite,
}: ProductCardProps) {
  const hasSecondImage = product.images.length > 1;

  return (
    <div className="group relative">
      <Link href={`/product/${product.id}`} className="block">
        <div
          className={`relative overflow-hidden bg-[#f5f5f5] ${
            compact ? "aspect-[4/5]" : "aspect-[3/4]"
          }`}
        >
          <Image
            src={product.images[0]}
            alt={product.name}
            fill
            unoptimized={isRemoteImageUrl(product.images[0])}
            sizes="(min-width: 1280px) 25vw, (min-width: 768px) 33vw, 50vw"
            className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-300 ${
              hasSecondImage ? "group-hover:opacity-0" : ""
            }`}
          />
          {hasSecondImage && (
            <Image
              src={product.images[1]}
              alt={`${product.name} - alternate view`}
              fill
              unoptimized={isRemoteImageUrl(product.images[1])}
              sizes="(min-width: 1280px) 25vw, (min-width: 768px) 33vw, 50vw"
              className="absolute inset-0 h-full w-full object-cover opacity-0 transition-opacity duration-300 group-hover:opacity-100"
            />
          )}
          {product.badge && (
            <div className="absolute top-2 left-2 z-10">
              <span
                className={`px-2 py-0.5 text-[10px] ${
                  product.badge === "Sale"
                    ? "bg-black text-white"
                    : "border border-black/10 bg-white text-black"
                }`}
              >
                {BADGE_LABELS[product.badge] ?? product.badge}
              </span>
            </div>
          )}
        </div>
      </Link>

      <button
        onClick={() => onToggleFavorite(product.id, product.apiId, product)}
        className="absolute top-2 right-2 bg-white/80 p-1.5 backdrop-blur-sm transition-colors hover:bg-white"
        aria-label={isFav ? "Убрать из избранного" : "В избранное"}
      >
        <Heart size={16} className={isFav ? "fill-black text-black" : "text-black/60"} />
      </button>

      <div className="pt-2.5 pb-1">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-xs text-black/50">{product.brand}</p>
            <p className="mt-0.5 truncate text-sm">{product.name}</p>
          </div>
        </div>
        <div className="mt-1 flex items-center gap-2">
          <p className="text-sm">
            <Price amount={product.price} />
          </p>
          {product.originalPrice && (
            <p className="text-xs text-black/40">
              <Price amount={product.originalPrice} strikethrough />
            </p>
          )}
        </div>
      </div>
    </div>
  );
});
