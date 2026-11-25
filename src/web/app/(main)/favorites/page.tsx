"use client";

import { Heart } from "lucide-react";
import Link from "next/link";

import { ProductCard } from "@/src/components/catalog/product-card";
import { Button } from "@/src/components/ui/button";
import { useUser } from "@/src/components/providers/user-context";

export default function FavoritesPage() {
  const {
    accountError,
    favoriteProducts,
    favorites,
    isAccountLoading,
    toggleFavorite,
  } = useUser();

  return (
    <section className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:py-14">
      <h1 className="text-3xl tracking-tight">Избранное</h1>

      {isAccountLoading ? (
        <div className="mx-auto flex min-h-[45vh] max-w-md flex-col items-center justify-center text-center">
          <p className="text-sm text-black/50">Загружаем избранное...</p>
        </div>
      ) : accountError && favoriteProducts.length === 0 ? (
        <div className="mx-auto flex min-h-[45vh] max-w-md flex-col items-center justify-center text-center">
          <Heart size={42} strokeWidth={1.2} className="mb-5 text-black/35" />
          <h2 className="text-xl">Не удалось загрузить избранное</h2>
          <p className="mt-3 text-sm text-black/50">{accountError}</p>
        </div>
      ) : favoriteProducts.length === 0 ? (
        <div className="mx-auto flex min-h-[45vh] max-w-md flex-col items-center justify-center text-center">
          <Heart size={42} strokeWidth={1.2} className="mb-5 text-black/35" />
          <h2 className="text-xl">В избранном пока ничего</h2>
          <Button asChild className="mt-6 h-12 w-full bg-black text-white">
            <Link href="/shop">Перейти в каталог</Link>
          </Button>
        </div>
      ) : (
        <div className="mt-8 grid grid-cols-2 gap-x-3 gap-y-8 md:grid-cols-3 lg:grid-cols-4">
          {favoriteProducts.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              isFav={favorites.includes(product.id)}
              onToggleFavorite={toggleFavorite}
            />
          ))}
        </div>
      )}
    </section>
  );
}
