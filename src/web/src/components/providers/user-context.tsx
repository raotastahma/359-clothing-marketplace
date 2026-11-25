"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  clearAuthTokens,
  getStoredAccessToken,
  requestJson,
  type Address as ApiAddress,
  type AddressesApiResponse,
  type FavoritesApiResponse,
  type OrderStatus as ApiOrderStatus,
  type OrderSummary as ApiOrderSummary,
  type OrdersApiResponse,
  type ProductApiResponse,
  type UpdateUserRequest,
  type User as ApiUser,
  type UserApiResponse,
} from "@/src/lib/api";
import { productDetailToUiProduct, productListItemToUiProduct } from "@/src/lib/product-adapter";
import type { Product } from "@/src/types/product";

import type { CartItem } from "./cart-context";

export interface UserProfile {
  id?: string;
  phone: string;
  name: string;
  email?: string | null;
  isVerified?: boolean;
  pdConsent: boolean;
  marketingConsent: boolean;
}

export interface OrderAddress {
  name: string;
  phone: string;
  city: string;
  street: string;
  zip: string;
}

export interface OrderParcel {
  id: string;
  brandName: string;
  status: ApiOrderStatus;
  trackingNumber: string | null;
  itemsCount: number;
}

export interface Order {
  id: string;
  createdAt: string;
  items: CartItem[];
  total: number;
  address?: OrderAddress;
  deliveryMethod?: "courier" | "pickup";
  paymentMethod?: "card_online" | "sbp";
  status: ApiOrderStatus | "confirmed";
  estimatedDelivery?: string;
  parcels?: OrderParcel[];
}

interface UserContextValue {
  user: UserProfile | null;
  favorites: string[];
  favoriteProducts: Product[];
  orders: Order[];
  addresses: ApiAddress[];
  isAccountLoading: boolean;
  accountError: string | null;
  recentlyViewed: Product[];
  login: (user: UserProfile) => void;
  logout: () => void;
  toggleFavorite: (productId: string, productApiId?: string, product?: Product) => void;
  updateProfile: (name: string) => Promise<void>;
  deleteAddress: (addressId: string) => Promise<void>;
  addToRecentlyViewed: (product: Product) => void;
}

const UserContext = createContext<UserContextValue | null>(null);
const RECENTLY_VIEWED_KEY = "359-recently-viewed-product-ids";

interface UserProviderProps {
  children: React.ReactNode;
}

function userProfileFromApi(user: ApiUser): UserProfile {
  return {
    id: user.id,
    phone: user.phone,
    name: user.name ?? "Гость",
    email: user.email,
    isVerified: user.is_verified,
    pdConsent: false,
    marketingConsent: false,
  };
}

function formatOrderDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
}

function orderFromApi(order: ApiOrderSummary): Order {
  return {
    id: order.id,
    createdAt: formatOrderDate(order.created_at),
    items: [],
    total: order.total_amount,
    status: order.status,
    parcels: order.sub_orders.map((subOrder) => ({
      id: subOrder.id,
      brandName: subOrder.brand_name,
      status: subOrder.status,
      trackingNumber: subOrder.tracking_number,
      itemsCount: subOrder.items_count,
    })),
  };
}

function canUseStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function readRecentlyViewedIds(): string[] {
  if (!canUseStorage()) return [];

  try {
    const value = window.localStorage.getItem(RECENTLY_VIEWED_KEY);
    const ids: unknown = value ? JSON.parse(value) : [];
    return Array.isArray(ids) ? ids.filter((id): id is string => typeof id === "string") : [];
  } catch {
    return [];
  }
}

function writeRecentlyViewedIds(ids: string[]): void {
  if (!canUseStorage()) return;
  try {
    window.localStorage.setItem(RECENTLY_VIEWED_KEY, JSON.stringify(ids.slice(0, 6)));
  } catch {
    // Recently viewed is best-effort UI state.
  }
}

export function UserProvider({ children }: UserProviderProps) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [favorites, setFavorites] = useState<string[]>([]);
  const [favoriteProducts, setFavoriteProducts] = useState<Product[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [addresses, setAddresses] = useState<ApiAddress[]>([]);
  const [isAccountLoading, setAccountLoading] = useState<boolean>(() =>
    Boolean(getStoredAccessToken()),
  );
  const [accountError, setAccountError] = useState<string | null>(null);
  const [recentlyViewed, setRecentlyViewed] = useState<Product[]>([]);

  const loadAccountData = useCallback(async (isCurrent: () => boolean = () => true) => {
    setAccountLoading(true);
    setAccountError(null);

    await requestJson<UserApiResponse>("/users/me", { redirectOnUnauthorized: false })
      .then(async ({ data }) => {
        if (!isCurrent()) return;
        setUser(userProfileFromApi(data));

        const [ordersResult, favoritesResult, addressesResult] = await Promise.allSettled([
          requestJson<OrdersApiResponse>("/orders", { redirectOnUnauthorized: false }),
          requestJson<FavoritesApiResponse>("/users/me/favorites", {
            redirectOnUnauthorized: false,
          }),
          requestJson<AddressesApiResponse>("/users/me/addresses", {
            redirectOnUnauthorized: false,
          }),
        ]);

        if (!isCurrent()) return;

        if (ordersResult.status === "fulfilled") {
          setOrders(ordersResult.value.data.map(orderFromApi));
        }

        if (favoritesResult.status === "fulfilled") {
          const nextProducts = favoritesResult.value.data.map(productListItemToUiProduct);
          setFavoriteProducts(nextProducts);
          setFavorites(nextProducts.map((product) => product.id));
        }

        if (addressesResult.status === "fulfilled") {
          setAddresses(addressesResult.value.data);
        }

        if (
          ordersResult.status === "rejected" ||
          favoritesResult.status === "rejected" ||
          addressesResult.status === "rejected"
        ) {
          setAccountError("Не удалось загрузить часть данных аккаунта.");
        }
      })
      .catch(() => {
        if (!isCurrent()) return;
        clearAuthTokens();
        setUser(null);
        setFavorites([]);
        setFavoriteProducts([]);
        setOrders([]);
        setAddresses([]);
        setAccountError("Не удалось загрузить профиль.");
      })
      .finally(() => {
        if (isCurrent()) setAccountLoading(false);
      });
  }, []);

  useEffect(() => {
    let isMounted = true;

    if (!getStoredAccessToken()) return undefined;

    Promise.resolve().then(() => {
      if (isMounted) void loadAccountData(() => isMounted);
    });

    return () => {
      isMounted = false;
    };
  }, [loadAccountData]);

  useEffect(() => {
    let isMounted = true;
    const ids = readRecentlyViewedIds();
    if (ids.length === 0) return undefined;

    Promise.allSettled(
      ids.map((slug) =>
        requestJson<ProductApiResponse>(`/products/${encodeURIComponent(slug)}`, {
          redirectOnUnauthorized: false,
        }),
      ),
    ).then((results) => {
      if (!isMounted) return;
      const hydratedProducts = results.flatMap((result) =>
        result.status === "fulfilled" ? [productDetailToUiProduct(result.value.data)] : [],
      );
      setRecentlyViewed((prev) => {
        const mergedProducts = [
          ...prev,
          ...hydratedProducts.filter((product) => !prev.some((item) => item.id === product.id)),
        ].slice(0, 6);
        writeRecentlyViewedIds(mergedProducts.map((product) => product.id));
        return mergedProducts;
      });
    });

    return () => {
      isMounted = false;
    };
  }, []);

  const login = useCallback((nextUser: UserProfile): void => {
    setUser(nextUser);
    if (getStoredAccessToken()) void loadAccountData();
  }, [loadAccountData]);

  const logout = useCallback((): void => {
    clearAuthTokens();
    setUser(null);
    setFavorites([]);
    setFavoriteProducts([]);
    setOrders([]);
    setAddresses([]);
  }, []);

  const toggleFavorite = useCallback((
    productId: string,
    productApiId?: string,
    product?: Product,
  ): void => {
    const wasFavorite = favorites.includes(productId);
    const favoriteProductId = productApiId ?? productId;

    setFavorites((prev) =>
      prev.includes(productId)
        ? prev.filter((value) => value !== productId)
        : [...prev, productId],
    );

    setFavoriteProducts((prev) => {
      if (wasFavorite) return prev.filter((item) => item.id !== productId);
      if (!product || prev.some((item) => item.id === product.id)) return prev;
      return [product, ...prev];
    });

    requestJson<unknown>(`/users/me/favorites/${encodeURIComponent(favoriteProductId)}`, {
      method: wasFavorite ? "DELETE" : "POST",
    }).catch(() => {
      setFavorites((prev) =>
        wasFavorite
          ? prev.includes(productId)
            ? prev
            : [...prev, productId]
          : prev.filter((value) => value !== productId),
      );
      setFavoriteProducts((prev) => {
        if (!wasFavorite) return prev.filter((item) => item.id !== productId);
        if (!product || prev.some((item) => item.id === product.id)) return prev;
        return [product, ...prev];
      });
    });
  }, [favorites]);

  const updateProfile = useCallback(async (name: string): Promise<void> => {
    const body = { name } satisfies UpdateUserRequest;
    const { data } = await requestJson<UserApiResponse>("/users/me", {
      method: "PATCH",
      body,
    });
    setUser(userProfileFromApi(data));
  }, []);

  const deleteAddress = useCallback(async (addressId: string): Promise<void> => {
    await requestJson<unknown>(`/users/me/addresses/${encodeURIComponent(addressId)}`, {
      method: "DELETE",
    });
    setAddresses((prev) => prev.filter((address) => address.id !== addressId));
  }, []);

  const addToRecentlyViewed = useCallback((product: Product): void => {
    setRecentlyViewed((prev) => {
      const filtered = prev.filter((item) => item.id !== product.id);
      const nextProducts = [product, ...filtered].slice(0, 6);
      writeRecentlyViewedIds(nextProducts.map((item) => item.id));
      return nextProducts;
    });
  }, []);

  const value = useMemo<UserContextValue>(
    () => ({
      user,
      favorites,
      favoriteProducts,
      orders,
      addresses,
      isAccountLoading,
      accountError,
      recentlyViewed,
      login,
      logout,
      toggleFavorite,
      updateProfile,
      deleteAddress,
      addToRecentlyViewed,
    }),
    [
      accountError,
      addToRecentlyViewed,
      addresses,
      deleteAddress,
      favoriteProducts,
      favorites,
      isAccountLoading,
      login,
      logout,
      orders,
      recentlyViewed,
      toggleFavorite,
      updateProfile,
      user,
    ],
  );

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}

export function useUser(): UserContextValue {
  const context = useContext(UserContext);
  if (!context) throw new Error("useUser must be used inside UserProvider");
  return context;
}
