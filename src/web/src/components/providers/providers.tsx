"use client";

import { Suspense } from "react";

import { CartProvider } from "./cart-context";
import { ContactProvider } from "./contact-context";
import { FilterProvider } from "./filter-context";
import { UserProvider } from "./user-context";

interface ProvidersProps {
  children: React.ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  return (
    <CartProvider>
      <FilterProvider>
        <UserProvider>
          <ContactProvider>
            <Suspense fallback={<div className="min-h-screen" />}>{children}</Suspense>
          </ContactProvider>
        </UserProvider>
      </FilterProvider>
    </CartProvider>
  );
}
