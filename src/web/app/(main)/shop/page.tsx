"use client";

import { ChevronLeft, ChevronRight, SlidersHorizontal } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  FilterSidebar,
  type BrandFilterOption,
  type CatalogCategoryOption,
} from "@/src/components/catalog/filter-sidebar";
import { ProductCard } from "@/src/components/catalog/product-card";
import { useFilter } from "@/src/components/providers/filter-context";
import { useUser } from "@/src/components/providers/user-context";
import {
  requestJson,
  type ApiMeta,
  type BrandsApiResponse,
  type CategoriesApiResponse,
  type Category,
  type ProductsApiResponse,
} from "@/src/lib/api";
import { productListItemToUiProduct } from "@/src/lib/product-adapter";
import { type Product } from "@/src/types/product";

const PER_PAGE = 20;
type BadgeFilter = "" | "Sale";

function isGenderRoot(category: Category): boolean {
  return category.slug === "men" || category.slug === "women";
}

function categoryOption(category: Category, labelPrefix = ""): CatalogCategoryOption {
  return {
    label: labelPrefix ? `${labelPrefix} / ${category.name}` : category.name,
    value: category.slug,
    children: (category.children ?? []).map((child) => categoryOption(child)),
  };
}

function categoryOptionsForGender(
  categories: Category[],
  genderFilter: "Men" | "Women" | "",
): CatalogCategoryOption[] {
  const hasGenderRoots = categories.some(isGenderRoot);
  if (!hasGenderRoots) {
    const gender = genderFilter.toLowerCase();
    return categories
      .filter((category) => !gender || category.gender === gender || category.gender === "unisex")
      .map((category) => categoryOption(category));
  }

  if (genderFilter) {
    const rootSlug = genderFilter.toLowerCase();
    const root = categories.find((category) => category.slug === rootSlug);
    return root ? root.children.map((category) => categoryOption(category)) : [];
  }

  return categories.flatMap((root) =>
    root.children.map((category) => categoryOption(category, root.name)),
  );
}

function findCategoryOption(
  options: CatalogCategoryOption[],
  value: string,
): CatalogCategoryOption | null {
  for (const option of options) {
    const unprefixedLabel = option.label.split(" / ").at(-1);
    if (option.value === value || option.label === value || unprefixedLabel === value) {
      return option;
    }

    const childOption = findCategoryOption(option.children, value);
    if (childOption) return childOption;
  }

  return null;
}

function findCategoryValue(options: CatalogCategoryOption[], value: string): string {
  return findCategoryOption(options, value)?.value ?? value;
}

function sortedSizes(sizes: string[]): string[] {
  return [...new Set(sizes)].sort((a, b) => a.localeCompare(b, "ru", { numeric: true }));
}

export default function ShopPage() {
  const {
    genderFilter,
    categoryFilter,
    setCategoryFilter,
    subcategoryFilter,
    setSubcategoryFilter,
    brandFilters,
    sizeFilters,
    sortBy,
    setGenderFilter,
    clearFilters,
  } = useFilter();
  const { favorites, toggleFavorite } = useUser();
  const searchParams = useSearchParams();
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [meta, setMeta] = useState<ApiMeta | null>(null);
  const [page, setPage] = useState(1);
  const [categories, setCategories] = useState<Category[]>([]);
  const [brands, setBrands] = useState<BrandFilterOption[]>([]);
  const [sizes, setSizes] = useState<string[]>([]);
  const [badgeFilter, setBadgeFilter] = useState<BadgeFilter>("");
  const [isLoading, setLoading] = useState(true);
  const [productsError, setProductsError] = useState<string | null>(null);
  const [filtersError, setFiltersError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const drag = useRef({ active: false, startX: 0, scrollLeft: 0 });

  const handleCloseMobileFilters = useCallback(() => setMobileFiltersOpen(false), []);
  const resetPage = useCallback(() => setPage(1), []);

  const categoryOptions = useMemo(
    () => categoryOptionsForGender(categories, genderFilter),
    [categories, genderFilter],
  );

  const navParent = useMemo(() => {
    if (!categoryFilter) return null;
    return categoryOptions.find((category) => category.value === categoryFilter) ?? null;
  }, [categoryFilter, categoryOptions]);

  useEffect(() => {
    const category = searchParams.get("category");
    const badge = searchParams.get("badge");
    const gender = searchParams.get("gender");
    const nextGender = gender === "Men" || gender === "Women" ? gender : "";
    const nextBadge = badge === "Sale" ? "Sale" : "";

    if (category && !nextBadge) {
      const nextOptions = categoryOptionsForGender(categories, nextGender);
      setCategoryFilter(findCategoryValue(nextOptions, category));
    } else {
      setCategoryFilter("");
    }

    setBadgeFilter(nextBadge);
    setGenderFilter(nextGender);
  }, [categories, searchParams, setCategoryFilter, setGenderFilter]);

  useEffect(() => {
    let isMounted = true;

    Promise.all([
      requestJson<CategoriesApiResponse>("/categories", {
        redirectOnUnauthorized: false,
      }),
      requestJson<BrandsApiResponse>("/brands?per_page=100", {
        redirectOnUnauthorized: false,
      }),
    ])
      .then(([categoriesResponse, brandsResponse]) => {
        if (!isMounted) return;
        setFiltersError(null);
        setCategories(categoriesResponse.data);
        setBrands(
          brandsResponse.data.map((brand) => ({
            label: brand.name,
            value: brand.slug,
          })),
        );
      })
      .catch((nextError: unknown) => {
        if (!isMounted) return;
        setCategories([]);
        setBrands([]);
        setFiltersError(
          nextError instanceof Error
            ? nextError.message
            : "Не удалось загрузить фильтры. Попробуйте ещё раз.",
        );
      });

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;
    const query = new URLSearchParams({
      page: String(page),
      per_page: String(PER_PAGE),
    });
    const selectedCategory = subcategoryFilter || categoryFilter;

    if (genderFilter === "Men") query.set("gender", "men");
    if (genderFilter === "Women") query.set("gender", "women");
    if (selectedCategory) query.set("category", selectedCategory);
    if (brandFilters[0]) query.set("brand", brandFilters[0]);
    if (sizeFilters.length > 0) query.set("size", sizeFilters.join(","));
    if (badgeFilter === "Sale") query.set("is_sale", "true");
    if (sortBy !== "default") query.set("sort", sortBy === "new" ? "newest" : sortBy);

    async function loadProducts(): Promise<void> {
      setLoading(true);

      try {
        const { data, meta: nextMeta } = await requestJson<ProductsApiResponse>(
          `/products?${query.toString()}`,
          {
            redirectOnUnauthorized: false,
          },
        );
        if (!isMounted) return;
        setProductsError(null);
        setProducts(data.map(productListItemToUiProduct));
        setMeta(nextMeta);
        setSizes((prevSizes) =>
          sortedSizes([
            ...prevSizes,
            ...sizeFilters,
            ...data.flatMap((product) => product.available_sizes),
          ]),
        );
      } catch (nextError: unknown) {
        if (!isMounted) return;
        setProducts([]);
        setMeta(null);
        setProductsError(
          nextError instanceof Error
            ? nextError.message
            : "Не удалось загрузить товары. Попробуйте ещё раз.",
        );
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    void loadProducts();

    return () => {
      isMounted = false;
    };
  }, [
    badgeFilter,
    brandFilters,
    categoryFilter,
    genderFilter,
    page,
    sizeFilters,
    sortBy,
    subcategoryFilter,
  ]);

  function onMouseDown(event: React.MouseEvent) {
    drag.current = {
      active: true,
      startX: event.pageX,
      scrollLeft: scrollRef.current?.scrollLeft ?? 0,
    };
  }

  function onMouseMove(event: React.MouseEvent) {
    if (!drag.current.active || !scrollRef.current) return;
    scrollRef.current.scrollLeft = drag.current.scrollLeft - (event.pageX - drag.current.startX);
  }

  function onMouseUp() {
    drag.current.active = false;
  }

  function handleTopClick(value: string) {
    resetPage();
    setBadgeFilter("");
    setCategoryFilter(value);
    setSubcategoryFilter("");
  }

  function handleSubClick(value: string) {
    resetPage();
    setSubcategoryFilter(subcategoryFilter === value ? "" : value);
  }

  function handleBack() {
    resetPage();
    setBadgeFilter("");
    setCategoryFilter("");
    setSubcategoryFilter("");
  }

  function clearVisibleFilters() {
    resetPage();
    setBadgeFilter("");
    setGenderFilter("");
    setCategoryFilter("");
    setSubcategoryFilter("");
  }

  function handleSaleClick() {
    resetPage();
    setBadgeFilter(badgeFilter === "Sale" ? "" : "Sale");
    setCategoryFilter("");
    setSubcategoryFilter("");
  }

  const error = productsError ?? filtersError;
  const isAtRoot = !navParent;
  const currentSubcategories = navParent ? navParent.children : [];
  const totalPages = Math.max(1, Math.ceil((meta?.total ?? 0) / (meta?.per_page ?? PER_PAGE)));
  const btnBase =
    "shrink-0 px-5 py-3.5 text-[11px] tracking-[1.8px] uppercase transition-colors whitespace-nowrap";
  const btnActive = "border-b-2 border-black -mb-px font-semibold text-black";
  const btnIdle = "text-black/40 hover:text-black";

  return (
    <div className="min-h-screen">
      <div className="sticky top-14 z-30 flex items-stretch border-b border-black/10 bg-white">
        <div
          ref={scrollRef}
          className="flex flex-1 select-none items-stretch overflow-x-auto"
          style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseUp}
        >
          {isAtRoot ? (
            <>
              <button
                onClick={clearVisibleFilters}
                className={`${btnBase} ${!categoryFilter && !badgeFilter ? btnActive : btnIdle}`}
              >
                Все
              </button>

              <button
                onClick={handleSaleClick}
                className={`${btnBase} ${badgeFilter === "Sale" ? btnActive : btnIdle}`}
              >
                Sale
              </button>

              {categoryOptions.map((category) => (
                <button
                  key={category.value}
                  onClick={() => handleTopClick(category.value)}
                  className={`${btnBase} ${
                    categoryFilter === category.value ? btnActive : btnIdle
                  }`}
                >
                  {category.label}
                </button>
              ))}
            </>
          ) : (
            <>
              <button
                onClick={handleBack}
                className="flex shrink-0 items-center gap-1 border-r border-black/10 py-3.5 pr-4 pl-3 text-[11px] tracking-[1.8px] whitespace-nowrap text-black/40 uppercase transition-colors hover:text-black"
              >
                <ChevronLeft size={13} strokeWidth={2} />
                <span>{navParent.label}</span>
              </button>

              <button
                onClick={() => setSubcategoryFilter("")}
                className={`${btnBase} ${!subcategoryFilter ? btnActive : btnIdle}`}
              >
                Все
              </button>

              {currentSubcategories.map((subcategory) => (
                <button
                  key={subcategory.value}
                  onClick={() => handleSubClick(subcategory.value)}
                  className={`${btnBase} ${
                    subcategoryFilter === subcategory.value ? btnActive : btnIdle
                  }`}
                >
                  {subcategory.label}
                </button>
              ))}
            </>
          )}
        </div>

        <button
          onClick={() => setMobileFiltersOpen((value) => !value)}
          className="flex shrink-0 items-center gap-2 border-l border-black/10 px-5 text-[11px] tracking-[1.5px] text-black/50 uppercase transition-colors hover:text-black md:hidden"
        >
          <SlidersHorizontal size={13} strokeWidth={1.8} />
          Фильтры
        </button>
      </div>

      <div className="flex items-start">
        <FilterSidebar
          brands={brands}
          categories={categoryOptions}
          mobileOpen={mobileFiltersOpen}
          onClose={handleCloseMobileFilters}
          onFilterChange={resetPage}
          sizes={sizes}
        />

        <main className="flex-1 px-4 py-6 md:px-8">
          {isLoading ? (
            <div className="grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 8 }).map((_, index) => (
                <div key={index} className="space-y-3">
                  <div className="aspect-[3/4] animate-pulse bg-black/5" />
                  <div className="h-3 w-2/3 animate-pulse bg-black/10" />
                  <div className="h-3 w-1/3 animate-pulse bg-black/10" />
                </div>
              ))}
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-24 text-center text-black/50">
              <p className="text-sm">{error}</p>
            </div>
          ) : products.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-black/40">
              <p className="text-sm">Товары не найдены</p>
              <button
                onClick={() => {
                  resetPage();
                  setBadgeFilter("");
                  clearFilters();
                }}
                className="mt-3 text-xs text-black underline underline-offset-2"
              >
                Сбросить фильтры
              </button>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
                {products.map((product) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    isFav={favorites.includes(product.id)}
                    onToggleFavorite={toggleFavorite}
                  />
                ))}
              </div>

              {totalPages > 1 && (
                <div className="mt-10 flex items-center justify-center gap-3">
                  <button
                    onClick={() => setPage((value) => Math.max(1, value - 1))}
                    disabled={page <= 1}
                    className="flex h-9 items-center gap-2 border border-black/15 px-3 text-xs text-black/60 transition-colors hover:border-black hover:text-black disabled:pointer-events-none disabled:opacity-35"
                  >
                    <ChevronLeft size={13} strokeWidth={2} />
                    Назад
                  </button>
                  <span className="text-xs text-black/45">
                    {page} / {totalPages}
                  </span>
                  <button
                    onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
                    disabled={page >= totalPages}
                    className="flex h-9 items-center gap-2 border border-black/15 px-3 text-xs text-black/60 transition-colors hover:border-black hover:text-black disabled:pointer-events-none disabled:opacity-35"
                  >
                    Вперёд
                    <ChevronRight size={13} strokeWidth={2} />
                  </button>
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
