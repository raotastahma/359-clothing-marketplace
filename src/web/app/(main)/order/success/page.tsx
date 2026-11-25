import { Suspense } from "react";

import { OrderSuccessClient } from "./order-success-client";

export default function OrderSuccessPage() {
  return (
    <Suspense
      fallback={
        <section className="mx-auto flex min-h-[60vh] max-w-xl flex-col items-center justify-center px-6 py-20 text-center">
          <p className="text-sm text-black/55">Загружаем заказ...</p>
        </section>
      }
    >
      <OrderSuccessClient />
    </Suspense>
  );
}
