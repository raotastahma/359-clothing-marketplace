"use client";

import { createContext, useContext, useMemo, useState } from "react";

export type GenderFilter = "Men" | "Women" | "";
export type SortBy = "default" | "price_asc" | "price_desc" | "new";

interface FilterContextValue {
  genderFilter: GenderFilter;
  categoryFilter: string;
  subcategoryFilter: string;
  brandFilters: string[];
  sizeFilters: string[];
  sortBy: SortBy;
  setGenderFilter: (value: GenderFilter) => void;
  setCategoryFilter: (value: string) => void;
  setSubcategoryFilter: (value: string) => void;
  setBrandFilter: (value: string) => void;
  toggleBrandFilter: (value: string) => void;
  toggleSizeFilter: (value: string) => void;
  setSortBy: (value: SortBy) => void;
  clearFilters: () => void;
}

const FilterContext = createContext<FilterContextValue | null>(null);

interface FilterProviderProps {
  children: React.ReactNode;
}

export function FilterProvider({ children }: FilterProviderProps) {
  const [genderFilter, setGenderFilter] = useState<GenderFilter>("");
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [subcategoryFilter, setSubcategoryFilter] = useState<string>("");
  const [brandFilters, setBrandFilters] = useState<string[]>([]);
  const [sizeFilters, setSizeFilters] = useState<string[]>([]);
  const [sortBy, setSortBy] = useState<SortBy>("default");

  function toggleBrandFilter(value: string): void {
    setBrandFilters((prev) =>
      prev.includes(value) ? prev.filter((item) => item !== value) : [...prev, value],
    );
  }

  function setBrandFilter(value: string): void {
    setBrandFilters(value ? [value] : []);
  }

  function toggleSizeFilter(value: string): void {
    setSizeFilters((prev) =>
      prev.includes(value) ? prev.filter((item) => item !== value) : [...prev, value],
    );
  }

  function clearFilters(): void {
    setGenderFilter("");
    setCategoryFilter("");
    setSubcategoryFilter("");
    setBrandFilters([]);
    setSizeFilters([]);
    setSortBy("default");
  }

  const value = useMemo<FilterContextValue>(
    () => ({
      genderFilter,
      categoryFilter,
      subcategoryFilter,
      brandFilters,
      sizeFilters,
      sortBy,
      setGenderFilter,
      setCategoryFilter,
      setSubcategoryFilter,
      setBrandFilter,
      toggleBrandFilter,
      toggleSizeFilter,
      setSortBy,
      clearFilters,
    }),
    [brandFilters, categoryFilter, genderFilter, sizeFilters, sortBy, subcategoryFilter],
  );

  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>;
}

export function useFilter(): FilterContextValue {
  const context = useContext(FilterContext);
  if (!context) throw new Error("useFilter must be used inside FilterProvider");
  return context;
}
