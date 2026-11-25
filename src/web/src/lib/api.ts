import { redirect } from "next/navigation";

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

export interface ValidationError {
  field: string;
  message: string;
}

export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: ValidationError[];
  };
}

export class ApiError extends Error {
  code: string;
  status?: number;
  details: ValidationError[];
  response?: ErrorResponse;

  constructor(
    message: string,
    {
      code,
      status,
      details = [],
      response,
      cause,
    }: {
      code: string;
      status?: number;
      details?: ValidationError[];
      response?: ErrorResponse;
      cause?: unknown;
    },
  ) {
    super(message, { cause });
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
    this.response = response;
  }
}

export type Gender = "men" | "women" | "unisex";
export type OrderStatus =
  | "pending"
  | "paid"
  | "processing"
  | "shipped"
  | "delivered"
  | "completed"
  | "cancelled_by_buyer"
  | "cancelled_by_brand"
  | "returned";
export type DeliveryProvider = "yandex_delivery";
export type DeliveryMethod = "pickup_point" | "courier";

export interface SendCodeResponse {
  message: string;
  expires_in: number;
}

export interface User {
  id: string;
  phone: string;
  name: string | null;
  email: string | null;
  is_verified: boolean;
  created_at?: string;
}

export interface VerifyCodeResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
}

export interface RefreshTokenResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

export interface ProductBrand {
  id: string;
  name: string;
  slug: string;
  logo_url?: string;
}

export interface ProductCategory {
  id: string;
  name: string;
  slug: string;
  gender?: Gender | null;
  parent?: {
    name: string;
    slug: string;
  };
}

export interface ProductImage {
  url: string;
  alt_text: string | null;
  sort_order?: number;
}

export interface ProductVariant {
  id: string;
  size: string;
  color: string | null;
  sku: string;
  price_rub: number;
  compare_at_price_rub: number | null;
  stock_quantity: number;
  is_active: boolean;
}

export interface ProductListItem {
  id: string;
  name: string;
  slug: string;
  brand: ProductBrand;
  category: ProductCategory;
  price_from: number | null;
  compare_at_price_from: number | null;
  is_new_arrival: boolean;
  images: ProductImage[];
  available_sizes: string[];
}

export interface Product extends ProductListItem {
  description: string | null;
  fabric_composition?: string | null;
  care_instructions?: string | null;
  season?: string | null;
  base_price_rub?: number | null;
  sale_price_rub?: number | null;
  variants: ProductVariant[];
  is_active: boolean;
  created_at: string;
}

export interface Brand {
  id: string;
  name: string;
  slug: string;
  logo_url: string | null;
  cover_url: string | null;
  founded_year: number | null;
  products_count: number;
}

export interface CartProductVariant {
  id: string;
  product_id?: string;
  product_name: string;
  product_slug: string;
  vendor_code?: string | null;
  sku?: string;
  size: string;
  color?: string | null;
  price_rub: number;
  compare_at_price_rub?: number | null;
  image_url: string | null;
  stock_quantity: number;
  brand_name: string;
}

export interface CartItem {
  id: string;
  product_variant: CartProductVariant;
  quantity: number;
}

export interface Cart {
  items: CartItem[];
  total: number;
  items_count: number;
}

export interface CreateOrderRequest {
  address_id: string;
  delivery_provider: DeliveryProvider;
  delivery_method: DeliveryMethod;
  comment?: string;
}

export interface OrderItem {
  id: string;
  product_name: string;
  product_slug: string;
  brand_name: string;
  size: string;
  quantity: number;
  price_rub: number;
  image_url: string | null;
}

export interface SubOrder {
  id: string;
  brand_name: string;
  status: OrderStatus;
  tracking_number: string | null;
  items_count: number;
  items?: OrderItem[];
}

export interface OrderSummary {
  id: string;
  status: OrderStatus;
  total_amount: number;
  customer_delivery_cost: number;
  created_at: string;
  sub_orders: SubOrder[];
}

export interface Order extends OrderSummary {
  items: OrderItem[];
  delivery_address?: Record<string, object> | null;
  address?: Address;
  payment_url?: string;
}

export interface CreateOrderResponse {
  id: string;
  status: OrderStatus;
  total_amount: number;
  customer_delivery_cost: number;
  items: OrderItem[];
  payment_url: string;
}

export interface UpdateUserRequest {
  name?: string;
  email?: string;
}

export interface Address {
  id: string;
  city: string;
  street: string;
  apartment: string | null;
  postal_code: string;
  is_default: boolean;
}

export interface AddressRequest {
  city: string;
  street: string;
  apartment?: string;
  postal_code?: string;
  is_default?: boolean;
}

export interface Category {
  id: string;
  name: string;
  slug: string;
  gender: Gender;
  sort_order: number;
  children: Category[];
}

export type SendCodeApiResponse = ApiResponse<SendCodeResponse>;
export type VerifyCodeApiResponse = ApiResponse<VerifyCodeResponse>;
export type RefreshTokenApiResponse = ApiResponse<RefreshTokenResponse>;
export type ProductsApiResponse = PaginatedApiResponse<ProductListItem>;
export type ProductApiResponse = ApiResponse<Product>;
export type BrandsApiResponse = ApiResponse<Brand[]>;
export type CartApiResponse = ApiResponse<Cart>;
export type CreateOrderApiResponse = ApiResponse<CreateOrderResponse>;
export type OrdersApiResponse = PaginatedApiResponse<OrderSummary>;
export type OrderApiResponse = ApiResponse<Order>;
export type UserApiResponse = ApiResponse<User>;
export type AddressesApiResponse = ApiResponse<Address[]>;
export type AddressApiResponse = ApiResponse<Address>;
export type FavoritesApiResponse = ProductsApiResponse;
export type CategoriesApiResponse = ApiResponse<Category[]>;

export type JsonBody = Record<string, unknown> | unknown[];

export interface RequestJsonOptions extends Omit<RequestInit, "body"> {
  body?: BodyInit | JsonBody | null;
  redirectOnUnauthorized?: boolean;
  skipAuthRefresh?: boolean;
}

export const ACCESS_TOKEN_KEY = "359-access-token";
export const REFRESH_TOKEN_KEY = "359-refresh-token";

function canUseStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function getStoredAccessToken(): string | null {
  if (!canUseStorage()) return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

function getStoredRefreshToken(): string | null {
  if (!canUseStorage()) return null;
  return window.localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setAuthTokens(tokens: RefreshTokenResponse): void {
  if (!canUseStorage()) return;
  window.localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
}

export function clearAuthTokens(): void {
  if (!canUseStorage()) return;
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}

function isErrorResponse(value: unknown): value is ErrorResponse {
  if (!value || typeof value !== "object" || !("error" in value)) return false;

  const error = (value as { error: unknown }).error;
  return (
    !!error &&
    typeof error === "object" &&
    "code" in error &&
    "message" in error &&
    typeof (error as { code: unknown }).code === "string" &&
    typeof (error as { message: unknown }).message === "string"
  );
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

function apiUrl(url: string): string {
  if (/^https?:\/\//.test(url)) return url;

  const baseUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "");
  if (!baseUrl) {
    throw new ApiError("API URL is not configured.", {
      code: "API_URL_MISSING",
    });
  }

  return `${baseUrl}/${url.replace(/^\/+/, "")}`;
}

function redirectToLogin(): void {
  if (typeof window === "undefined") {
    redirect("/login");
  }

  if (window.location.pathname === "/login") return;
  window.location.assign("/login");
}

function requestBody(body: RequestJsonOptions["body"]): BodyInit | null | undefined {
  if (body == null || isBodyInit(body)) return body;
  return JSON.stringify(body);
}

function requestHeaders(
  headers: RequestJsonOptions["headers"],
  body: RequestJsonOptions["body"],
): Headers {
  const nextHeaders = new Headers(headers);

  if (!nextHeaders.has("Accept")) {
    nextHeaders.set("Accept", "application/json");
  }

  if (body !== undefined && !(body instanceof FormData) && !nextHeaders.has("Content-Type")) {
    nextHeaders.set("Content-Type", "application/json");
  }

  const accessToken = getStoredAccessToken();
  if (accessToken && !nextHeaders.has("Authorization")) {
    nextHeaders.set("Authorization", `Bearer ${accessToken}`);
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
  if (isErrorResponse(payload)) {
    return new ApiError(payload.error.message, {
      code: payload.error.code,
      status,
      details: payload.error.details,
      response: payload,
    });
  }

  return new ApiError("Не удалось выполнить запрос. Попробуйте ещё раз.", {
    code: "HTTP_ERROR",
    status,
  });
}

async function refreshAuthTokens(): Promise<boolean> {
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) return false;

  try {
    const response = await fetch(apiUrl("/auth/refresh"), {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
    });

    const payload = (await parseJson(response)) as RefreshTokenApiResponse | null;
    if (!response.ok || !payload?.data) {
      clearAuthTokens();
      return false;
    }

    setAuthTokens(payload.data);
    return true;
  } catch {
    clearAuthTokens();
    return false;
  }
}

export function getValidationErrorMessages(error: unknown): string[] {
  if (!(error instanceof ApiError)) return [];
  if (error.status !== 422 && error.code !== "VALIDATION_ERROR") return [];

  if (error.details.length === 0) return [error.message];
  return error.details.map((detail) => detail.message);
}

export async function requestJson<T>(
  url: string,
  {
    body,
    headers,
    redirectOnUnauthorized = true,
    skipAuthRefresh = false,
    ...init
  }: RequestJsonOptions = {},
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(apiUrl(url), {
      ...init,
      body: requestBody(body),
      headers: requestHeaders(headers, body),
    });
  } catch (error) {
    if (error instanceof ApiError) throw error;

    throw new ApiError("Не удалось подключиться к серверу. Проверьте соединение.", {
      code: "NETWORK_ERROR",
      cause: error,
    });
  }

  let payload = await parseJson(response);

  if (response.status === 401 && !skipAuthRefresh) {
    const didRefresh = await refreshAuthTokens();
    if (didRefresh) {
      response = await fetch(apiUrl(url), {
        ...init,
        body: requestBody(body),
        headers: requestHeaders(headers, body),
      });
      payload = await parseJson(response);
    }
  }

  if (!response.ok) {
    const error = apiErrorFromResponse(response.status, payload);

    if (response.status === 401 && redirectOnUnauthorized) {
      redirectToLogin();
    }

    throw error;
  }

  return payload as T;
}
