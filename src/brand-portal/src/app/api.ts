export interface ApiMeta {
  page: number;
  per_page: number;
  total: number;
}

export interface ApiResponse<T> {
  data: T;
}

export interface PaginatedApiResponse<T> extends ApiResponse<T[]> {
  meta: ApiMeta;
}

export interface ErrorResponse {
  error?: {
    code?: string;
    message?: string;
  };
  detail?: string;
}

export type ProductStatus = "active" | "hidden" | "archived";

export interface BrandPortalProductVariant {
  id: string;
  vendor_code: string | null;
  size: string;
  color: string | null;
  sku: string;
  price_rub: number | null;
  compare_at_price_rub: number | null;
  stock_quantity: number;
  is_active: boolean;
}

export interface BrandPortalProductImage {
  id: string;
  url: string;
  sort_order: number;
  alt_text: string | null;
}

export interface BrandPortalProduct {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  fabric_composition: string | null;
  care_instructions: string | null;
  season: string | null;
  base_price_rub: number | null;
  sale_price_rub: number | null;
  product_status: ProductStatus;
  is_active: boolean;
  is_new_arrival: boolean;
  created_at: string;
  brand: {
    id: string;
    name: string;
    slug: string;
    logo_url: string | null;
  };
  category: {
    id: string;
    name: string;
    slug: string;
    gender: string;
    parent: unknown;
  };
  variants: BrandPortalProductVariant[];
  images: BrandPortalProductImage[];
}

export interface BrandPortalProductsParams {
  status?: ProductStatus;
  category?: string;
  season?: string;
  page?: number;
  per_page?: number;
}

export interface BrandPortalProductVariantPayload {
  vendor_code: string | null;
  size: string;
  color: string | null;
  sku: string;
  price_rub: number;
  compare_at_price_rub: number | null;
  stock_quantity: number;
  is_active: boolean;
}

export interface BrandPortalProductPayload {
  name: string;
  slug: string | null;
  description: string | null;
  fabric_composition: string | null;
  care_instructions: string | null;
  category_id: string;
  season: string | null;
  base_price_rub: number | null;
  sale_price_rub: number | null;
  product_status: ProductStatus;
  is_active: boolean;
  is_new_arrival: boolean;
}

export interface BrandPortalProductCreatePayload extends BrandPortalProductPayload {
  variants: BrandPortalProductVariantPayload[];
}

export interface BrandPortalProductImageReorderItem {
  image_id: string;
  sort_order: number;
}

export interface BrandPortalProductImageReorderPayload {
  items: BrandPortalProductImageReorderItem[];
}

export interface CategoryTreeItem {
  id: string;
  name: string;
  slug: string;
  gender: string;
  sort_order: number;
  children: CategoryTreeItem[];
}

export class ApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export const ACCESS_TOKEN_KEY = "359-access-token";

type JsonBody = object;
type UnauthorizedHandler = () => void;

interface RequestJsonOptions extends Omit<RequestInit, "body"> {
  body?: BodyInit | JsonBody | null;
  auth?: boolean;
  recoverUnauthorized?: boolean;
}

let unauthorizedHandler: UnauthorizedHandler | null = null;

function apiUrl(url: string): string {
  if (/^https?:\/\//.test(url)) return url;

  const baseUrl = import.meta.env.VITE_API_URL?.replace(/\/+$/, "");
  if (!baseUrl) {
    throw new ApiError("API URL is not configured.");
  }

  return `${baseUrl}/${url.replace(/^\/+/, "")}`;
}

function canUseStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function getStoredAccessToken(): string | null {
  if (!canUseStorage()) return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function hasStoredAccessToken(): boolean {
  return Boolean(getStoredAccessToken());
}

export function storeBrandAccessToken(accessToken: string): void {
  if (!canUseStorage()) return;
  window.localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
}

export function clearBrandTokens(): void {
  if (!canUseStorage()) return;
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
}

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): () => void {
  unauthorizedHandler = handler;
  return () => {
    if (unauthorizedHandler === handler) unauthorizedHandler = null;
  };
}

function isBodyInit(value: unknown): value is BodyInit {
  return (
    typeof value === "string" ||
    value instanceof Blob ||
    value instanceof FormData ||
    value instanceof URLSearchParams ||
    value instanceof ArrayBuffer ||
    ArrayBuffer.isView(value) ||
    value instanceof ReadableStream
  );
}

function requestBody(body: RequestJsonOptions["body"]): BodyInit | null | undefined {
  if (body == null || isBodyInit(body)) return body;
  return JSON.stringify(body);
}

function requestHeaders(
  headers: RequestJsonOptions["headers"],
  body: RequestJsonOptions["body"],
  auth: boolean,
): Headers {
  const nextHeaders = new Headers(headers);

  if (!nextHeaders.has("Accept")) {
    nextHeaders.set("Accept", "application/json");
  }

  if (body !== undefined && !(body instanceof FormData) && !nextHeaders.has("Content-Type")) {
    nextHeaders.set("Content-Type", "application/json");
  }

  if (auth) {
    const accessToken = getStoredAccessToken();
    if (accessToken && !nextHeaders.has("Authorization")) {
      nextHeaders.set("Authorization", `Bearer ${accessToken}`);
    }
  }

  return nextHeaders;
}

async function parseJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;

  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function apiErrorFromResponse(status: number, payload: unknown): ApiError {
  if (payload && typeof payload === "object") {
    const response = payload as ErrorResponse;
    const message = response.error?.message ?? response.detail;
    if (message) return new ApiError(message, status);
  }

  return new ApiError("Не удалось выполнить запрос. Попробуйте ещё раз.", status);
}

export async function requestJson<T>(
  url: string,
  { auth = true, body, headers, recoverUnauthorized = true, ...init }: RequestJsonOptions = {},
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(apiUrl(url), {
      ...init,
      body: requestBody(body),
      headers: requestHeaders(headers, body, auth),
    });
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError("Не удалось подключиться к серверу. Проверьте соединение.");
  }

  const payload = await parseJson(response);

  if (!response.ok) {
    const error = apiErrorFromResponse(response.status, payload);
    if (response.status === 401 && recoverUnauthorized) {
      unauthorizedHandler?.();
    }
    throw error;
  }

  return payload as T;
}

export function getBrandPortalProducts(
  params: BrandPortalProductsParams,
): Promise<PaginatedApiResponse<BrandPortalProduct>> {
  const searchParams = new URLSearchParams();

  if (params.status) searchParams.set("status", params.status);
  if (params.category) searchParams.set("category", params.category);
  if (params.season) searchParams.set("season", params.season);
  if (params.page) searchParams.set("page", String(params.page));
  if (params.per_page) searchParams.set("per_page", String(params.per_page));

  const query = searchParams.toString();
  return requestJson<PaginatedApiResponse<BrandPortalProduct>>(
    `/brand-portal/products${query ? `?${query}` : ""}`,
  );
}

export function getBrandPortalProduct(id: string): Promise<ApiResponse<BrandPortalProduct>> {
  return requestJson<ApiResponse<BrandPortalProduct>>(`/brand-portal/products/${id}`);
}

export function createBrandPortalProduct(
  payload: BrandPortalProductCreatePayload,
): Promise<ApiResponse<BrandPortalProduct>> {
  return requestJson<ApiResponse<BrandPortalProduct>>("/brand-portal/products", {
    method: "POST",
    body: payload,
  });
}

export function updateBrandPortalProduct(
  id: string,
  payload: BrandPortalProductPayload,
): Promise<ApiResponse<BrandPortalProduct>> {
  return requestJson<ApiResponse<BrandPortalProduct>>(`/brand-portal/products/${id}`, {
    method: "PATCH",
    body: payload,
  });
}

export function archiveBrandPortalProduct(id: string): Promise<ApiResponse<BrandPortalProduct>> {
  return requestJson<ApiResponse<BrandPortalProduct>>(`/brand-portal/products/${id}`, {
    method: "DELETE",
  });
}

export function createBrandPortalProductVariant(
  productId: string,
  payload: BrandPortalProductVariantPayload,
): Promise<ApiResponse<BrandPortalProductVariant>> {
  return requestJson<ApiResponse<BrandPortalProductVariant>>(
    `/brand-portal/products/${productId}/variants`,
    {
      method: "POST",
      body: payload,
    },
  );
}

export function updateBrandPortalProductVariant(
  productId: string,
  variantId: string,
  payload: BrandPortalProductVariantPayload,
): Promise<ApiResponse<BrandPortalProductVariant>> {
  return requestJson<ApiResponse<BrandPortalProductVariant>>(
    `/brand-portal/products/${productId}/variants/${variantId}`,
    {
      method: "PATCH",
      body: payload,
    },
  );
}

export function deleteBrandPortalProductVariant(productId: string, variantId: string): Promise<void> {
  return requestJson<void>(`/brand-portal/products/${productId}/variants/${variantId}`, {
    method: "DELETE",
  });
}

export function uploadBrandPortalProductImages(
  productId: string,
  formData: FormData,
): Promise<ApiResponse<BrandPortalProductImage[]>> {
  return requestJson<ApiResponse<BrandPortalProductImage[]>>(
    `/brand-portal/products/${productId}/images`,
    {
      method: "POST",
      body: formData,
    },
  );
}

export function deleteBrandPortalProductImage(productId: string, imageId: string): Promise<void> {
  return requestJson<void>(`/brand-portal/products/${productId}/images/${imageId}`, {
    method: "DELETE",
  });
}

export function reorderBrandPortalProductImages(
  productId: string,
  payload: BrandPortalProductImageReorderPayload,
): Promise<ApiResponse<BrandPortalProductImage[]>> {
  return requestJson<ApiResponse<BrandPortalProductImage[]>>(
    `/brand-portal/products/${productId}/images/reorder`,
    {
      method: "PATCH",
      body: payload,
    },
  );
}

export function getCategories(): Promise<ApiResponse<CategoryTreeItem[]>> {
  return requestJson<ApiResponse<CategoryTreeItem[]>>("/categories", { auth: false });
}
