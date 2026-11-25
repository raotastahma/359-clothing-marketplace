import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { Outlet, NavLink, useLocation } from "react-router";
import logoSrc from "../../imports/logo_359.svg";
import {
  LayoutDashboard,
  Package,
  ShoppingBag,
  Wallet,
  Settings,
  Bell,
  ChevronDown,
  User,
  LogOut,
  X,
  Menu,
} from "lucide-react";
import { ErrorBoundary } from "./ErrorBoundary";
import { useAuth } from "../auth-context";
import { Button } from "./ui/button";
import { Separator } from "./ui/separator";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "./ui/sheet";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { useIsMobile } from "./ui/use-mobile";

const navItems = [
  { to: "/", label: "Статистика", icon: LayoutDashboard, exact: true },
  { to: "/catalog", label: "Каталог", icon: Package },
  { to: "/orders", label: "Заказы", icon: ShoppingBag },
  { to: "/finances", label: "Финансы", icon: Wallet },
  { to: "/settings", label: "Настройки", icon: Settings },
];

const initialNotifications = [
  { id: 1, text: "Новый заказ ORD-4821 на ₽ 4 990", time: "5 мин назад", read: false },
  { id: 2, text: "Заказ ORD-4818 отправлен покупателю", time: "2 часа назад", read: false },
  { id: 3, text: "YML синхронизация завершена успешно", time: "4 часа назад", read: true },
  { id: 4, text: "Выплата ₽ 18 540 запланирована на 01.03", time: "1 день назад", read: true },
];

function SidebarNav({ pathname }: { pathname: string }) {
  return (
    <nav className="flex-1 py-4 overflow-y-auto">
      <ul className="space-y-0.5 px-2">
        {navItems.map((item) => {
          const isActive = item.exact
            ? pathname === item.to
            : pathname === item.to || pathname.startsWith(item.to + "/");
          return (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.exact}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent"
                }`}
              >
                <item.icon size={16} strokeWidth={1.5} />
                <span>{item.label}</span>
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function Layout() {
  const location = useLocation();
  const isMobile = useIsMobile();
  const { logout, session } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);
  const [notifications, setNotifications] = useState(initialNotifications);

  const bellRef = useRef<HTMLDivElement>(null);
  const brandName = session?.brand.name ?? "Бренд";

  const hasUnread = useMemo(() => notifications.some((n) => !n.read), [notifications]);

  const markAllRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  // Закрываем sidebar при смене маршрута на мобильном
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) setBellOpen(false);
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const sidebarContent = (
    <>
      {/* Logo */}
      <div className="h-14 flex items-center px-6 border-b border-border flex-shrink-0">
        <NavLink to="/" className="flex items-center gap-3">
          <img src={logoSrc} alt="359" className="h-7 w-auto" />
          <div className="text-[11px] text-muted-foreground uppercase tracking-wider leading-none">Brand Portal</div>
        </NavLink>
      </div>

      <SidebarNav pathname={location.pathname} />

      {/* Brand Info */}
      <div className="px-4 py-3 border-t border-border flex-shrink-0">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="w-full flex items-center gap-2 p-2 rounded-md hover:bg-accent cursor-pointer transition-colors outline-none">
              <div className="w-7 h-7 bg-muted rounded-full flex items-center justify-center flex-shrink-0">
                <User size={13} strokeWidth={1.5} className="text-muted-foreground" />
              </div>
              <div className="flex-1 min-w-0 text-left">
                <div className="text-xs text-foreground truncate">{brandName}</div>
                <div className="text-[10px] text-muted-foreground">Бренд</div>
              </div>
              <ChevronDown size={13} className="text-muted-foreground" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" align="start" className="w-[calc(100%-2rem)]">
            <DropdownMenuItem asChild>
              <NavLink to="/settings" className="cursor-pointer">
                <Settings size={14} strokeWidth={1.5} />
                Настройки бренда
              </NavLink>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-muted-foreground" onSelect={logout}>
              <LogOut size={14} strokeWidth={1.5} />
              Выйти
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </>
  );

  return (
    <div className="flex h-screen bg-muted/30 overflow-hidden">

      {/* ── Desktop sidebar ── */}
      <aside className="hidden md:flex w-[240px] flex-shrink-0 bg-card border-r border-border flex-col">
        {sidebarContent}
      </aside>

      {/* ── Mobile drawer (Sheet) ── */}
      <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
        <SheetContent side="left" className="w-[260px] p-0 flex flex-col md:hidden [&>button:last-child]:hidden">
          <SheetHeader className="sr-only">
            <SheetTitle>Навигация</SheetTitle>
            <SheetDescription>Меню навигации Brand Portal</SheetDescription>
          </SheetHeader>
          {/* Logo */}
          <div className="h-14 flex items-center px-6 border-b border-border flex-shrink-0">
            <NavLink to="/" className="flex items-center gap-3">
              <img src={logoSrc} alt="359" className="h-7 w-auto" />
              <div className="text-[11px] text-muted-foreground uppercase tracking-wider leading-none">Brand Portal</div>
            </NavLink>
          </div>
          <SidebarNav pathname={location.pathname} />
          <div className="px-4 py-3 border-t border-border flex-shrink-0">
            <div className="flex items-center gap-2 p-2">
              <div className="w-7 h-7 bg-muted rounded-full flex items-center justify-center flex-shrink-0">
                <User size={13} strokeWidth={1.5} className="text-muted-foreground" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs text-foreground truncate">{brandName}</div>
                <div className="text-[10px] text-muted-foreground">Бренд</div>
              </div>
            </div>
          </div>
        </SheetContent>
      </Sheet>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <header className="h-14 bg-card border-b border-border flex items-center px-4 md:px-6 gap-3 flex-shrink-0">

          {/* Бургер — только на мобильном */}
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu size={18} strokeWidth={1.5} />
          </Button>

          <div className="flex-1 min-w-0">
            <span className="text-sm text-muted-foreground hidden sm:inline">Добрый день,</span>
            <span className="text-sm text-foreground ml-1">{brandName}</span>
          </div>

          <div className="flex items-center gap-2 md:gap-3">
            {/* Bell */}
            <div className="relative" ref={bellRef}>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setBellOpen(!bellOpen)}
                className="relative"
              >
                <Bell size={16} strokeWidth={1.5} />
                {hasUnread && (
                  <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-primary rounded-full" />
                )}
              </Button>

              {/* Desktop dropdown */}
              {bellOpen && (
                <div className="hidden md:block absolute top-full right-0 mt-1 w-[320px] bg-popover border border-border rounded-lg shadow-lg z-50 overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-3">
                    <span className="text-sm text-foreground">Уведомления</span>
                    <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setBellOpen(false)}>
                      <X size={13} strokeWidth={1.5} />
                    </Button>
                  </div>
                  <Separator />
                  <div className="max-h-[280px] overflow-y-auto">
                    {notifications.map((n) => (
                      <div key={n.id} className={`px-4 py-3 border-b border-border last:border-0 ${!n.read ? "bg-accent/50" : ""}`}>
                        <div className="flex items-start gap-2">
                          <div className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${!n.read ? "bg-primary" : "bg-transparent"}`} />
                          <div>
                            <div className="text-xs text-foreground">{n.text}</div>
                            <div className="text-[10px] text-muted-foreground mt-0.5">{n.time}</div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                  <Separator />
                  <div className="px-4 py-2.5">
                    <button
                      onClick={markAllRead}
                      className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                    >
                      Отметить все прочитанными
                    </button>
                  </div>
                </div>
              )}

              {/* Mobile bottom sheet (only on mobile) */}
              {isMobile && (
                <Sheet open={bellOpen} onOpenChange={setBellOpen}>
                  <SheetContent side="bottom" className="rounded-t-xl max-h-[75vh] flex flex-col">
                    <SheetHeader>
                      <SheetTitle>Уведомления</SheetTitle>
                      <SheetDescription className="sr-only">Список уведомлений Brand Portal</SheetDescription>
                    </SheetHeader>
                    <div className="overflow-y-auto flex-1 -mx-4">
                      {notifications.map((n) => (
                        <div key={n.id} className={`px-5 py-4 border-b border-border last:border-0 ${!n.read ? "bg-accent/50" : ""}`}>
                          <div className="flex items-start gap-3">
                            <div className={`w-2 h-2 rounded-full mt-1 flex-shrink-0 ${!n.read ? "bg-primary" : "bg-muted"}`} />
                            <div className="flex-1 min-w-0">
                              <div className="text-sm text-foreground">{n.text}</div>
                              <div className="text-xs text-muted-foreground mt-0.5">{n.time}</div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="-mx-4 px-5 py-4 border-t border-border">
                      <Button variant="outline" className="w-full" onClick={markAllRead}>
                        Отметить все прочитанными
                      </Button>
                    </div>
                  </SheetContent>
                </Sheet>
              )}
            </div>

          </div>
        </header>

        {/* Content — wrapped in ErrorBoundary */}
        <main className="flex-1 overflow-y-auto">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
