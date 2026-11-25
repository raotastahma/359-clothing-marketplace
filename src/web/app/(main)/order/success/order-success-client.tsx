"use client";

import { Check } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Price } from "@/src/components/price";
import { Button } from "@/src/components/ui/button";
import { requestJson, type Order, type OrderApiResponse, type OrderStatus } from "@/src/lib/api";

const STATUS_LABELS: Record<OrderStatus, string> = {
  pending: "Ожидает оплаты",
  paid: "Оплачен",
  processing: "Собирается",
  shipped: "Передан в доставку",
  delivered: "Доставлен",
  completed: "Завершен",
  cancelled_by_buyer: "Отменен покупателем",
  cancelled_by_brand: "Отменен брендом",
  returned: "Возвращен",
};

function getErrorMessage(error: string | null): string | null {
  if (!error) return null;
  if (error === "payment_redirect") {
    return "Не удалось перейти на страницу оплаты ЮKassa. Попробуйте оплатить заказ из личного кабинета.";
  }
  return "Оплата не завершена. Проверьте статус заказа в личном кабинете.";
}

export function OrderSuccessClient() {
  const searchParams = useSearchParams();
  const orderId = searchParams.get("id");
  const paymentError = getErrorMessage(searchParams.get("error"));
  const missingOrderError = orderId ? null : "Не удалось определить номер заказа.";
  const [order, setOrder] = useState<Order | null>(null);
  const [isLoading, setLoading] = useState<boolean>(Boolean(orderId));
  const [orderError, setOrderError] = useState<string | null>(null);

  useEffect(() => {
    if (!orderId) return undefined;

    let isMounted = true;

    queueMicrotask(() => {
      if (!isMounted) return;
      setLoading(true);
      setOrderError(null);
    });

    requestJson<OrderApiResponse>(`/orders/${encodeURIComponent(orderId)}`, {
      redirectOnUnauthorized: false,
    })
      .then(({ data }) => {
        if (isMounted) setOrder(data);
      })
      .catch(() => {
        if (isMounted) setOrderError("Не удалось загрузить данные заказа.");
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [orderId]);

  const brandNames = useMemo(
    () => order?.sub_orders.map((subOrder) => subOrder.brand_name) ?? [],
    [order],
  );

  return (
    <section className="mx-auto flex min-h-[60vh] max-w-xl flex-col items-center justify-center px-6 py-20 text-center">
      <div className="mb-6 flex h-14 w-14 items-center justify-center bg-black text-white">
        <Check size={24} strokeWidth={1.5} />
      </div>
      <h1 className="text-2xl tracking-tight">
        {paymentError ? "Заказ создан" : "Оплата прошла успешно"}
      </h1>
      {orderId ? <p className="mt-3 text-sm text-black/55">Номер заказа: {orderId}</p> : null}
      {paymentError ? <p className="mt-4 text-sm text-destructive">{paymentError}</p> : null}

      {isLoading ? <p className="mt-4 text-sm text-black/55">Загружаем данные заказа...</p> : null}
      {missingOrderError ? (
        <p className="mt-4 text-sm text-destructive">{missingOrderError}</p>
      ) : null}
      {orderError ? <p className="mt-4 text-sm text-destructive">{orderError}</p> : null}

      {order ? (
        <div className="mt-6 w-full space-y-5 text-left">
          <div className="border border-black/10 p-4 text-sm">
            <div className="flex items-center justify-between gap-4">
              <span className="text-black/55">Оплачено</span>
              <Price amount={order.total_amount} />
            </div>
            <p className="mt-3 text-black/60">
              Ваш заказ разделен на {order.sub_orders.length} посылки от брендов:{" "}
              {brandNames.join(", ")}
            </p>
            <p className="mt-2 text-black/60">
              Каждый бренд подтвердит заказ в течение 24 часов.
            </p>
          </div>

          <div className="space-y-3">
            {order.sub_orders.map((subOrder) => (
              <div
                key={subOrder.id}
                className="flex items-center justify-between gap-4 border border-black/10 p-4 text-sm"
              >
                <div>
                  <p className="font-medium">{subOrder.brand_name}</p>
                  <p className="mt-1 text-xs text-black/50">{subOrder.items_count} товаров</p>
                </div>
                <span className="text-right text-xs text-black/55">
                  {STATUS_LABELS[subOrder.status]}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-8 grid w-full gap-3 sm:grid-cols-2">
        <Button asChild className="h-12 bg-black text-white">
          <Link href="/profile/orders">Мои заказы</Link>
        </Button>
        <Button asChild variant="outline" className="h-12 border-black/20 bg-white">
          <Link href="/shop">Продолжить покупки</Link>
        </Button>
      </div>
    </section>
  );
}
