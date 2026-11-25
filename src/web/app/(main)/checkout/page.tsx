// Customer checkout route: renders the delivery/payment flow and validates contact data before order creation.
"use client";

import {
  Check,
  CreditCard,
  ShoppingBag,
  Smartphone,
  Store,
  Truck,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";

import { Price } from "@/src/components/price";
import { Button } from "@/src/components/ui/button";
import { useCart, type CartItem } from "@/src/components/providers/cart-context";
import { useUser } from "@/src/components/providers/user-context";
import {
  requestJson,
  type AddressApiResponse,
  type AddressRequest,
  type CartApiResponse,
  type CreateOrderApiResponse,
  type CreateOrderRequest,
} from "@/src/lib/api";
import { cn } from "@/src/lib/utils";

type CheckoutStep = 1 | 2 | 3;
type DeliveryMethod = "pickup" | "courier";
type PaymentMethod = "sbp" | "card_online";

interface BrandGroup {
  brand: string;
  items: CartItem[];
}

interface ContactForm {
  fullName: string;
  phone: string;
  city: string;
  street: string;
  zip: string;
}

const DELIVERY_COST = 0;

function isValidCheckoutPhone(value: string): boolean {
  const digits = value.replace(/\D/g, "");

  return digits.length === 10 || (digits.length === 11 && ["7", "8"].includes(digits[0]));
}

function groupByBrand(items: CartItem[]): BrandGroup[] {
  const groups = new Map<string, CartItem[]>();

  items.forEach((item) => {
    const brandItems = groups.get(item.product.brand) ?? [];
    brandItems.push(item);
    groups.set(item.product.brand, brandItems);
  });

  return Array.from(groups, ([brand, brandItems]) => ({ brand, items: brandItems }));
}

function getProductImage(product: CartItem["product"]): string | undefined {
  return product.images[0];
}

function getVariantId(item: CartItem): string | null {
  return item.product.variantIdsBySize?.[item.size] ?? null;
}

async function syncServerCart(items: CartItem[]): Promise<void> {
  const localItems = items.map((item) => ({
    item,
    productVariantId: getVariantId(item),
  }));
  if (localItems.some(({ productVariantId }) => !productVariantId)) {
    throw new Error("Не удалось определить вариант одного из товаров.");
  }

  const localQuantityByVariant = new Map(
    localItems.map(({ item, productVariantId }) => [productVariantId as string, item.quantity]),
  );
  const { data: serverCart } = await requestJson<CartApiResponse>("/cart/items");

  await Promise.all(
    serverCart.items.map((serverItem) => {
      const localQuantity = localQuantityByVariant.get(serverItem.product_variant.id);
      if (localQuantity === undefined) {
        return requestJson<CartApiResponse>(`/cart/items/${serverItem.id}`, { method: "DELETE" });
      }

      localQuantityByVariant.delete(serverItem.product_variant.id);
      if (serverItem.quantity === localQuantity) return Promise.resolve();

      return requestJson<CartApiResponse>(`/cart/items/${serverItem.id}`, {
        method: "PATCH",
        body: { quantity: localQuantity },
      });
    }),
  );

  await Promise.all(
    Array.from(localQuantityByVariant, ([productVariantId, quantity]) =>
      requestJson<CartApiResponse>("/cart/items", {
        method: "POST",
        body: {
          product_variant_id: productVariantId,
          quantity,
        },
      }),
    ),
  );
}

function SelectCard({
  children,
  isSelected,
  onClick,
}: {
  children: ReactNode;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full items-start gap-4 border p-4 text-left transition-colors",
        isSelected
          ? "border-black bg-black text-white"
          : "border-black/15 bg-white text-black hover:border-black/40",
      )}
    >
      {children}
    </button>
  );
}

function StepBar({ step }: { step: CheckoutStep }) {
  const steps = [
    { value: 1, label: "Доставка" },
    { value: 2, label: "Оплата" },
    { value: 3, label: "Готово" },
  ] as const;

  return (
    <div className="flex items-center gap-3">
      {steps.map((item, index) => {
        const isDone = step > item.value;
        const isActive = step === item.value;

        return (
          <div key={item.value} className="flex flex-1 items-center gap-3">
            <div className="flex items-center gap-3">
              <span
                className={cn(
                  "flex h-8 w-8 items-center justify-center text-xs",
                  isDone || isActive
                    ? "bg-black text-white"
                    : "border border-black/20 text-black/45",
                )}
              >
                {isDone ? <Check size={14} strokeWidth={1.5} /> : item.value}
              </span>
              <span
                className={cn(
                  "hidden text-xs tracking-[1.5px] uppercase sm:inline",
                  isActive ? "text-black" : "text-black/45",
                )}
              >
                {item.label}
              </span>
            </div>
            {index < steps.length - 1 ? <div className="h-px flex-1 bg-black/10" /> : null}
          </div>
        );
      })}
    </div>
  );
}

function OrderItems({ groups }: { groups: BrandGroup[] }) {
  return (
    <div className="space-y-6">
      {groups.map((group) => (
        <section key={group.brand} className="space-y-3">
          <h3 className="text-[11px] tracking-[2px] text-black/45 uppercase">{group.brand}</h3>
          <div className="space-y-3">
            {group.items.map((item) => (
              <div
                key={`${item.product.id}-${item.size}`}
                className="grid grid-cols-[4rem_1fr] gap-3 border-b border-black/10 pb-3"
              >
                <div
                  className="h-20 w-16 bg-black/5 bg-cover bg-center"
                  style={{
                    backgroundImage: getProductImage(item.product)
                      ? `url(${getProductImage(item.product)})`
                      : undefined,
                  }}
                  aria-label={item.product.name}
                />
                <div className="min-w-0">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm leading-snug">{item.product.name}</p>
                      <p className="mt-1 text-xs text-black/50">
                        Размер {item.size} · {item.quantity} шт.
                      </p>
                    </div>
                    <Price
                      amount={item.product.price * item.quantity}
                      className="shrink-0 text-sm"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function Summary({ total, title = "Итого" }: { total: number; title?: string }) {
  return (
    <div className="space-y-3 border border-black/10 p-5">
      <div className="flex items-center justify-between text-sm">
        <span>Товары</span>
        <Price amount={total} />
      </div>
      <div className="flex items-center justify-between text-sm">
        <span>Доставка</span>
        <Price amount={DELIVERY_COST} />
      </div>
      <div className="flex items-center justify-between border-t border-black/10 pt-3 text-base font-medium">
        <span>{title}</span>
        <Price amount={total + DELIVERY_COST} />
      </div>
    </div>
  );
}

export default function CheckoutPage() {
  const { cartItems, cartCount, cartTotal, clearCart } = useCart();
  const { addresses, user } = useUser();
  const [step, setStep] = useState<CheckoutStep>(1);
  const [deliveryMethod, setDeliveryMethod] = useState<DeliveryMethod>("pickup");
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("sbp");
  const [form, setForm] = useState<ContactForm>({
    fullName: "",
    phone: "",
    city: "",
    street: "",
    zip: "",
  });
  const [errors, setErrors] = useState<Partial<Record<keyof ContactForm, string>>>({});
  const [orderError, setOrderError] = useState<string | null>(null);
  const [isSubmitting, setSubmitting] = useState(false);

  const brandGroups = useMemo(() => groupByBrand(cartItems), [cartItems]);

  useEffect(() => {
    const defaultAddress = addresses.find((address) => address.is_default) ?? addresses[0];
    if (!user && !defaultAddress) return;

    setForm((prev) => ({
      fullName: prev.fullName || user?.name || "",
      phone: prev.phone || user?.phone || "",
      city: prev.city || defaultAddress?.city || "",
      street:
        prev.street ||
        [defaultAddress?.street, defaultAddress?.apartment].filter(Boolean).join(", "),
      zip: prev.zip || defaultAddress?.postal_code || "",
    }));
  }, [addresses, user]);

  function updateField(field: keyof ContactForm, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  }

  function validateDelivery(): boolean {
    const nextErrors: Partial<Record<keyof ContactForm, string>> = {};

    if (!form.fullName.trim()) nextErrors.fullName = "Укажите ФИО";
    if (!form.phone.trim()) nextErrors.phone = "Укажите телефон";
    else if (!isValidCheckoutPhone(form.phone)) {
      nextErrors.phone = "Укажите 10 цифр или 11 цифр с 7 или 8 в начале";
    }
    if (deliveryMethod === "courier") {
      if (!form.city.trim()) nextErrors.city = "Укажите город";
      if (!form.street.trim()) nextErrors.street = "Укажите улицу, дом и квартиру";
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  function onDeliverySubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validateDelivery()) return;
    setStep(2);
  }

  async function placeOrder() {
    try {
      await syncServerCart(cartItems);

      const addressBody = {
        city: deliveryMethod === "courier" ? form.city.trim() : "Москва",
        street:
          deliveryMethod === "courier"
            ? form.street.trim()
            : "ПВЗ Яндекс.Доставки",
        postal_code: deliveryMethod === "courier" ? form.zip.trim() : undefined,
        is_default: true,
      } satisfies AddressRequest;
      const { data: address } = await requestJson<AddressApiResponse>("/users/me/addresses", {
        method: "POST",
        body: addressBody,
      });

      const orderBody = {
        address_id: address.id,
        delivery_provider: "yandex_delivery",
        delivery_method: deliveryMethod === "pickup" ? "pickup_point" : "courier",
      } satisfies CreateOrderRequest;
      const { data: order } = await requestJson<CreateOrderApiResponse>("/orders", {
        method: "POST",
        body: orderBody,
      });

      return order;
    } catch (nextError) {
      throw nextError instanceof Error
        ? nextError
        : new Error("Не удалось оформить заказ. Попробуйте ещё раз.");
    }
  }

  async function onPaymentSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setOrderError(null);
    setSubmitting(true);

    try {
      const order = await placeOrder();
      clearCart();

      if (!order.payment_url) {
        window.location.assign(
          `/order/success?id=${encodeURIComponent(order.id)}&error=payment_redirect`,
        );
        return;
      }

      window.location.assign(order.payment_url);
    } catch (nextError) {
      setOrderError(
        nextError instanceof Error
          ? nextError.message
          : "Не удалось оформить заказ. Попробуйте ещё раз.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  function addressFields() {
    return (
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-2 text-sm">
          <span>Город</span>
          <input
            value={form.city}
            onChange={(event) => updateField("city", event.target.value)}
            className="h-11 w-full border border-black/15 bg-white px-3 outline-none focus:border-black"
            aria-invalid={Boolean(errors.city)}
          />
          {errors.city ? (
            <span className="block text-xs text-destructive">{errors.city}</span>
          ) : null}
        </label>
        <label className="space-y-2 text-sm sm:col-span-2">
          <span>Улица, дом, квартира</span>
          <input
            value={form.street}
            onChange={(event) => updateField("street", event.target.value)}
            className="h-11 w-full border border-black/15 bg-white px-3 outline-none focus:border-black"
            aria-invalid={Boolean(errors.street)}
          />
          {errors.street ? (
            <span className="block text-xs text-destructive">{errors.street}</span>
          ) : null}
        </label>
        <label className="space-y-2 text-sm">
          <span>Индекс</span>
          <input
            value={form.zip}
            onChange={(event) => updateField("zip", event.target.value)}
            className="h-11 w-full border border-black/15 bg-white px-3 outline-none focus:border-black"
            aria-invalid={Boolean(errors.zip)}
          />
          {errors.zip ? (
            <span className="block text-xs text-destructive">{errors.zip}</span>
          ) : null}
        </label>
      </div>
    );
  }

  if (cartItems.length === 0 && step !== 3) {
    return (
      <section className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center px-6 py-20 text-center">
        <ShoppingBag size={42} strokeWidth={1.2} className="mb-5 text-black/35" />
        <h1 className="text-xl">Корзина пуста</h1>
        <Button asChild className="mt-6 w-full bg-black text-white">
          <Link href="/shop">Перейти в каталог</Link>
        </Button>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:py-14">
      <div className="mb-10">
        <h1 className="mb-6 text-2xl tracking-tight sm:text-3xl">Оформление заказа</h1>
        <StepBar step={step} />
      </div>

      {step === 1 ? (
        <form onSubmit={onDeliverySubmit} className="grid gap-8 lg:grid-cols-[1fr_23rem]">
          <div className="space-y-8">
            <section className="space-y-4">
              <div>
                <h2 className="text-sm tracking-[2px] uppercase">
                  Состав заказа · {cartCount} товаров
                </h2>
                <p className="mt-2 text-sm text-black/50">
                  Бесплатная доставка для всех товаров
                </p>
              </div>
              <OrderItems groups={brandGroups} />
            </section>

            <section className="space-y-4">
              <h2 className="text-sm tracking-[2px] uppercase">Контакты</h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-2 text-sm">
                  <span>ФИО</span>
                  <input
                    value={form.fullName}
                    onChange={(event) => updateField("fullName", event.target.value)}
                    className="h-11 w-full border border-black/15 bg-white px-3 outline-none focus:border-black"
                    aria-invalid={Boolean(errors.fullName)}
                  />
                  {errors.fullName ? (
                    <span className="block text-xs text-destructive">{errors.fullName}</span>
                  ) : null}
                </label>
                <label className="space-y-2 text-sm">
                  <span>Телефон</span>
                  <input
                    value={form.phone}
                    onChange={(event) => updateField("phone", event.target.value)}
                    className="h-11 w-full border border-black/15 bg-white px-3 outline-none focus:border-black"
                    aria-invalid={Boolean(errors.phone)}
                  />
                  {errors.phone ? (
                    <span className="block text-xs text-destructive">{errors.phone}</span>
                  ) : null}
                </label>
              </div>
            </section>

            <section className="space-y-4">
              <h2 className="text-sm tracking-[2px] uppercase">Способ доставки</h2>
              <div className="grid gap-3 sm:grid-cols-2">
                <SelectCard
                  isSelected={deliveryMethod === "pickup"}
                  onClick={() => setDeliveryMethod("pickup")}
                >
                  <Store size={20} strokeWidth={1.5} />
                  <span>
                    <span className="block text-sm font-medium">Самовывоз из ПВЗ</span>
                    <span className="mt-1 block text-xs opacity-70">Бесплатно</span>
                  </span>
                </SelectCard>
                <SelectCard
                  isSelected={deliveryMethod === "courier"}
                  onClick={() => setDeliveryMethod("courier")}
                >
                  <Truck size={20} strokeWidth={1.5} />
                  <span>
                    <span className="block text-sm font-medium">Курьер</span>
                    <span className="mt-1 block text-xs opacity-70">Бесплатно</span>
                  </span>
                </SelectCard>
              </div>

              {deliveryMethod === "pickup" ? (
                <div className="border border-black/10 bg-black/[0.02] p-4 text-sm text-black/60">
                  ПВЗ Яндекс.Доставки · адрес будет уточнен при интеграции доставки
                </div>
              ) : null}

              {deliveryMethod === "courier" ? addressFields() : null}
            </section>
          </div>

          <aside className="lg:sticky lg:top-20 lg:self-start">
            <Summary total={cartTotal} />
            <Button className="mt-4 h-12 w-full bg-black text-white" type="submit">
              Перейти к оплате
            </Button>
          </aside>
        </form>
      ) : null}

      {step === 2 ? (
        <form onSubmit={onPaymentSubmit} className="grid gap-8 lg:grid-cols-[1fr_23rem]">
          <div className="space-y-6">
            <section className="space-y-4">
              <h2 className="text-sm tracking-[2px] uppercase">Оплата</h2>
              <div className="grid gap-3 sm:grid-cols-2">
                <SelectCard
                  isSelected={paymentMethod === "sbp"}
                  onClick={() => setPaymentMethod("sbp")}
                >
                  <Smartphone size={20} strokeWidth={1.5} />
                  <span className="flex flex-1 items-start justify-between gap-3">
                    <span>
                      <span className="block text-sm font-medium">СБП</span>
                      <span className="mt-1 block text-xs opacity-70">Онлайн-оплата</span>
                    </span>
                    <span className="bg-white px-2 py-0.5 text-[10px] tracking-[1px] text-black uppercase">
                      Быстро
                    </span>
                  </span>
                </SelectCard>
                <SelectCard
                  isSelected={paymentMethod === "card_online"}
                  onClick={() => setPaymentMethod("card_online")}
                >
                  <CreditCard size={20} strokeWidth={1.5} />
                  <span>
                    <span className="block text-sm font-medium">Картой онлайн</span>
                    <span className="mt-1 block text-xs opacity-70">Visa, Mastercard, МИР</span>
                  </span>
                </SelectCard>
              </div>
              <div className="border border-black/10 bg-black/[0.02] p-4 text-sm text-black/60">
                Вы будете перенаправлены на страницу оплаты ЮKassa
              </div>
            </section>
          </div>

          <aside className="lg:sticky lg:top-20 lg:self-start">
            <Summary total={cartTotal} title="К оплате" />
            {orderError ? <p className="mt-3 text-sm text-destructive">{orderError}</p> : null}
            <div className="mt-4 grid grid-cols-2 gap-3">
              <Button
                type="button"
                variant="outline"
                className="h-12 border-black/20 bg-white"
                onClick={() => setStep(1)}
              >
                Назад
              </Button>
              <Button className="h-12 bg-black text-white" type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Создаем заказ" : "Перейти к оплате"}
              </Button>
            </div>
          </aside>
        </form>
      ) : null}
    </section>
  );
}
