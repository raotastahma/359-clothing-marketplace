"use client";

import { Heart, Share2 } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { use, useEffect, useMemo, useRef, useState } from "react";

import { ProductCard } from "@/src/components/catalog/product-card";
import { SizeModal } from "@/src/components/overlays/size-modal";
import { Price } from "@/src/components/price";
import { useCart } from "@/src/components/providers/cart-context";
import { useUser } from "@/src/components/providers/user-context";
import {
  requestJson,
  type ProductApiResponse,
  type ProductsApiResponse,
} from "@/src/lib/api";
import {
  productDetailToUiProduct,
  productListItemToUiProduct,
} from "@/src/lib/product-adapter";
import { cn, isRemoteImageUrl } from "@/src/lib/utils";
import { BADGE_LABELS, CATEGORY_LABELS, type Product } from "@/src/types/product";

interface ProductPageProps {
  params: Promise<{ id: string }>;
}

type ProductTab = "description" | "details";

export default function ProductPage({ params }: ProductPageProps) {
  const { id } = use(params);
  const { addToCart } = useCart();
  const { addToRecentlyViewed, favorites, recentlyViewed, toggleFavorite } = useUser();
  const [activeImageState, setActiveImageState] = useState({ productId: "", index: 0 });
  const [selectedSizeState, setSelectedSizeState] = useState({ productId: "", value: "" });
  const [activeTab, setActiveTab] = useState<ProductTab>("description");
  const [isSizeModalOpen, setSizeModalOpen] = useState(false);
  const [addedState, setAddedState] = useState({ productId: "", value: false });
  const [product, setProduct] = useState<Product | null>(null);
  const [relatedProducts, setRelatedProducts] = useState<Product[]>([]);
  const [isLoading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cartError, setCartError] = useState<string | null>(null);
  const [isAdding, setAdding] = useState(false);
  const feedbackTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let isMounted = true;

    setLoading(true);
    setError(null);
    setProduct(null);
    setRelatedProducts([]);

    requestJson<ProductApiResponse>(`/products/${encodeURIComponent(id)}`, {
      redirectOnUnauthorized: false,
    })
      .then(async ({ data }) => {
        const nextProduct = productDetailToUiProduct(data);
        if (!isMounted) return;

        setProduct(nextProduct);
        addToRecentlyViewed(nextProduct);

        const related = await requestJson<ProductsApiResponse>(
          `/products?category=${encodeURIComponent(data.category.slug)}&per_page=8`,
          { redirectOnUnauthorized: false },
        );
        if (isMounted) {
          setRelatedProducts(
            related.data
              .map(productListItemToUiProduct)
              .filter((item) => item.id !== nextProduct.id)
              .slice(0, 8),
          );
        }
      })
      .catch((nextError: unknown) => {
        if (!isMounted) return;
        setError(
          nextError instanceof Error
            ? nextError.message
            : "Не удалось загрузить товар. Попробуйте ещё раз.",
        );
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [addToRecentlyViewed, id]);

  useEffect(() => {
    return () => {
      if (feedbackTimer.current) clearTimeout(feedbackTimer.current);
    };
  }, []);

  const otherRecentlyViewed = useMemo(() => {
    if (!product) return [];
    return recentlyViewed.filter((item) => item.id !== product.id).slice(0, 6);
  }, [product, recentlyViewed]);

  if (isLoading) {
    return (
      <section className="mx-auto grid max-w-screen-xl gap-8 px-4 py-8 md:px-8 lg:grid-cols-2 lg:px-10">
        <div className="aspect-[4/5] animate-pulse bg-black/5" />
        <div className="space-y-5">
          <div className="h-4 w-28 animate-pulse bg-black/10" />
          <div className="h-7 w-60 animate-pulse bg-black/10" />
          <div className="h-6 w-32 animate-pulse bg-black/10" />
          <div className="h-12 w-full animate-pulse bg-black/10" />
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center px-6 py-20 text-center">
        <h1 className="text-xl">Товар не найден</h1>
        <p className="mt-3 text-sm text-black/50">{error}</p>
        <Link href="/shop" className="mt-5 text-sm underline underline-offset-4">
          В каталог
        </Link>
      </section>
    );
  }

  if (!product) {
    return (
      <section className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center px-6 py-20 text-center">
        <h1 className="text-xl">Товар не найден</h1>
        <p className="mt-3 text-sm text-black/50">Проверьте ссылку или вернитесь в каталог.</p>
        <Link href="/shop" className="mt-5 text-sm underline underline-offset-4">
          В каталог
        </Link>
      </section>
    );
  }

  const currentProduct = product;
  const activeImage = activeImageState.productId === currentProduct.id ? activeImageState.index : 0;
  const selectedSize =
    selectedSizeState.productId === currentProduct.id ? selectedSizeState.value : "";
  const isAdded = addedState.productId === currentProduct.id && addedState.value;
  const isFavorite = favorites.includes(currentProduct.id);
  const activeImageSrc = currentProduct.images[activeImage] ?? currentProduct.images[0];
  const categoryLabel = CATEGORY_LABELS[currentProduct.category] ?? currentProduct.category;
  const subcategoryLabel =
    CATEGORY_LABELS[currentProduct.subcategory] ?? currentProduct.subcategory;
  const detailRows = [
    currentProduct.material ? ["Состав", currentProduct.material] : null,
    currentProduct.careInstructions ? ["Уход", currentProduct.careInstructions] : null,
    currentProduct.season ? ["Сезон", currentProduct.season] : null,
    ["Категория", subcategoryLabel],
  ].filter(Boolean) as [string, string][];

  function handleSizeSelect(size: string) {
    if (!currentProduct.inStock) return;
    setSelectedSizeState({ productId: currentProduct.id, value: size });
    setCartError(null);
  }

  async function handleAddToCart() {
    if (!selectedSize) {
      setSizeModalOpen(true);
      return;
    }

    setAdding(true);
    setCartError(null);

    try {
      await addToCart(currentProduct, selectedSize);
      setAddedState({ productId: currentProduct.id, value: true });
      if (feedbackTimer.current) clearTimeout(feedbackTimer.current);
      feedbackTimer.current = setTimeout(
        () => setAddedState({ productId: currentProduct.id, value: false }),
        2000,
      );
    } catch (nextError) {
      setCartError(
        nextError instanceof Error
          ? nextError.message
          : "Не удалось добавить товар в корзину.",
      );
    } finally {
      setAdding(false);
    }
  }

  async function handleShare() {
    const shareData = {
      title: `${currentProduct.brand} - ${currentProduct.name}`,
      url: window.location.href,
    };

    try {
      if (navigator.share) {
        await navigator.share(shareData);
      } else {
        await navigator.clipboard.writeText(shareData.url);
      }
    } catch {
      // Sharing can be cancelled by the user.
    }
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="border-b border-black/10 px-4 py-3 md:px-8 lg:px-10">
        <nav className="flex items-center gap-2 text-xs text-black/40" aria-label="Breadcrumbs">
          <Link href="/" className="transition-colors hover:text-black">
            Главная
          </Link>
          <span>/</span>
          <Link
            href={`/shop?category=${encodeURIComponent(currentProduct.category)}`}
            className="transition-colors hover:text-black"
          >
            {categoryLabel}
          </Link>
          <span>/</span>
          <span className="text-black/70">{currentProduct.name}</span>
        </nav>
      </div>

      <div className="mx-auto max-w-screen-xl px-4 py-6 md:px-8 md:py-8 lg:px-10">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-2 xl:gap-16">
          <section aria-label="Изображения товара">
            <div className="md:hidden">
              <div className="flex snap-x gap-3 overflow-x-auto">
                {currentProduct.images.map((image, index) => (
                  <div
                    key={image}
                    className="relative aspect-[4/5] w-[84vw] shrink-0 snap-center overflow-hidden bg-[#f5f5f5]"
                  >
                    <Image
                      src={image}
                      alt={`${currentProduct.name}, фото ${index + 1}`}
                      fill
                      unoptimized={isRemoteImageUrl(image)}
                      sizes="84vw"
                      className="object-cover"
                      priority={index === 0}
                    />
                  </div>
                ))}
              </div>
            </div>

            <div className="hidden grid-cols-[5rem_1fr] gap-3 md:grid">
              <div className="flex flex-col gap-2">
                {currentProduct.images.map((image, index) => (
                  <button
                    key={image}
                    onClick={() =>
                      setActiveImageState({ productId: currentProduct.id, index })
                    }
                    className={cn(
                      "relative aspect-[4/5] overflow-hidden border-b-2 bg-[#f5f5f5] transition-colors",
                      activeImage === index
                        ? "border-black"
                        : "border-transparent hover:border-black/30",
                    )}
                    aria-label={`Показать фото ${index + 1}`}
                  >
                    <Image
                      src={image}
                      alt=""
                      fill
                      unoptimized={isRemoteImageUrl(image)}
                      sizes="80px"
                      className="object-cover"
                    />
                  </button>
                ))}
              </div>

              <div className="relative aspect-[4/5] overflow-hidden bg-[#f5f5f5]">
                <Image
                  src={activeImageSrc}
                  alt={currentProduct.name}
                  fill
                  unoptimized={isRemoteImageUrl(activeImageSrc)}
                  sizes="(min-width: 1024px) 45vw, 80vw"
                  className="object-cover"
                  priority
                />
                {currentProduct.badge ? (
                  <div className="absolute top-3 left-3">
                    <span
                      className={cn(
                        "px-2.5 py-1 text-[11px]",
                        currentProduct.badge === "Sale"
                          ? "bg-black text-white"
                          : "border border-black/10 bg-white text-black",
                      )}
                    >
                      {BADGE_LABELS[currentProduct.badge] ?? currentProduct.badge}
                    </span>
                  </div>
                ) : null}
              </div>
            </div>
          </section>

          <section className="space-y-6 lg:sticky lg:top-20 lg:self-start">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs tracking-wider text-black/50 uppercase">
                  {currentProduct.brand}
                </p>
                <h1 className="mt-1 text-xl">{currentProduct.name}</h1>
                <p className="mt-1 text-xs text-black/40">{subcategoryLabel}</p>
              </div>
              <button
                onClick={handleShare}
                className="mt-1 p-2 transition-opacity hover:opacity-60"
                aria-label="Поделиться товаром"
              >
                <Share2 size={18} strokeWidth={1.5} />
              </button>
            </div>

            <div className="flex items-center gap-3">
              <Price amount={currentProduct.price} className="text-xl" />
              {currentProduct.originalPrice ? (
                <Price
                  amount={currentProduct.originalPrice}
                  strikethrough
                  className="text-sm text-black/40"
                />
              ) : null}
              {currentProduct.badge ? (
                <span className="border border-black/10 px-2 py-0.5 text-[11px]">
                  {BADGE_LABELS[currentProduct.badge] ?? currentProduct.badge}
                </span>
              ) : null}
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs tracking-wider text-black/40 uppercase">Размер</p>
                <button
                  onClick={() => setSizeModalOpen(true)}
                  className="text-xs text-black/50 underline underline-offset-2 transition-colors hover:text-black md:hidden"
                >
                  Выбрать размер
                </button>
              </div>

              <button
                onClick={() => setSizeModalOpen(true)}
                className="h-12 w-full border border-black/20 text-[11px] tracking-[2.5px] uppercase transition-colors hover:border-black md:hidden"
              >
                {selectedSize ? `Размер ${selectedSize}` : "Выбрать размер"}
              </button>

              <div className="hidden grid-cols-3 gap-2 sm:grid-cols-6 md:grid">
                {currentProduct.sizes.map((size) => {
                  const isDisabled = !currentProduct.inStock;
                  return (
                    <button
                      key={size}
                      onClick={() => handleSizeSelect(size)}
                      disabled={isDisabled}
                      className={cn(
                        "h-10 border text-xs transition-colors",
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

              <p className="mt-2 text-xs text-black/40">
                {selectedSize ? `Размер ${selectedSize} выбран` : "Выберите размер"}
              </p>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() =>
                  toggleFavorite(currentProduct.id, currentProduct.apiId, currentProduct)
                }
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
                disabled={isAdding}
                className="h-12 flex-1 bg-black px-5 text-[11px] tracking-[2.5px] text-white uppercase transition-colors hover:bg-black/80"
              >
                {isAdding ? "Добавляем" : isAdded ? "Добавлено" : "В корзину"}
              </button>
            </div>

            {cartError ? <p className="text-sm text-destructive">{cartError}</p> : null}

            <div className="border-t border-black/10 pt-5">
              <div className="flex border-b border-black/10">
                <button
                  onClick={() => setActiveTab("description")}
                  className={cn(
                    "border-b-2 px-0 py-3 pr-8 text-[11px] tracking-[1.8px] uppercase transition-colors",
                    activeTab === "description"
                      ? "border-black text-black"
                      : "border-transparent text-black/40 hover:text-black",
                  )}
                >
                  Описание
                </button>
                <button
                  onClick={() => setActiveTab("details")}
                  className={cn(
                    "border-b-2 px-0 py-3 text-[11px] tracking-[1.8px] uppercase transition-colors",
                    activeTab === "details"
                      ? "border-black text-black"
                      : "border-transparent text-black/40 hover:text-black",
                  )}
                >
                  Детали
                </button>
              </div>

              <div className="pt-4">
                {activeTab === "description" ? (
                  <div className="space-y-3 text-sm leading-relaxed text-black/60">
                    {currentProduct.description.split("\n\n").map((paragraph) => (
                      <p key={paragraph}>{paragraph}</p>
                    ))}
                  </div>
                ) : (
                  <div className="space-y-3">
                    {detailRows.map(([label, value]) => (
                      <div key={label} className="flex justify-between gap-6 text-xs">
                        <span className="text-black/40">{label}</span>
                        <span className="text-right">{value}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </section>
        </div>

        {relatedProducts.length > 0 ? (
          <section className="mt-16 border-t border-black/10 pt-10">
            <h2 className="mb-6 text-sm tracking-wider text-black/40 uppercase">
              Похожие товары
            </h2>
            <div className="flex gap-4 overflow-x-auto pb-2">
              {relatedProducts.map((item) => (
                <div key={item.id} className="w-44 shrink-0 sm:w-56">
                  <ProductCard
                    product={item}
                    compact
                    isFav={favorites.includes(item.id)}
                    onToggleFavorite={toggleFavorite}
                  />
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {otherRecentlyViewed.length > 0 ? (
          <section className="mt-12 border-t border-black/10 pt-10">
            <h2 className="mb-6 text-sm tracking-wider text-black/40 uppercase">
              Недавно просмотренные
            </h2>
            <div className="flex gap-4 overflow-x-auto pb-2">
              {otherRecentlyViewed.map((item) => (
                <div key={item.id} className="w-44 shrink-0 sm:w-56">
                  <ProductCard
                    product={item}
                    compact
                    isFav={favorites.includes(item.id)}
                    onToggleFavorite={toggleFavorite}
                  />
                </div>
              ))}
            </div>
          </section>
        ) : null}
      </div>

      <SizeModal
        product={currentProduct}
        open={isSizeModalOpen}
        onClose={() => setSizeModalOpen(false)}
      />
    </div>
  );
}
