"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import type { Product } from "@/src/types/product";

export type { Product };

export interface CartItem {
  cartItemId?: string;
  product: Product;
  size: string;
  quantity: number;
}

interface CartContextValue {
  cartItems: CartItem[];
  isCartOpen: boolean;
  cartCount: number;
  cartTotal: number;
  addToCart: (product: Product, size: string) => Promise<void>;
  removeFromCart: (productId: string, size: string) => void;
  updateQuantity: (productId: string, size: string, quantity: number) => void;
  clearCart: () => void;
  setCartOpen: (open: boolean) => void;
}

const CartContext = createContext<CartContextValue | null>(null);

interface CartProviderProps {
  children: React.ReactNode;
}

const CART_STORAGE_KEY = "359-cart";

function canUseStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function isStoredCartItem(value: unknown): value is CartItem {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<CartItem>;
  return (
    !!item.product &&
    typeof item.product.id === "string" &&
    typeof item.product.brand === "string" &&
    typeof item.product.name === "string" &&
    typeof item.product.price === "number" &&
    Array.isArray(item.product.images) &&
    typeof item.size === "string" &&
    typeof item.quantity === "number"
  );
}

function readStoredCart(): CartItem[] {
  if (!canUseStorage()) return [];

  try {
    const value = window.localStorage.getItem(CART_STORAGE_KEY);
    const parsed: unknown = value ? JSON.parse(value) : [];
    return Array.isArray(parsed) ? parsed.filter(isStoredCartItem) : [];
  } catch {
    return [];
  }
}

function writeStoredCart(items: CartItem[]): void {
  if (!canUseStorage()) return;
  try {
    window.localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(items));
  } catch {
    // Cart persistence is best-effort client state.
  }
}

export function CartProvider({ children }: CartProviderProps) {
  const [cartItems, setCartItems] = useState<CartItem[]>([]);
  const [isCartOpen, setCartOpen] = useState<boolean>(false);
  const [hasLoadedCart, setHasLoadedCart] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;

    queueMicrotask(() => {
      if (!isMounted) return;
      setCartItems(readStoredCart());
      setHasLoadedCart(true);
    });

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (hasLoadedCart) writeStoredCart(cartItems);
  }, [cartItems, hasLoadedCart]);

  const addToCart = useCallback(async (product: Product, size: string): Promise<void> => {
    const productVariantId = product.variantIdsBySize?.[size];
    if (!productVariantId) {
      throw new Error("Не удалось определить вариант товара.");
    }

    setCartItems((prev) => {
      const existingItem = prev.find(
        (cartItem) => cartItem.product.id === product.id && cartItem.size === size,
      );
      if (existingItem) {
        return prev.map((cartItem) =>
          cartItem.product.id === product.id && cartItem.size === size
            ? { ...cartItem, quantity: cartItem.quantity + 1 }
            : cartItem,
        );
      }
      return [...prev, { product, size, quantity: 1 }];
    });
    setCartOpen(true);
  }, []);

  const removeFromCart = useCallback((productId: string, size: string): void => {
    setCartItems((prev) =>
      prev.filter((cartItem) => !(cartItem.product.id === productId && cartItem.size === size)),
    );
  }, []);

  const updateQuantity = useCallback(
    (productId: string, size: string, quantity: number): void => {
      if (quantity <= 0) {
        removeFromCart(productId, size);
        return;
      }

      setCartItems((prev) =>
        prev.map((cartItem) =>
          cartItem.product.id === productId && cartItem.size === size
            ? { ...cartItem, quantity }
            : cartItem,
        ),
      );
    },
    [removeFromCart],
  );

  const clearCart = useCallback((): void => {
    writeStoredCart([]);
    setCartItems([]);
  }, []);

  const cartCount = useMemo(
    () => cartItems.reduce((sum, item) => sum + item.quantity, 0),
    [cartItems],
  );
  const cartTotal = useMemo(
    () => cartItems.reduce((sum, item) => sum + item.product.price * item.quantity, 0),
    [cartItems],
  );

  const value = useMemo<CartContextValue>(
    () => ({
      cartItems,
      isCartOpen,
      cartCount,
      cartTotal,
      addToCart,
      removeFromCart,
      updateQuantity,
      clearCart,
      setCartOpen,
    }),
    [
      addToCart,
      cartCount,
      cartItems,
      cartTotal,
      clearCart,
      isCartOpen,
      removeFromCart,
      updateQuantity,
    ],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextValue {
  const context = useContext(CartContext);
  if (!context) throw new Error("useCart must be used inside CartProvider");
  return context;
}
