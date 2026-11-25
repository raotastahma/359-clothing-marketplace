import type { Metadata } from "next";
import { Providers } from "@/src/components/providers/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "359 Clothing",
  description: "Marketplace of Russian designer clothing brands",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
