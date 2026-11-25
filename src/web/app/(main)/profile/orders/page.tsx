"use client";

import { ArrowLeft, ShoppingBag } from "lucide-react";
import Link from "next/link";

import { Price } from "@/src/components/price";
import { Button } from "@/src/components/ui/button";
import { useUser, type Order, type OrderParcel } from "@/src/components/providers/user-context";

const STATUS_LABELS: Record<string, string> = {
  pending: "Новый",
  paid: "Оплачен",
  processing: "В обработке",
  confirmed: "Подтвержден",
  shipped: "В пути",
  delivered: "Доставлен",
  completed: "Завершен",
  cancelled_by_buyer: "Отменен",
  cancelled_by_brand: "Отменен брендом",
  returned: "Возвращен",
};

function StatusBadge({ status }: { status: Order["status"] | OrderParcel["status"] }) {
  return (
    <span className="border border-black/10 bg-black px-3 py-1 text-[11px] tracking-[1.5px] text-white uppercase">
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

function OrderCard({ order }: { order: Order }) {
  return (
    <article className="border border-black/10 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base">Заказ {order.id}</h2>
          <p className="mt-1 text-sm text-black/50">{order.createdAt}</p>
        </div>
        <StatusBadge status={order.status} />
      </div>

      {order.parcels && order.parcels.length > 0 ? (
        <div className="mt-5 space-y-3">
          {order.parcels.map((parcel) => (
            <div
              key={parcel.id}
              className="border-b border-black/10 pb-3 last:border-b-0 last:pb-0"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] tracking-[1.5px] text-black/45 uppercase">
                    {parcel.brandName}
                  </p>
                  <p className="mt-1 text-sm">{parcel.itemsCount} товаров</p>
                  {parcel.trackingNumber ? (
                    <p className="mt-1 text-xs text-black/50">
                      Трек-номер {parcel.trackingNumber}
                    </p>
                  ) : null}
                </div>
                <StatusBadge status={parcel.status} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-5 space-y-3">
          {order.items.map((item) => (
            <div
              key={`${order.id}-${item.product.id}-${item.size}`}
              className="grid grid-cols-[4rem_1fr] gap-3 border-b border-black/10 pb-3 last:border-b-0 last:pb-0"
            >
              <div
                className="h-20 w-16 bg-black/5 bg-cover bg-center"
                style={{ backgroundImage: `url(${item.product.images[0]})` }}
                aria-label={item.product.name}
              />
              <div className="min-w-0">
                <p className="text-[11px] tracking-[1.5px] text-black/45 uppercase">
                  {item.product.brand}
                </p>
                <p className="mt-1 text-sm">{item.product.name}</p>
                <p className="mt-1 text-xs text-black/50">
                  Размер {item.size} · {item.quantity} шт.
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-5 flex items-center justify-between border-t border-black/10 pt-4">
        <span className="text-sm text-black/50">Итого</span>
        <Price amount={order.total} className="text-base" />
      </div>
    </article>
  );
}

export default function OrdersPage() {
  const { accountError, isAccountLoading, orders } = useUser();

  return (
    <section className="mx-auto max-w-3xl px-4 py-10 sm:px-6 lg:py-14">
      <div className="flex items-center gap-4">
        <Link
          href="/profile"
          className="flex h-10 w-10 items-center justify-center border border-black/10 transition-colors hover:bg-black hover:text-white"
          aria-label="Назад"
        >
          <ArrowLeft size={18} strokeWidth={1.5} />
        </Link>
        <h1 className="text-3xl tracking-tight">Заказы</h1>
      </div>

      {isAccountLoading ? (
        <div className="flex min-h-[45vh] flex-col items-center justify-center text-center">
          <p className="text-sm text-black/50">Загружаем заказы...</p>
        </div>
      ) : accountError && orders.length === 0 ? (
        <div className="flex min-h-[45vh] flex-col items-center justify-center text-center">
          <ShoppingBag size={42} strokeWidth={1.2} className="mb-5 text-black/35" />
          <h2 className="text-xl">Не удалось загрузить заказы</h2>
          <p className="mt-3 text-sm text-black/50">{accountError}</p>
        </div>
      ) : orders.length === 0 ? (
        <div className="flex min-h-[45vh] flex-col items-center justify-center text-center">
          <ShoppingBag size={42} strokeWidth={1.2} className="mb-5 text-black/35" />
          <h2 className="text-xl">У вас пока нет заказов</h2>
          <Button asChild className="mt-6 h-12 w-full max-w-sm bg-black text-white">
            <Link href="/shop">Перейти в каталог</Link>
          </Button>
        </div>
      ) : (
        <div className="mt-8 space-y-4">
          {orders.map((order) => (
            <OrderCard key={order.id} order={order} />
          ))}
        </div>
      )}
    </section>
  );
}
