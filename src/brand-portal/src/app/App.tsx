import { createBrowserRouter, Outlet, RouterProvider } from "react-router";
import { lazy, Suspense, useEffect, type ReactNode } from "react";
import { AuthProvider } from "./AuthProvider";
import { Layout } from "./components/Layout";
import { Login } from "./Login";
import { ProtectedRoute } from "./ProtectedRoute";
import faviconUrl from "../imports/fabicon_359_b.svg";

const Dashboard = lazy(() => import("./components/Dashboard").then(m => ({ default: m.Dashboard })));
const Catalog = lazy(() => import("./components/Catalog").then(m => ({ default: m.Catalog })));
const ProductEditor = lazy(() => import("./components/ProductEditor").then(m => ({ default: m.ProductEditor })));
const Orders = lazy(() => import("./components/Orders").then(m => ({ default: m.Orders })));
const Finances = lazy(() => import("./components/Finances").then(m => ({ default: m.Finances })));
const Settings = lazy(() => import("./components/Settings").then(m => ({ default: m.Settings })));
const NotFound = lazy(() => import("./components/NotFound").then(m => ({ default: m.NotFound })));

function SuspenseWrapper({ children }: { children: ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="flex-1 flex items-center justify-center p-12">
          <div className="w-5 h-5 border-2 border-border border-t-primary rounded-full animate-spin" />
        </div>
      }
    >
      {children}
    </Suspense>
  );
}

const router = createBrowserRouter([
  {
    path: "/",
    element: (
      <AuthProvider>
        <Outlet />
      </AuthProvider>
    ),
    children: [
      { path: "login", element: <Login /> },
      {
        element: (
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        ),
        children: [
          { index: true, element: <SuspenseWrapper><Dashboard /></SuspenseWrapper> },
          { path: "catalog", element: <SuspenseWrapper><Catalog /></SuspenseWrapper> },
          { path: "catalog/upload", element: <SuspenseWrapper><NotFound /></SuspenseWrapper> },
          { path: "catalog/new", element: <SuspenseWrapper><ProductEditor /></SuspenseWrapper> },
          { path: "catalog/:id", element: <SuspenseWrapper><ProductEditor /></SuspenseWrapper> },
          { path: "orders", element: <SuspenseWrapper><Orders /></SuspenseWrapper> },
          { path: "finances", element: <SuspenseWrapper><Finances /></SuspenseWrapper> },
          { path: "settings", element: <SuspenseWrapper><Settings /></SuspenseWrapper> },
          { path: "*", element: <SuspenseWrapper><NotFound /></SuspenseWrapper> },
        ],
      },
    ],
  },
]);

export default function App() {
  useEffect(() => {
    const link =
      document.querySelector<HTMLLinkElement>("link[rel*='icon']") ||
      document.createElement("link");
    link.type = 'image/svg+xml';
    link.rel = 'icon';
    link.href = faviconUrl;
    document.head.appendChild(link);
  }, []);

  return <RouterProvider router={router} />;
}
