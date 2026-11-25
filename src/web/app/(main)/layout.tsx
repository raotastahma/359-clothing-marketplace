import { Suspense } from "react";
import { ContactModal } from "@/src/components/overlays/contact-modal";
import { CartDrawer } from "@/src/components/overlays/cart-drawer";
import { Footer } from "@/src/components/layout/footer";
import { Header } from "@/src/components/layout/header";

interface MainLayoutProps {
  children: React.ReactNode;
}

export default function MainLayout({ children }: MainLayoutProps) {
  return (
    <div className="flex min-h-screen flex-col bg-white text-black">
      <Suspense fallback={<div className="h-14 border-b border-black/10 bg-white" />}>
        <Header />
      </Suspense>
      <main className="flex-1 pt-14">{children}</main>
      <Footer />
      <CartDrawer />
      <ContactModal />
    </div>
  );
}
