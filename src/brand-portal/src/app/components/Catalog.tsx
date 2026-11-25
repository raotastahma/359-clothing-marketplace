import { Link } from "react-router";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Archive, ChevronDown, ChevronLeft, ChevronRight, Edit2, Plus, X } from "lucide-react";
import {
  archiveBrandPortalProduct,
  getBrandPortalProducts,
  getCategories,
  type BrandPortalProduct,
  type BrandPortalProductImage,
  type CategoryTreeItem,
  type ProductStatus,
} from "../api";
import { useAuth } from "../auth-context";
import { PRODUCT_STATUS_COLORS } from "./constants";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./ui/table";

const PER_PAGE = 20;

const PRODUCT_STATUS_LABELS: Record<ProductStatus, string> = {
  active: "Активен",
  hidden: "Скрыт",
  archived: "Архив",
};

const STATUS_OPTIONS: FilterOption<ProductStatus>[] = [
  { value: "active", label: PRODUCT_STATUS_LABELS.active },
  { value: "hidden", label: PRODUCT_STATUS_LABELS.hidden },
  { value: "archived", label: PRODUCT_STATUS_LABELS.archived },
];

interface FilterOption<T extends string = string> {
  value: T;
  label: string;
}

interface FilterDropdownProps<T extends string = string> {
  label: string;
  options: FilterOption<T>[];
  selected: T | null;
  onChange: (value: T | null) => void;
  renderOption?: (option: FilterOption<T>) => ReactNode;
}

function FilterDropdown<T extends string>({
  label,
  options,
  selected,
  onChange,
  renderOption,
}: FilterDropdownProps<T>) {
  const [open, setOpen] = useState(false);
  const isActive = selected !== null;

  const toggle = (option: T) => {
    onChange(selected === option ? null : option);
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className={isActive ? "border-foreground" : ""}>
          {label}
          {isActive && (
            <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[9px] text-primary-foreground">
              1
            </span>
          )}
          <ChevronDown size={13} strokeWidth={1.5} className={open ? "rotate-180 transition-transform" : "transition-transform"} />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-auto min-w-[180px] p-0">
        {options.map((option) => {
          const checked = selected === option.value;
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => toggle(option.value)}
              className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-accent"
            >
              <span className={`size-3 rounded-full border border-border ${checked ? "bg-primary" : "bg-background"}`} />
              {renderOption ? renderOption(option) : <span className="text-sm text-foreground">{option.label}</span>}
            </button>
          );
        })}
        {isActive && (
          <button
            type="button"
            onClick={() => {
              onChange(null);
              setOpen(false);
            }}
            className="flex w-full items-center gap-2 border-t border-border px-4 py-2 text-xs text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <X size={11} strokeWidth={1.5} />
            Сбросить
          </button>
        )}
      </PopoverContent>
    </Popover>
  );
}

function ProductStatusBadge({ status }: { status: ProductStatus }) {
  return <Badge className={PRODUCT_STATUS_COLORS[status]}>{PRODUCT_STATUS_LABELS[status]}</Badge>;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Не удалось загрузить каталог.";
}

function formatCurrency(value: number | null) {
  if (value === null) return "—";

  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(value);
}

function firstImage(product: BrandPortalProduct): BrandPortalProductImage | null {
  return product.images.slice().sort((first, second) => first.sort_order - second.sort_order)[0] ?? null;
}

function firstVariantCode(product: BrandPortalProduct) {
  const variant = product.variants[0];
  return variant?.sku || variant?.vendor_code || "—";
}

function productStock(product: BrandPortalProduct) {
  return product.variants.reduce((total, variant) => total + Number(variant.stock_quantity ?? 0), 0);
}

function productPrice(product: BrandPortalProduct) {
  if (product.sale_price_rub !== null) return product.sale_price_rub;
  if (product.base_price_rub !== null) return product.base_price_rub;
  return product.variants.find((variant) => variant.price_rub !== null)?.price_rub ?? null;
}

function flattenCategories(categories: CategoryTreeItem[]): FilterOption[] {
  return categories.flatMap((category) => [
    { value: category.slug, label: category.name },
    ...flattenCategories(category.children),
  ]);
}

function uniqueProductCategories(products: BrandPortalProduct[]): FilterOption[] {
  const bySlug = new Map<string, string>();

  products.forEach((product) => {
    bySlug.set(product.category.slug, product.category.name);
  });

  return Array.from(bySlug, ([value, label]) => ({ value, label }));
}

function uniqueSeasons(products: BrandPortalProduct[], selectedSeason: string | null): FilterOption[] {
  const values = new Set<string>();

  products.forEach((product) => {
    if (product.season) values.add(product.season);
  });
  if (selectedSeason) values.add(selectedSeason);

  return Array.from(values, (season) => ({ value: season, label: season }));
}

function paginationItems(currentPage: number, totalPages: number) {
  if (totalPages <= 5) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const pages = new Set([1, totalPages, currentPage, currentPage - 1, currentPage + 1]);
  return Array.from(pages)
    .filter((page) => page >= 1 && page <= totalPages)
    .sort((first, second) => first - second)
    .reduce<(number | "ellipsis")[]>((items, page) => {
      const previous = items[items.length - 1];
      if (typeof previous === "number" && page - previous > 1) {
        items.push("ellipsis");
      }
      items.push(page);
      return items;
    }, []);
}

export function Catalog() {
  const { session } = useAuth();
  const canMutate = session?.role === "owner" || session?.role === "manager";
  const [products, setProducts] = useState<BrandPortalProduct[]>([]);
  const [categories, setCategories] = useState<FilterOption[]>([]);
  const [status, setStatus] = useState<ProductStatus | null>(null);
  const [category, setCategory] = useState<string | null>(null);
  const [season, setSeason] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [meta, setMeta] = useState({ page: 1, per_page: PER_PAGE, total: 0 });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [archivingId, setArchivingId] = useState<string | null>(null);

  const loadProducts = useCallback(() => {
    let ignore = false;

    setIsLoading(true);
    setError(null);
    getBrandPortalProducts({
      status: status ?? undefined,
      category: category ?? undefined,
      season: season ?? undefined,
      page,
      per_page: PER_PAGE,
    })
      .then((response) => {
        if (ignore) return;
        setProducts(response.data);
        setMeta(response.meta);
      })
      .catch((requestError: unknown) => {
        if (!ignore) setError(errorMessage(requestError));
      })
      .finally(() => {
        if (!ignore) setIsLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, [category, page, season, status]);

  useEffect(loadProducts, [loadProducts]);

  useEffect(() => {
    let ignore = false;

    getCategories()
      .then((response) => {
        if (!ignore) setCategories(flattenCategories(response.data));
      })
      .catch(() => {
        if (!ignore) setCategories([]);
      });

    return () => {
      ignore = true;
    };
  }, []);

  const categoryOptions = useMemo(
    () => (categories.length > 0 ? categories : uniqueProductCategories(products)),
    [categories, products],
  );
  const seasonOptions = useMemo(() => uniqueSeasons(products, season), [products, season]);
  const hasActiveFilters = status !== null || category !== null || season !== null;
  const totalPages = Math.max(1, Math.ceil(meta.total / meta.per_page));
  const pages = useMemo(() => paginationItems(meta.page, totalPages), [meta.page, totalPages]);

  const changeStatus = (value: ProductStatus | null) => {
    setStatus(value);
    setPage(1);
  };

  const changeCategory = (value: string | null) => {
    setCategory(value);
    setPage(1);
  };

  const changeSeason = (value: string | null) => {
    setSeason(value);
    setPage(1);
  };

  const resetFilters = () => {
    setStatus(null);
    setCategory(null);
    setSeason(null);
    setPage(1);
  };

  const archiveProduct = async (id: string) => {
    if (!canMutate) return;

    setArchivingId(id);
    setError(null);
    try {
      await archiveBrandPortalProduct(id);
      loadProducts();
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setArchivingId(null);
    }
  };

  return (
    <section className="p-4 md:p-8">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3 md:mb-6">
        <div>
          <h1 className="text-foreground">Каталог товаров</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {meta.total} товаров · страница {meta.page} из {totalPages}
          </p>
        </div>
        {canMutate && (
          <Button asChild>
            <Link to="/catalog/new">
              <Plus size={14} strokeWidth={1.5} />
              <span className="hidden sm:inline">Добавить товар</span>
            </Link>
          </Button>
        )}
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2 md:gap-3">
        <FilterDropdown label="Категория" options={categoryOptions} selected={category} onChange={changeCategory} />
        <FilterDropdown
          label="Статус"
          options={STATUS_OPTIONS}
          selected={status}
          onChange={changeStatus}
          renderOption={(option) => <ProductStatusBadge status={option.value} />}
        />
        <FilterDropdown label="Сезон" options={seasonOptions} selected={season} onChange={changeSeason} />
        {hasActiveFilters && (
          <Button variant="ghost" size="sm" onClick={resetFilters} className="text-muted-foreground">
            <X size={13} strokeWidth={1.5} />
            Сбросить
          </Button>
        )}
      </div>

      {error && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <span>{error}</span>
          <Button variant="outline" size="sm" onClick={loadProducts}>
            Повторить
          </Button>
        </div>
      )}

      <div className="overflow-x-auto rounded-md border border-border bg-card">
        <Table className="min-w-[760px]">
          <TableHeader>
            <TableRow className="bg-muted/50 hover:bg-muted/50">
              <TableHead className="w-16 px-3">Image</TableHead>
              <TableHead className="px-3">Название</TableHead>
              <TableHead className="px-3">Категория</TableHead>
              <TableHead className="px-3 text-right">Цена</TableHead>
              <TableHead className="px-3 text-right">Остаток</TableHead>
              <TableHead className="px-3">Статус</TableHead>
              {canMutate && <TableHead className="w-24 px-3 text-right">Actions</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={canMutate ? 7 : 6} className="px-5 py-10 text-center text-sm text-muted-foreground">
                  Загружаем товары
                </TableCell>
              </TableRow>
            ) : products.length === 0 ? (
              <TableRow>
                <TableCell colSpan={canMutate ? 7 : 6} className="px-5 py-10 text-center text-sm text-muted-foreground">
                  Нет товаров, соответствующих фильтрам
                </TableCell>
              </TableRow>
            ) : (
              products.map((product) => {
                const image = firstImage(product);
                return (
                  <TableRow key={product.id}>
                    <TableCell className="px-3 py-3">
                      <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-md border border-border bg-muted">
                        {image ? (
                          <img
                            src={image.url}
                            alt={image.alt_text ?? product.name}
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <div className="h-4 w-4 rounded-sm bg-muted-foreground/20" />
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="px-3 py-3">
                      <Link to={`/catalog/${product.id}`} className="text-sm text-foreground hover:underline">
                        {product.name}
                      </Link>
                      <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">{firstVariantCode(product)}</div>
                    </TableCell>
                    <TableCell className="px-3 py-3 text-sm text-muted-foreground">{product.category.name}</TableCell>
                    <TableCell className="px-3 py-3 text-right text-sm text-foreground">{formatCurrency(productPrice(product))}</TableCell>
                    <TableCell className="px-3 py-3 text-right text-sm text-foreground">{productStock(product)}</TableCell>
                    <TableCell className="px-3 py-3">
                      <ProductStatusBadge status={product.product_status} />
                    </TableCell>
                    {canMutate && (
                      <TableCell className="px-3 py-3">
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="icon" className="h-7 w-7" asChild>
                            <Link to={`/catalog/${product.id}`} aria-label="Редактировать товар">
                              <Edit2 size={13} strokeWidth={1.5} className="text-muted-foreground" />
                            </Link>
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            aria-label="Архивировать товар"
                            disabled={product.product_status === "archived" || archivingId === product.id}
                            onClick={() => archiveProduct(product.id)}
                          >
                            <Archive size={13} strokeWidth={1.5} className="text-muted-foreground" />
                          </Button>
                        </div>
                      </TableCell>
                    )}
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <span className="text-xs text-muted-foreground">
          Показано {products.length} из {meta.total}
        </span>
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            disabled={meta.page <= 1}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
          >
            <ChevronLeft size={14} strokeWidth={1.5} />
          </Button>
          {pages.map((pageItem, index) =>
            pageItem === "ellipsis" ? (
              <span key={`ellipsis-${index}`} className="flex h-8 w-8 items-center justify-center text-xs text-muted-foreground">
                ...
              </span>
            ) : (
              <Button
                key={pageItem}
                variant={pageItem === meta.page ? "default" : "outline"}
                size="icon"
                className="h-8 w-8 text-xs"
                onClick={() => setPage(pageItem)}
              >
                {pageItem}
              </Button>
            ),
          )}
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            disabled={meta.page >= totalPages}
            onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
          >
            <ChevronRight size={14} strokeWidth={1.5} />
          </Button>
        </div>
      </div>
    </section>
  );
}
