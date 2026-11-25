import { Link, useNavigate, useParams } from "react-router";
import { type ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ChevronLeft, GripVertical, ImagePlus, Plus, Save, Trash2, X } from "lucide-react";
import {
  createBrandPortalProduct,
  createBrandPortalProductVariant,
  deleteBrandPortalProductImage,
  deleteBrandPortalProductVariant,
  getBrandPortalProduct,
  getCategories,
  reorderBrandPortalProductImages,
  updateBrandPortalProduct,
  updateBrandPortalProductVariant,
  uploadBrandPortalProductImages,
  type BrandPortalProduct,
  type BrandPortalProductImage,
  type BrandPortalProductPayload,
  type BrandPortalProductVariant,
  type BrandPortalProductVariantPayload,
  type CategoryTreeItem,
  type ProductStatus,
} from "../api";
import { useAuth } from "../auth-context";
import { PRODUCT_STATUS_COLORS } from "./constants";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import { Switch } from "./ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./ui/table";
import { Textarea } from "./ui/textarea";

const PRODUCT_STATUS_LABELS: Record<ProductStatus, string> = {
  active: "Активен",
  hidden: "Скрыт",
  archived: "Архив",
};

const PRODUCT_STATUSES: ProductStatus[] = ["active", "hidden", "archived"];
const MAX_PRODUCT_IMAGES = 10;
const MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024;
const SUPPORTED_IMAGE_TYPES = new Set(["image/jpeg", "image/png"]);

interface CategoryOption {
  id: string;
  label: string;
}

interface ProductForm {
  name: string;
  slug: string;
  description: string;
  fabric_composition: string;
  care_instructions: string;
  category_id: string;
  season: string;
  base_price_rub: string;
  sale_price_rub: string;
  product_status: ProductStatus;
  is_new_arrival: boolean;
}

interface VariantForm {
  rowId: string;
  id: string | null;
  vendor_code: string;
  size: string;
  color: string;
  sku: string;
  price_rub: string;
  compare_at_price_rub: string;
  stock_quantity: string;
  is_active: boolean;
}

interface PendingImage {
  rowId: string;
  file: File;
}

let variantRowCounter = 0;
let pendingImageCounter = 0;

function nextVariantRowId() {
  variantRowCounter += 1;
  return `variant-row-${variantRowCounter}`;
}

function nextPendingImageRowId() {
  pendingImageCounter += 1;
  return `pending-image-${pendingImageCounter}`;
}

function emptyProductForm(): ProductForm {
  return {
    name: "",
    slug: "",
    description: "",
    fabric_composition: "",
    care_instructions: "",
    category_id: "",
    season: "",
    base_price_rub: "",
    sale_price_rub: "",
    product_status: "active",
    is_new_arrival: false,
  };
}

function emptyVariantForm(): VariantForm {
  return {
    rowId: nextVariantRowId(),
    id: null,
    vendor_code: "",
    size: "",
    color: "",
    sku: "",
    price_rub: "",
    compare_at_price_rub: "",
    stock_quantity: "0",
    is_active: true,
  };
}

function textOrNull(value: string) {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

function optionalNumber(value: string) {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

function requiredNumber(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Не удалось сохранить товар.";
}

function flattenCategories(categories: CategoryTreeItem[], prefix = ""): CategoryOption[] {
  return categories.flatMap((category) => [
    { id: category.id, label: `${prefix}${category.name}` },
    ...flattenCategories(category.children, `${prefix}${category.name} / `),
  ]);
}

function productToForm(product: BrandPortalProduct): ProductForm {
  return {
    name: product.name,
    slug: product.slug,
    description: product.description ?? "",
    fabric_composition: product.fabric_composition ?? "",
    care_instructions: product.care_instructions ?? "",
    category_id: product.category.id,
    season: product.season ?? "",
    base_price_rub: product.base_price_rub === null ? "" : String(product.base_price_rub),
    sale_price_rub: product.sale_price_rub === null ? "" : String(product.sale_price_rub),
    product_status: product.product_status,
    is_new_arrival: product.is_new_arrival,
  };
}

function variantToForm(variant: BrandPortalProductVariant): VariantForm {
  return {
    rowId: variant.id,
    id: variant.id,
    vendor_code: variant.vendor_code ?? "",
    size: variant.size,
    color: variant.color ?? "",
    sku: variant.sku,
    price_rub: variant.price_rub === null ? "" : String(variant.price_rub),
    compare_at_price_rub: variant.compare_at_price_rub === null ? "" : String(variant.compare_at_price_rub),
    stock_quantity: String(variant.stock_quantity),
    is_active: variant.is_active,
  };
}

function productPayload(form: ProductForm): BrandPortalProductPayload {
  return {
    name: form.name.trim(),
    slug: textOrNull(form.slug),
    description: textOrNull(form.description),
    fabric_composition: textOrNull(form.fabric_composition),
    care_instructions: textOrNull(form.care_instructions),
    category_id: form.category_id,
    season: textOrNull(form.season),
    base_price_rub: optionalNumber(form.base_price_rub),
    sale_price_rub: optionalNumber(form.sale_price_rub),
    product_status: form.product_status,
    is_active: form.product_status !== "archived",
    is_new_arrival: form.is_new_arrival,
  };
}

function variantPayload(variant: VariantForm): BrandPortalProductVariantPayload {
  return {
    vendor_code: textOrNull(variant.vendor_code),
    size: variant.size.trim(),
    color: textOrNull(variant.color),
    sku: variant.sku.trim(),
    price_rub: requiredNumber(variant.price_rub),
    compare_at_price_rub: optionalNumber(variant.compare_at_price_rub),
    stock_quantity: Number.parseInt(variant.stock_quantity, 10),
    is_active: variant.is_active,
  };
}

function sameVariantPayload(first: BrandPortalProductVariantPayload, second: BrandPortalProductVariantPayload) {
  return (
    first.vendor_code === second.vendor_code &&
    first.size === second.size &&
    first.color === second.color &&
    first.sku === second.sku &&
    first.price_rub === second.price_rub &&
    first.compare_at_price_rub === second.compare_at_price_rub &&
    first.stock_quantity === second.stock_quantity &&
    first.is_active === second.is_active
  );
}

function validateForm(form: ProductForm, variants: VariantForm[]) {
  if (!form.name.trim()) return "Укажите название товара.";
  if (!form.category_id) return "Выберите категорию.";
  if (variants.length === 0) return "Добавьте хотя бы один вариант.";

  const basePrice = optionalNumber(form.base_price_rub);
  const salePrice = optionalNumber(form.sale_price_rub);
  if (Number.isNaN(basePrice) || Number.isNaN(salePrice)) return "Цена товара должна быть числом.";

  for (const variant of variants) {
    if (!variant.size.trim()) return "Укажите размер для каждого варианта.";
    if (!variant.sku.trim()) return "Укажите SKU для каждого варианта.";

    const price = requiredNumber(variant.price_rub);
    if (!Number.isFinite(price) || price <= 0) return "Цена каждого варианта должна быть больше 0.";

    const compareAtPrice = optionalNumber(variant.compare_at_price_rub);
    if (Number.isNaN(compareAtPrice) || (compareAtPrice !== null && compareAtPrice < 0)) {
      return "Старая цена варианта должна быть числом не меньше 0.";
    }

    const stock = Number.parseInt(variant.stock_quantity, 10);
    if (!Number.isInteger(stock) || stock < 0 || String(stock) !== variant.stock_quantity.trim()) {
      return "Остаток каждого варианта должен быть целым числом не меньше 0.";
    }
  }

  return null;
}

function sortedImages(images: BrandPortalProductImage[]) {
  return images.slice().sort((first, second) => {
    if (first.sort_order !== second.sort_order) return first.sort_order - second.sort_order;
    return first.id.localeCompare(second.id);
  });
}

function mergeImages(current: BrandPortalProductImage[], next: BrandPortalProductImage[]) {
  const byId = new Map(current.map((image) => [image.id, image]));
  for (const image of next) {
    byId.set(image.id, image);
  }
  return sortedImages(Array.from(byId.values()));
}

function imageSelectionError(files: File[], currentCount: number) {
  if (files.length === 0) return "Выберите хотя бы один файл.";
  if (currentCount + files.length > MAX_PRODUCT_IMAGES) return "У товара может быть не больше 10 изображений.";

  for (const file of files) {
    if (!SUPPORTED_IMAGE_TYPES.has(file.type)) return "Можно загрузить только JPEG или PNG.";
    if (file.size > MAX_IMAGE_SIZE_BYTES) return "Каждый файл должен быть не больше 5 МБ.";
  }

  return null;
}

function imagesFormData(files: File[], startSortOrder: number) {
  const formData = new FormData();
  const sortOrders = files.map((_, index) => startSortOrder + index);

  for (const file of files) {
    formData.append("files", file);
  }
  formData.append("sort_orders", JSON.stringify(sortOrders));

  return formData;
}

export function ProductEditor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { session } = useAuth();
  const [createdProductId, setCreatedProductId] = useState<string | null>(null);
  const productId = id ?? createdProductId;
  const isNew = !productId;
  const canMutate = session?.role === "owner" || session?.role === "manager";
  const [form, setForm] = useState<ProductForm>(() => emptyProductForm());
  const [variants, setVariants] = useState<VariantForm[]>(() => [emptyVariantForm()]);
  const [originalVariants, setOriginalVariants] = useState<Record<string, BrandPortalProductVariantPayload>>({});
  const [deletedVariantIds, setDeletedVariantIds] = useState<string[]>([]);
  const [images, setImages] = useState<BrandPortalProductImage[]>([]);
  const [pendingImages, setPendingImages] = useState<PendingImage[]>([]);
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [isLoading, setIsLoading] = useState(!isNew);
  const [isCategoryLoading, setIsCategoryLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isImageUploading, setIsImageUploading] = useState(false);
  const [isImageReordering, setIsImageReordering] = useState(false);
  const [imageActionId, setImageActionId] = useState<string | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadProduct = useCallback(() => {
    if (!id) {
      if (createdProductId) {
        setIsLoading(false);
        return;
      }

      setIsLoading(false);
      setForm(emptyProductForm());
      setVariants([emptyVariantForm()]);
      setOriginalVariants({});
      setDeletedVariantIds([]);
      setImages([]);
      setPendingImages([]);
      setImageError(null);
      return;
    }

    if (id === createdProductId) {
      setIsLoading(false);
      return;
    }

    let ignore = false;
    setIsLoading(true);
    setError(null);

    getBrandPortalProduct(id)
      .then((response) => {
        if (ignore) return;
        const nextVariants = response.data.variants.map(variantToForm);

        setForm(productToForm(response.data));
        setVariants(nextVariants.length > 0 ? nextVariants : [emptyVariantForm()]);
        setOriginalVariants(
          response.data.variants.reduce<Record<string, BrandPortalProductVariantPayload>>((items, variant) => {
            items[variant.id] = variantPayload(variantToForm(variant));
            return items;
          }, {}),
        );
        setDeletedVariantIds([]);
        setImages(sortedImages(response.data.images));
        setPendingImages([]);
        setImageError(null);
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
  }, [createdProductId, id]);

  useEffect(loadProduct, [loadProduct]);

  useEffect(() => {
    let ignore = false;
    setIsCategoryLoading(true);

    getCategories()
      .then((response) => {
        if (!ignore) setCategories(flattenCategories(response.data));
      })
      .catch((requestError: unknown) => {
        if (!ignore) setError(errorMessage(requestError));
      })
      .finally(() => {
        if (!ignore) setIsCategoryLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, []);

  const imageList = useMemo(() => sortedImages(images), [images]);
  const imageCount = imageList.length + pendingImages.length;

  const updateForm = <K extends keyof ProductForm>(field: K, value: ProductForm[K]) => {
    setForm((current) => ({ ...current, [field]: value }));
    setFeedback(null);
    setError(null);
  };

  const updateVariant = <K extends keyof VariantForm>(rowId: string, field: K, value: VariantForm[K]) => {
    setVariants((current) =>
      current.map((variant) => (variant.rowId === rowId ? { ...variant, [field]: value } : variant)),
    );
    setFeedback(null);
    setError(null);
  };

  const addVariant = () => {
    if (!canMutate) return;
    setVariants((current) => [...current, emptyVariantForm()]);
    setFeedback(null);
  };

  const removeVariant = (variant: VariantForm) => {
    if (!canMutate) return;
    setVariants((current) => current.filter((item) => item.rowId !== variant.rowId));
    const variantId = variant.id;
    if (variantId) setDeletedVariantIds((current) => [...current, variantId]);
    setFeedback(null);
  };

  const uploadImages = async (productId: string, files: File[], startSortOrder: number) => {
    const response = await uploadBrandPortalProductImages(productId, imagesFormData(files, startSortOrder));
    setImages((current) => mergeImages(current, response.data));
    return response.data;
  };

  const handleImageSelection = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!canMutate) return;

    const validationError = imageSelectionError(files, imageCount);
    if (validationError) {
      setImageError(validationError);
      return;
    }

    setImageError(null);
    setFeedback(null);

    if (isNew || !productId) {
      setPendingImages((current) => [
        ...current,
        ...files.map((file) => ({
          rowId: nextPendingImageRowId(),
          file,
        })),
      ]);
      return;
    }

    setIsImageUploading(true);
    try {
      await uploadImages(productId, files, imageList.length);
    } catch (requestError) {
      setImageError(errorMessage(requestError));
    } finally {
      setIsImageUploading(false);
    }
  };

  const removePendingImage = (rowId: string) => {
    if (!canMutate) return;
    setPendingImages((current) =>
      current.filter((image) => image.rowId !== rowId),
    );
    setImageError(null);
    setFeedback(null);
  };

  const deleteImage = async (imageId: string) => {
    if (!canMutate || !productId || imageActionId) return;

    setImageActionId(imageId);
    setImageError(null);
    try {
      await deleteBrandPortalProductImage(productId, imageId);
      setImages((current) => sortedImages(current.filter((image) => image.id !== imageId)));
    } catch (requestError) {
      setImageError(errorMessage(requestError));
    } finally {
      setImageActionId(null);
    }
  };

  const moveImage = async (imageId: string, direction: -1 | 1) => {
    if (!canMutate || !productId || isImageReordering) return;

    const currentIndex = imageList.findIndex((image) => image.id === imageId);
    const nextIndex = currentIndex + direction;
    if (currentIndex < 0 || nextIndex < 0 || nextIndex >= imageList.length) return;

    const reordered = imageList.slice();
    [reordered[currentIndex], reordered[nextIndex]] = [reordered[nextIndex], reordered[currentIndex]];

    setIsImageReordering(true);
    setImageError(null);
    try {
      const response = await reorderBrandPortalProductImages(productId, {
        items: reordered.map((image, index) => ({
          image_id: image.id,
          sort_order: index,
        })),
      });
      setImages(sortedImages(response.data));
    } catch (requestError) {
      setImageError(errorMessage(requestError));
    } finally {
      setIsImageReordering(false);
    }
  };

  const saveProduct = async () => {
    if (!canMutate || isSaving) return;

    const validationError = validateForm(form, variants);
    if (validationError) {
      setError(validationError);
      setFeedback(null);
      return;
    }

    setIsSaving(true);
    setError(null);
    setFeedback(null);
    setImageError(null);

    try {
      const payload = productPayload(form);

      if (isNew) {
        const response = await createBrandPortalProduct({
          ...payload,
          variants: variants.map(variantPayload),
        });
        const nextVariants = response.data.variants.map(variantToForm);

        setCreatedProductId(response.data.id);
        setForm(productToForm(response.data));
        setVariants(nextVariants.length > 0 ? nextVariants : [emptyVariantForm()]);
        setOriginalVariants(
          response.data.variants.reduce<Record<string, BrandPortalProductVariantPayload>>((items, variant) => {
            items[variant.id] = variantPayload(variantToForm(variant));
            return items;
          }, {}),
        );
        setImages(sortedImages(response.data.images));
        navigate(`/catalog/${response.data.id}`, { replace: true });

        if (pendingImages.length > 0) {
          try {
            await uploadImages(
              response.data.id,
              pendingImages.map((image) => image.file),
              response.data.images.length,
            );
            setPendingImages([]);
          } catch (requestError) {
            setImageError(
              `Товар сохранён, но изображения не загружены: ${errorMessage(requestError)} Нажмите «Сохранить», чтобы повторить загрузку.`,
            );
            return;
          }
        }
      } else if (productId) {
        await updateBrandPortalProduct(productId, payload);

        for (const variantId of deletedVariantIds) {
          await deleteBrandPortalProductVariant(productId, variantId);
          setDeletedVariantIds((current) => current.filter((item) => item !== variantId));
          setOriginalVariants((current) => {
            const remaining = { ...current };
            delete remaining[variantId];
            return remaining;
          });
        }

        for (const variant of variants) {
          const nextPayload = variantPayload(variant);
          if (!variant.id) {
            const response = await createBrandPortalProductVariant(productId, nextPayload);
            const savedVariant = variantToForm(response.data);

            setVariants((current) =>
              current.map((item) => (item.rowId === variant.rowId ? savedVariant : item)),
            );
            setOriginalVariants((current) => ({
              ...current,
              [response.data.id]: variantPayload(savedVariant),
            }));
            continue;
          }

          const previousPayload = originalVariants[variant.id];
          if (!previousPayload || !sameVariantPayload(previousPayload, nextPayload)) {
            const response = await updateBrandPortalProductVariant(productId, variant.id, nextPayload);
            const savedVariant = variantToForm(response.data);

            setVariants((current) =>
              current.map((item) => (item.rowId === variant.rowId ? savedVariant : item)),
            );
            setOriginalVariants((current) => ({
              ...current,
              [response.data.id]: variantPayload(savedVariant),
            }));
          }
        }

        if (pendingImages.length > 0) {
          await uploadImages(
            productId,
            pendingImages.map((image) => image.file),
            imageList.length,
          );
          setPendingImages([]);
        }
      }

      setFeedback("Сохранено. Возвращаемся в каталог.");
      window.setTimeout(() => navigate("/catalog"), 650);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setIsSaving(false);
    }
  };

  const controlsDisabled = !canMutate || isSaving;
  const imageControlsDisabled =
    !canMutate || isLoading || isSaving || isImageUploading || isImageReordering || Boolean(imageActionId);

  return (
    <section key={productId ?? "new"} className="max-w-[920px] p-4 md:p-8">
      <div className="mb-4 flex items-center gap-2 md:mb-5">
        <Link to="/catalog" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ChevronLeft size={14} strokeWidth={1.5} />
          Каталог
        </Link>
        <span className="text-border">/</span>
        <span className="text-sm text-muted-foreground">{isNew ? "Новый товар" : form.name || "Товар"}</span>
      </div>

      <div className="mb-5 flex flex-wrap items-center justify-between gap-3 md:mb-6">
        <h1 className="text-foreground">{isNew ? "Новый товар" : "Редактировать товар"}</h1>
        <div className="flex gap-2 md:gap-3">
          <Button variant="outline" asChild>
            <Link to="/catalog">
              <X size={14} strokeWidth={1.5} />
              Отмена
            </Link>
          </Button>
          <Button onClick={saveProduct} disabled={controlsDisabled || isLoading || isCategoryLoading}>
            <Save size={14} strokeWidth={1.5} />
            {isSaving ? "Сохраняем" : "Сохранить"}
          </Button>
        </div>
      </div>

      {isLoading && (
        <div className="mb-4 rounded-md border border-border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
          Загружаем товар
        </div>
      )}

      {error && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <span>{error}</span>
          {!isNew && (
            <Button variant="outline" size="sm" onClick={loadProduct}>
              Повторить
            </Button>
          )}
        </div>
      )}

      {feedback && (
        <div className="mb-4 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          {feedback}
        </div>
      )}

      {imageError && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {imageError}
        </div>
      )}

      <Tabs defaultValue="main">
        <TabsList className="mb-5 w-full sm:w-auto md:mb-6">
          <TabsTrigger value="main">Основное</TabsTrigger>
          <TabsTrigger value="variants">Варианты</TabsTrigger>
          <TabsTrigger value="images">Изображения</TabsTrigger>
        </TabsList>

        <TabsContent value="main">
          <div className="space-y-4 md:space-y-5">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label className="text-xs uppercase tracking-wider text-muted-foreground">Name</Label>
                <Input
                  value={form.name}
                  onChange={(event) => updateForm("name", event.target.value)}
                  placeholder="Введите название"
                  disabled={controlsDisabled || isLoading}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs uppercase tracking-wider text-muted-foreground">Slug</Label>
                <Input
                  value={form.slug}
                  onChange={(event) => updateForm("slug", event.target.value)}
                  placeholder="product-slug"
                  disabled={controlsDisabled || isLoading}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label className="text-xs uppercase tracking-wider text-muted-foreground">Category</Label>
                <Select
                  value={form.category_id || undefined}
                  onValueChange={(value) => updateForm("category_id", value)}
                  disabled={controlsDisabled || isCategoryLoading || isLoading}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={isCategoryLoading ? "Загружаем категории" : "Выберите категорию"} />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((category) => (
                      <SelectItem key={category.id} value={category.id}>
                        {category.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs uppercase tracking-wider text-muted-foreground">Status</Label>
                <Select
                  value={form.product_status}
                  onValueChange={(value) => updateForm("product_status", value as ProductStatus)}
                  disabled={controlsDisabled || isLoading}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PRODUCT_STATUSES.map((status) => (
                      <SelectItem key={status} value={status}>
                        <Badge className={PRODUCT_STATUS_COLORS[status]}>{PRODUCT_STATUS_LABELS[status]}</Badge>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-muted-foreground">Description</Label>
              <Textarea
                rows={4}
                value={form.description}
                onChange={(event) => updateForm("description", event.target.value)}
                placeholder="Описание товара"
                disabled={controlsDisabled || isLoading}
              />
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label className="text-xs uppercase tracking-wider text-muted-foreground">Fabric</Label>
                <Textarea
                  rows={3}
                  value={form.fabric_composition}
                  onChange={(event) => updateForm("fabric_composition", event.target.value)}
                  placeholder="Состав"
                  disabled={controlsDisabled || isLoading}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs uppercase tracking-wider text-muted-foreground">Care</Label>
                <Textarea
                  rows={3}
                  value={form.care_instructions}
                  onChange={(event) => updateForm("care_instructions", event.target.value)}
                  placeholder="Уход"
                  disabled={controlsDisabled || isLoading}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="space-y-1.5">
                <Label className="text-xs uppercase tracking-wider text-muted-foreground">Price</Label>
                <Input
                  value={form.base_price_rub}
                  onChange={(event) => updateForm("base_price_rub", event.target.value)}
                  inputMode="decimal"
                  disabled={controlsDisabled || isLoading}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs uppercase tracking-wider text-muted-foreground">Sale Price</Label>
                <Input
                  value={form.sale_price_rub}
                  onChange={(event) => updateForm("sale_price_rub", event.target.value)}
                  inputMode="decimal"
                  disabled={controlsDisabled || isLoading}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs uppercase tracking-wider text-muted-foreground">Season</Label>
                <Input
                  value={form.season}
                  onChange={(event) => updateForm("season", event.target.value)}
                  placeholder="FW26"
                  disabled={controlsDisabled || isLoading}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs uppercase tracking-wider text-muted-foreground">New Arrival</Label>
                <div className="flex h-9 items-center rounded-md border border-input bg-input-background px-3">
                  <Switch
                    checked={form.is_new_arrival}
                    onCheckedChange={(checked) => updateForm("is_new_arrival", checked)}
                    disabled={controlsDisabled || isLoading}
                  />
                </div>
              </div>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="variants">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <span className="text-sm text-muted-foreground">Размеры и цвета · {variants.length} варианта</span>
            <Button variant="outline" size="sm" onClick={addVariant} disabled={controlsDisabled || isLoading}>
              <Plus size={13} strokeWidth={1.5} />
              Add row
            </Button>
          </div>
          <Card className="overflow-x-auto rounded-md">
            <Table className="min-w-[960px]">
              <TableHeader>
                <TableRow className="bg-muted/50 hover:bg-muted/50">
                  <TableHead className="w-8 px-3" />
                  <TableHead className="px-3">Vendor Code</TableHead>
                  <TableHead className="px-3">Size</TableHead>
                  <TableHead className="px-3">Color</TableHead>
                  <TableHead className="px-3">SKU</TableHead>
                  <TableHead className="px-3 text-right">Price</TableHead>
                  <TableHead className="px-3 text-right">Compare</TableHead>
                  <TableHead className="px-3 text-right">Остаток</TableHead>
                  <TableHead className="px-3">Active</TableHead>
                  <TableHead className="w-10 px-3" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {variants.map((variant) => (
                  <TableRow key={variant.rowId}>
                    <TableCell className="px-3 py-2.5">
                      <GripVertical size={13} strokeWidth={1.5} className="text-muted-foreground/40" />
                    </TableCell>
                    <TableCell className="px-3 py-2.5">
                      <Input
                        value={variant.vendor_code}
                        onChange={(event) => updateVariant(variant.rowId, "vendor_code", event.target.value)}
                        className="h-8 px-2 font-mono text-xs"
                        disabled={controlsDisabled || isLoading}
                      />
                    </TableCell>
                    <TableCell className="px-3 py-2.5">
                      <Input
                        value={variant.size}
                        onChange={(event) => updateVariant(variant.rowId, "size", event.target.value)}
                        className="h-8 w-20 px-2 text-xs"
                        disabled={controlsDisabled || isLoading}
                      />
                    </TableCell>
                    <TableCell className="px-3 py-2.5">
                      <Input
                        value={variant.color}
                        onChange={(event) => updateVariant(variant.rowId, "color", event.target.value)}
                        className="h-8 px-2 text-xs"
                        disabled={controlsDisabled || isLoading}
                      />
                    </TableCell>
                    <TableCell className="px-3 py-2.5">
                      <Input
                        value={variant.sku}
                        onChange={(event) => updateVariant(variant.rowId, "sku", event.target.value)}
                        className="h-8 px-2 font-mono text-xs"
                        disabled={controlsDisabled || isLoading}
                      />
                    </TableCell>
                    <TableCell className="px-3 py-2.5">
                      <Input
                        value={variant.price_rub}
                        onChange={(event) => updateVariant(variant.rowId, "price_rub", event.target.value)}
                        inputMode="decimal"
                        className="ml-auto h-8 w-24 px-2 text-right text-xs"
                        disabled={controlsDisabled || isLoading}
                      />
                    </TableCell>
                    <TableCell className="px-3 py-2.5">
                      <Input
                        value={variant.compare_at_price_rub}
                        onChange={(event) => updateVariant(variant.rowId, "compare_at_price_rub", event.target.value)}
                        inputMode="decimal"
                        className="ml-auto h-8 w-24 px-2 text-right text-xs"
                        disabled={controlsDisabled || isLoading}
                      />
                    </TableCell>
                    <TableCell className="px-3 py-2.5">
                      <Input
                        value={variant.stock_quantity}
                        onChange={(event) => updateVariant(variant.rowId, "stock_quantity", event.target.value)}
                        inputMode="numeric"
                        className="ml-auto h-8 w-20 px-2 text-right text-xs"
                        disabled={controlsDisabled || isLoading}
                      />
                    </TableCell>
                    <TableCell className="px-3 py-2.5">
                      <Switch
                        checked={variant.is_active}
                        onCheckedChange={(checked) => updateVariant(variant.rowId, "is_active", checked)}
                        disabled={controlsDisabled || isLoading}
                      />
                    </TableCell>
                    <TableCell className="px-3 py-2.5">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => removeVariant(variant)}
                        disabled={controlsDisabled || isLoading}
                        aria-label="Удалить вариант"
                      >
                        <Trash2 size={12} strokeWidth={1.5} className="text-muted-foreground" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>

        <TabsContent value="images">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <span className="text-sm text-muted-foreground">Изображения · {imageCount}/10</span>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              {isImageUploading && <span>Загружаем</span>}
              {imageActionId && <span>Удаляем</span>}
              {isImageReordering && <span>Сохраняем порядок</span>}
              {pendingImages.length > 0 && <span>Ожидают сохранения: {pendingImages.length}</span>}
            </div>
          </div>
          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {imageList.map((image, index) => (
              <div key={image.id} className="group relative aspect-[3/4] overflow-hidden rounded-md border-2 border-border bg-muted">
                <img
                  src={image.url}
                  alt={image.alt_text ?? form.name}
                  className="h-full w-full object-cover"
                />
                {index === 0 && (
                  <Badge className="absolute bottom-0 left-0 right-0 justify-center rounded-none text-[9px]">
                    Главное
                  </Badge>
                )}
                {canMutate && (
                  <div className="absolute right-1 top-1 flex gap-1 rounded-md bg-background/90 p-1 opacity-100 shadow-sm sm:opacity-0 sm:transition-opacity sm:group-hover:opacity-100">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => moveImage(image.id, -1)}
                      disabled={imageControlsDisabled || index === 0}
                      aria-label="Поднять изображение"
                    >
                      <ArrowUp size={12} strokeWidth={1.5} />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => moveImage(image.id, 1)}
                      disabled={imageControlsDisabled || index === imageList.length - 1}
                      aria-label="Опустить изображение"
                    >
                      <ArrowDown size={12} strokeWidth={1.5} />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => deleteImage(image.id)}
                      disabled={imageControlsDisabled}
                      aria-label="Удалить изображение"
                    >
                      <Trash2 size={12} strokeWidth={1.5} className="text-muted-foreground" />
                    </Button>
                  </div>
                )}
              </div>
            ))}
            {pendingImages.map((image) => (
              <div
                key={image.rowId}
                className="relative flex aspect-[3/4] flex-col justify-between overflow-hidden rounded-md border-2 border-dashed border-border bg-muted/50 p-3"
              >
                <div>
                  <Badge className="mb-2 bg-muted-foreground text-background">Новый</Badge>
                  <p className="break-words text-xs text-foreground">{image.file.name}</p>
                </div>
                <p className="text-xs text-muted-foreground">{Math.round(image.file.size / 1024)} КБ</p>
                {canMutate && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="absolute right-1 top-1 h-7 w-7 bg-background/90"
                    onClick={() => removePendingImage(image.rowId)}
                    disabled={imageControlsDisabled}
                    aria-label="Убрать выбранное изображение"
                  >
                    <Trash2 size={12} strokeWidth={1.5} className="text-muted-foreground" />
                  </Button>
                )}
              </div>
            ))}
            <label
              className={`flex aspect-[3/4] flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed border-border ${
                imageControlsDisabled || imageCount >= MAX_PRODUCT_IMAGES ? "cursor-not-allowed opacity-60" : "cursor-pointer"
              }`}
            >
              <ImagePlus size={20} strokeWidth={1.5} className="text-muted-foreground/50" />
              <span className="px-2 text-center text-xs text-muted-foreground">Добавить</span>
              <input
                type="file"
                accept="image/png,image/jpeg"
                multiple
                className="sr-only"
                disabled={imageControlsDisabled || imageCount >= MAX_PRODUCT_IMAGES}
                onChange={handleImageSelection}
              />
            </label>
          </div>
          <label
            className={`flex flex-col items-center justify-center gap-3 rounded-md border-2 border-dashed border-border bg-muted/30 p-6 md:p-8 ${
              imageControlsDisabled || imageCount >= MAX_PRODUCT_IMAGES ? "cursor-not-allowed opacity-60" : "cursor-pointer"
            }`}
          >
            <ImagePlus size={24} strokeWidth={1.5} className="text-muted-foreground/50" />
            <span className="text-center text-sm text-muted-foreground">Выберите файлы</span>
            <span className="text-center text-xs text-muted-foreground/70">JPG, PNG · не более 5 МБ</span>
            <input
              type="file"
              accept="image/png,image/jpeg"
              multiple
              className="sr-only"
              disabled={imageControlsDisabled || imageCount >= MAX_PRODUCT_IMAGES}
              onChange={handleImageSelection}
            />
          </label>
        </TabsContent>
      </Tabs>
    </section>
  );
}
