import type {
  Product as ApiProduct,
  ProductListItem,
  ProductVariant,
} from "@/src/lib/api";
import type { Product as UiProduct } from "@/src/types/product";

function imageUrls(images: ProductListItem["images"]): string[] {
  const urls = images.map((image) => image.url).filter(Boolean);
  return urls.length > 0 ? urls : ["/logo.svg"];
}

function priceNumber(value: unknown): number | undefined {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : undefined;
  }

  if (typeof value === "string") {
    const price = Number(value.trim());
    return Number.isFinite(price) ? price : undefined;
  }

  return undefined;
}

function badgeFor({
  compareAtPrice,
  isNewArrival,
}: {
  compareAtPrice: number | null | undefined;
  isNewArrival: boolean;
}): UiProduct["badge"] {
  if (compareAtPrice) return "Sale";
  if (isNewArrival) return "New arrival";
  return undefined;
}

function genderFromCategory(gender: string | null | undefined): UiProduct["gender"] {
  if (gender === "men") return "Men";
  if (gender === "women") return "Women";
  return "Unisex";
}

function variantIdsBySize(variants: ProductVariant[]): Record<string, string> {
  return variants.reduce<Record<string, string>>((ids, variant) => {
    if (variant.is_active && variant.stock_quantity > 0 && !ids[variant.size]) {
      ids[variant.size] = variant.id;
    }
    return ids;
  }, {});
}

const APPAREL_SIZE_ORDER = ["XXXS", "XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL"];

function compareAvailableSizes(first: string, second: string): number {
  const firstIndex = APPAREL_SIZE_ORDER.indexOf(first.trim().toUpperCase());
  const secondIndex = APPAREL_SIZE_ORDER.indexOf(second.trim().toUpperCase());

  if (firstIndex >= 0 && secondIndex >= 0) return firstIndex - secondIndex;
  if (firstIndex >= 0) return -1;
  if (secondIndex >= 0) return 1;

  return first.localeCompare(second, undefined, { numeric: true, sensitivity: "base" });
}

function variantPrices(variants: ProductVariant[]): number[] {
  return variants
    .filter((variant) => variant.is_active)
    .map((variant) => priceNumber(variant.price_rub))
    .filter((price): price is number => price !== undefined && price > 0);
}

function variantCompareAtPrices(variants: ProductVariant[]): number[] {
  return variants
    .filter((variant) => variant.is_active && variant.compare_at_price_rub)
    .map((variant) => priceNumber(variant.compare_at_price_rub))
    .filter((price): price is number => price !== undefined && price > 0);
}

export function productListItemToUiProduct(product: ProductListItem): UiProduct {
  const compareAtPrice = priceNumber(product.compare_at_price_from);

  return {
    id: product.slug,
    apiId: product.id,
    brand: product.brand.name,
    name: product.name,
    category: product.category.parent?.name ?? product.category.name,
    subcategory: product.category.name,
    price: priceNumber(product.price_from) ?? 0,
    originalPrice: compareAtPrice,
    badge: badgeFor({
      compareAtPrice,
      isNewArrival: product.is_new_arrival,
    }),
    sizes: product.available_sizes,
    images: imageUrls(product.images),
    description: "",
    inStock: product.available_sizes.length > 0,
    gender: genderFromCategory(product.category.gender),
  };
}

export function productDetailToUiProduct(product: ApiProduct): UiProduct {
  const prices = variantPrices(product.variants);
  const compareAtPrices = variantCompareAtPrices(product.variants);
  const salePrice = priceNumber(product.sale_price_rub);
  const basePrice = priceNumber(product.base_price_rub);
  const price = salePrice ?? basePrice ?? Math.min(...prices);
  const originalPrice =
    salePrice && basePrice
      ? basePrice
      : compareAtPrices.length > 0
        ? Math.min(...compareAtPrices)
        : undefined;
  const sizeVariantIds = variantIdsBySize(product.variants);
  const sizes = Object.keys(sizeVariantIds).sort(compareAvailableSizes);

  return {
    id: product.slug,
    apiId: product.id,
    brand: product.brand.name,
    name: product.name,
    category: product.category.parent?.name ?? product.category.name,
    subcategory: product.category.name,
    price: Number.isFinite(price) ? price : 0,
    originalPrice,
    badge: badgeFor({
      compareAtPrice: originalPrice,
      isNewArrival: product.is_new_arrival,
    }),
    sizes,
    images: imageUrls(product.images),
    description: product.description ?? "",
    inStock: sizes.length > 0,
    gender: genderFromCategory(product.category.gender),
    material: product.fabric_composition ?? undefined,
    careInstructions: product.care_instructions ?? undefined,
    season: product.season ?? undefined,
    variantIdsBySize: sizeVariantIds,
  };
}
