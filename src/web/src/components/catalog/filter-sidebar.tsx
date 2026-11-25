"use client";

import { ChevronDown, ChevronRight, X } from "lucide-react";
import { useEffect, useState } from "react";

import { useFilter, type SortBy } from "@/src/components/providers/filter-context";
import { useScrollLock } from "@/src/hooks/use-scroll-lock";

export interface CatalogCategoryOption {
  label: string;
  value: string;
  children: CatalogCategoryOption[];
}

export interface BrandFilterOption {
  label: string;
  value: string;
}

interface FilterSidebarProps {
  brands: BrandFilterOption[];
  categories: CatalogCategoryOption[];
  mobileOpen?: boolean;
  onClose?: () => void;
  onFilterChange?: () => void;
  sizes: string[];
}

const SORT_OPTIONS: { value: SortBy; label: string }[] = [
  { value: "default", label: "По умолчанию" },
  { value: "price_asc", label: "Сначала дешевле" },
  { value: "price_desc", label: "Сначала дороже" },
  { value: "new", label: "Сначала новые" },
];

export function FilterSidebar({
  brands,
  categories,
  mobileOpen = false,
  onClose,
  onFilterChange,
  sizes,
}: FilterSidebarProps) {
  const {
    categoryFilter,
    setCategoryFilter,
    subcategoryFilter,
    setSubcategoryFilter,
    brandFilters,
    setBrandFilter,
    sizeFilters,
    toggleSizeFilter,
    sortBy,
    setSortBy,
    clearFilters,
  } = useFilter();
  const [brandsOpen, setBrandsOpen] = useState(true);
  const [categoryOpen, setCategoryOpen] = useState(true);

  const hasCategories = categories.length > 0;
  const hasSizes = sizes.length > 0;
  const hasBrands = brands.length > 0;

  useScrollLock(mobileOpen);

  useEffect(() => {
    if (!mobileOpen || !onClose) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose?.();
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [mobileOpen, onClose]);

  const activeFilterCount =
    (categoryFilter ? 1 : 0) +
    (subcategoryFilter ? 1 : 0) +
    brandFilters.length +
    sizeFilters.length;

  const content = (
    <div className="h-full overflow-y-auto">
      {onClose && (
        <div className="flex items-center justify-between border-b border-black/10 px-5 py-4 lg:hidden">
          <span className="text-sm">
            Фильтры {activeFilterCount > 0 && `(${activeFilterCount})`}
          </span>
          <button onClick={onClose} className="p-1 transition-opacity hover:opacity-60">
            <X size={18} />
          </button>
        </div>
      )}

      <div className="space-y-6 px-5 py-5">
        {activeFilterCount > 0 && (
          <button
            onClick={() => {
              onFilterChange?.();
              clearFilters();
              onClose?.();
            }}
            className="text-xs text-black/50 underline-offset-2 transition-colors hover:text-black hover:underline"
          >
            Сбросить
          </button>
        )}

        <div>
          <p className="mb-3 text-xs tracking-wider text-black/40 uppercase">Сортировка</p>
          <div className="space-y-0.5">
            {SORT_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => {
                  onFilterChange?.();
                  setSortBy(option.value);
                }}
                className={`w-full px-2 py-1.5 text-left text-sm transition-colors hover:text-black ${
                  sortBy === option.value ? "text-black/70" : "text-black/40"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <button
            onClick={() => setCategoryOpen((value) => !value)}
            className="mb-3 flex w-full items-center justify-between text-xs tracking-wider text-black/40 uppercase"
          >
            <span>Категория</span>
            <ChevronDown
              size={14}
              className={`transition-transform ${categoryOpen ? "rotate-180" : ""}`}
            />
          </button>

          {categoryOpen && (
            <div className="space-y-0.5">
              {categories.map((category) => {
                const subcategories = category.children;
                const isActive = categoryFilter === category.value;

                return (
                  <div key={category.value}>
                    <button
                      onClick={() => {
                        onFilterChange?.();
                        if (isActive) {
                          setCategoryFilter("");
                          setSubcategoryFilter("");
                        } else {
                          setCategoryFilter(category.value);
                          setSubcategoryFilter("");
                        }
                      }}
                      className={`flex w-full items-center justify-between px-2 py-2 text-left text-sm transition-colors ${
                        isActive
                          ? "bg-black/5 text-black"
                          : "text-black/70 hover:bg-black/5 hover:text-black"
                      }`}
                    >
                      <span>{category.label}</span>
                      {subcategories.length > 0 && (
                        <ChevronRight
                          size={12}
                          className={`text-black/30 transition-transform ${
                            isActive ? "rotate-90" : ""
                          }`}
                        />
                      )}
                    </button>

                    {isActive && subcategories.length > 0 && (
                      <div className="mt-0.5 mb-1 ml-2 space-y-0.5 border-l border-black/15 pl-3">
                        {subcategories.map((subcategory) => (
                          <button
                            key={subcategory.value}
                            onClick={() => {
                              onFilterChange?.();
                              setSubcategoryFilter(
                                subcategoryFilter === subcategory.value ? "" : subcategory.value,
                              );
                            }}
                            className={`w-full px-2 py-1.5 text-left text-sm transition-colors ${
                              subcategoryFilter === subcategory.value
                                ? "text-black"
                                : "text-black/45 hover:text-black"
                            }`}
                          >
                            {subcategory.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
              {!hasCategories && <p className="px-2 py-1.5 text-sm text-black/40">Нет категорий</p>}
            </div>
          )}
        </div>

        <div>
          <p className="mb-3 text-xs tracking-wider text-black/40 uppercase">Размер</p>
          <div className="flex flex-wrap gap-2">
            {sizes.map((size) => {
              const active = sizeFilters.includes(size);

              return (
                <button
                  key={size}
                  onClick={() => {
                    onFilterChange?.();
                    toggleSizeFilter(size);
                  }}
                  className={`${size.length > 3 ? "px-3" : "w-10"} h-10 border text-xs transition-colors ${
                    active
                      ? "border-black bg-black text-white"
                      : "border-black/20 text-black/70 hover:border-black"
                  }`}
                >
                  {size}
                </button>
              );
            })}
            {!hasSizes && <p className="text-sm text-black/40">Нет размеров</p>}
          </div>
        </div>

        <div>
          <button
            onClick={() => setBrandsOpen((value) => !value)}
            className="mb-3 flex w-full items-center justify-between text-xs tracking-wider text-black/40 uppercase"
          >
            <span>Бренд</span>
            <ChevronDown
              size={14}
              className={`transition-transform ${brandsOpen ? "rotate-180" : ""}`}
            />
          </button>
          {brandsOpen && (
            <div className="space-y-0.5">
              {brands.map((brand) => {
                const isActive = brandFilters.includes(brand.value);

                return (
                  <label
                    key={brand.value}
                    className="flex cursor-pointer items-center gap-2 px-2 py-1.5 text-sm text-black/70 transition-colors hover:text-black"
                  >
                    <input
                      type="checkbox"
                      checked={isActive}
                      onChange={() => {
                        onFilterChange?.();
                        setBrandFilter(isActive ? "" : brand.value);
                      }}
                      className="h-3.5 w-3.5 accent-black"
                    />
                    <span>{brand.label}</span>
                  </label>
                );
              })}
              {!hasBrands && <p className="px-2 py-1.5 text-sm text-black/40">Нет брендов</p>}
            </div>
          )}
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="w-full bg-black py-3 text-sm text-white transition-colors hover:bg-black/80 lg:hidden"
          >
            Применить фильтры {activeFilterCount > 0 && `(${activeFilterCount})`}
          </button>
        )}
      </div>
    </div>
  );

  return (
    <>
      <aside className="sticky top-14 hidden h-[calc(100vh-56px)] w-56 flex-shrink-0 self-start border-r border-black/10 lg:block">
        {content}
      </aside>

      {onClose && (
        <>
          {mobileOpen && (
            <button
              className="fixed inset-0 z-40 bg-black/40 lg:hidden"
              onClick={onClose}
              aria-label="Закрыть фильтры"
            />
          )}
          <div
            className={`fixed top-0 left-0 z-40 h-full w-72 bg-white shadow-2xl transition-transform duration-300 ease-in-out lg:hidden ${
              mobileOpen ? "translate-x-0" : "-translate-x-full"
            }`}
          >
            {content}
          </div>
        </>
      )}
    </>
  );
}
