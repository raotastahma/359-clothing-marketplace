import { useEffect, useMemo, useState } from "react";
import { ChevronDown, Clock3, PackageCheck, Search, Truck, X } from "lucide-react";
import { requestJson, type ApiResponse, type PaginatedApiResponse } from "../api";
import { ORDER_STATUS_COLORS } from "./constants";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";
import { Checkbox } from "./ui/checkbox";
import { Input } from "./ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { Separator } from "./ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "./ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./ui/table";

const ORDER_STATUS_LABELS: Record<string, string> = {
  pending: "Ожидает оплаты",
  paid: "Ожидает подтверждения",
  processing: "Собирается",
  shipped: "Отправлен",
  delivered: "Доставлен",
  completed: "Завершён",
  cancelled_by_brand: "Отменён брендом",
  cancelled_by_buyer: "Отменён покупателем",
  returned: "Возврат",
};

const STATUS_OPTIONS = Object.keys(ORDER_STATUS_LABELS);
const PERIOD_OPTIONS = ["Сегодня", "7 дней", "30 дней"];

interface OrderItem {
  product_name: string;
  size: string;
  quantity: number;
  unit_price: number;
  image_url?: string | null;
}

interface Order {
  id: string;
  parent_order_id?: string;
  status: string;
  created_at: string;
  confirmation_deadline?: string;
  shipping_deadline?: string;
  delivery_address?: Record<string, unknown> | null;
  items: OrderItem[];
  total_amount?: number;
  items_total?: number;
  commission_total?: number;
  payout_amount?: number;
  sla_status?: string;
  tracking_number?: string;
}

type OrderAction = Pick<
  Order,
  | "id"
  | "status"
  | "confirmation_deadline"
  | "shipping_deadline"
  | "sla_status"
  | "tracking_number"
>;

interface FilterDropdownProps {
  label: string;
  options: string[];
  selected: string[];
  onChange: (value: string[]) => void;
  renderOption?: (option: string) => React.ReactNode;
}

function FilterDropdown({ label, options, selected, onChange, renderOption }: FilterDropdownProps) {
  const [open, setOpen] = useState(false);
  const isActive = selected.length > 0;

  const toggle = (option: string) => {
    onChange(
      selected.includes(option)
        ? selected.filter((item) => item !== option)
        : [...selected, option],
    );
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className={isActive ? "border-foreground" : ""}>
          {label}
          {isActive && (
            <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[9px] text-primary-foreground">
              {selected.length}
            </span>
          )}
          <ChevronDown size={13} strokeWidth={1.5} className={open ? "rotate-180 transition-transform" : "transition-transform"} />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-auto min-w-[190px] p-0">
        {options.map((option) => {
          const checked = selected.includes(option);
          return (
            <button
              key={option}
              type="button"
              onClick={() => toggle(option)}
              className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-accent"
            >
              <Checkbox checked={checked} className="pointer-events-none" />
              {renderOption ? renderOption(option) : <span className="text-sm text-foreground">{option}</span>}
            </button>
          );
        })}
        {isActive && (
          <button
            type="button"
            onClick={() => {
              onChange([]);
              setOpen(false);
            }}
            className="flex w-full items-center gap-2 border-t border-border px-4 py-2 text-xs text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <X size={11} strokeWidth={1.5} />
            Сбросить
          </button>
        )}
      </PopoverContent>
    </Popover>
  );
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function getSlaDeadline(order: Order) {
  if (order.status === "paid" && order.confirmation_deadline) {
    return {
      label: "До подтверждения",
      deadline: order.confirmation_deadline,
    };
  }

  if (order.status === "processing" && order.shipping_deadline) {
    return {
      label: "До отправки",
      deadline: order.shipping_deadline,
    };
  }

  return null;
}

function formatSlaRemaining(deadline: string, now: number) {
  const remaining = new Date(deadline).getTime() - now;
  const absolute = Math.abs(remaining);
  const hours = Math.floor(absolute / 3600000);
  const minutes = Math.floor((absolute % 3600000) / 60000);
  const text = `${hours} ч ${minutes} мин`;

  if (remaining < 0) {
    return {
      color: "text-red-600",
      text: `Просрочено: ${text}`,
    };
  }

  if (remaining < 3600000) {
    return {
      color: "text-red-500",
      text,
    };
  }

  if (remaining <= 4 * 3600000) {
    return {
      color: "text-orange-500",
      text,
    };
  }

  return {
    color: "text-gray-500",
    text,
  };
}

function SlaTimer({ label, deadline }: { label: string; deadline: string }) {
  const [now, setNow] = useState(Date.now());
  const remaining = formatSlaRemaining(deadline, now);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <span className={`inline-flex items-center gap-1 text-sm ${remaining.color}`}>
      <Clock3 size={13} strokeWidth={1.5} />
      {label}: {remaining.text}
    </span>
  );
}

function OrderStatusBadge({ status }: { status: string }) {
  return <Badge className={ORDER_STATUS_COLORS[status] ?? ORDER_STATUS_COLORS.pending}>{ORDER_STATUS_LABELS[status] ?? status}</Badge>;
}

function formatDeliveryAddress(value: Record<string, unknown> | null | undefined) {
  if (!value) return "—";
  const parts = Object.values(value).filter((part) => typeof part === "string" || typeof part === "number");
  return parts.join(", ") || "—";
}

function orderItemsTotal(order: Order) {
  return order.items_total ?? order.total_amount ?? 0;
}

function orderCommissionTotal(order: Order) {
  if (order.commission_total !== undefined) return order.commission_total;
  if (order.payout_amount === undefined) return 0;
  return Math.max(orderItemsTotal(order) - order.payout_amount, 0);
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Не удалось загрузить данные.";
}

function isInPeriod(order: Order, selectedPeriods: string[]) {
  if (selectedPeriods.length === 0) {
    return true;
  }

  const createdAt = new Date(order.created_at).getTime();
  const now = Date.now();

  return selectedPeriods.some((period) => {
    if (period === "Сегодня") {
      return new Date(order.created_at).toDateString() === new Date().toDateString();
    }

    if (period === "7 дней") {
      return now - createdAt <= 7 * 86400000;
    }

    return now - createdAt <= 30 * 86400000;
  });
}

function OrderDetail({
  order,
  trackingValue,
  onTrackingChange,
  onConfirm,
  onShip,
}: {
  order: Order | null;
  trackingValue: string;
  onTrackingChange: (value: string) => void;
  onConfirm: (id: string) => void;
  onShip: (id: string) => void;
}) {
  if (!order) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-muted-foreground">
        Выберите заказ, чтобы посмотреть детали
      </div>
    );
  }

  const sla = getSlaDeadline(order);
  const itemsTotal = orderItemsTotal(order);
  const commissionTotal = orderCommissionTotal(order);
  const payoutTotal = order.payout_amount ?? itemsTotal - commissionTotal;

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="space-y-2 p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm text-muted-foreground">Подзаказ</p>
            <h2 className="text-foreground">{order.id}</h2>
          </div>
          <OrderStatusBadge status={order.status} />
        </div>
        <p className="text-sm text-muted-foreground">Создан {formatDate(order.created_at)}</p>
        {sla && <SlaTimer label={sla.label} deadline={sla.deadline} />}
      </div>

      <Separator />

      <div className="space-y-5 p-5">
        <section className="space-y-1">
          <h3 className="text-sm text-foreground">Основной заказ</h3>
          <p className="text-sm text-muted-foreground">{order.parent_order_id ?? "—"}</p>
        </section>

        <section className="space-y-1">
          <h3 className="text-sm text-foreground">Доставка</h3>
          <p className="text-sm text-muted-foreground">{formatDeliveryAddress(order.delivery_address)}</p>
          {order.tracking_number && (
            <p className="text-sm text-muted-foreground">Трек-номер: {order.tracking_number}</p>
          )}
        </section>

        <section className="space-y-3">
          <h3 className="text-sm text-foreground">Товары</h3>
          {order.items.map((item) => (
            <div key={`${order.id}-${item.product_name}-${item.size}`} className="flex gap-3">
              <div className="flex size-14 shrink-0 items-center justify-center rounded-md bg-muted text-xs text-muted-foreground">
                <PackageCheck size={18} strokeWidth={1.5} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-foreground">{item.product_name}</p>
                <p className="text-xs text-muted-foreground">Размер {item.size} · {item.quantity} шт.</p>
                <p className="text-sm text-foreground">{formatCurrency(item.unit_price)}</p>
              </div>
            </div>
          ))}
        </section>

        <section className="space-y-2 rounded-md bg-muted/50 p-3">
          <div className="flex justify-between gap-4 text-sm">
            <span className="text-muted-foreground">Товары</span>
            <span className="text-foreground">{formatCurrency(itemsTotal)}</span>
          </div>
          <div className="flex justify-between gap-4 text-sm">
            <span className="text-muted-foreground">Комиссия</span>
            <span className="text-foreground">-{formatCurrency(commissionTotal)}</span>
          </div>
          <Separator />
          <div className="flex justify-between gap-4 text-sm">
            <span className="text-foreground">К выплате</span>
            <span className="text-foreground">{formatCurrency(payoutTotal)}</span>
          </div>
        </section>

        {order.status === "paid" && (
          <Button className="w-full" onClick={() => onConfirm(order.id)}>
            <PackageCheck size={14} strokeWidth={1.5} />
            Подтвердить и начать сборку
          </Button>
        )}

        {order.status === "processing" && (
          <div className="space-y-2">
            <Input
              value={trackingValue}
              onChange={(event) => onTrackingChange(event.target.value)}
              placeholder="Трек-номер"
            />
            <Button className="w-full" onClick={() => onShip(order.id)} disabled={!trackingValue.trim()}>
              <Truck size={14} strokeWidth={1.5} />
              Отправить
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

export function Orders() {
  const [isDetailSheetLayout, setIsDetailSheetLayout] = useState(false);
  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filterPeriod, setFilterPeriod] = useState<string[]>([]);
  const [filterStatus, setFilterStatus] = useState<string[]>([]);
  const [trackingByOrder, setTrackingByOrder] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const selectedOrder = useMemo(
    () => orders.find((order) => order.id === selectedId) ?? null,
    [orders, selectedId],
  );

  useEffect(() => {
    const mql = window.matchMedia("(max-width: 1023px)");
    const onChange = () => setIsDetailSheetLayout(window.innerWidth < 1024);

    onChange();
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    let ignore = false;

    setIsLoading(true);
    setError(null);
    requestJson<PaginatedApiResponse<Order>>("/brand-portal/orders?per_page=100")
      .then((response) => {
        if (!ignore) setOrders(response.data);
      })
      .catch((requestError: unknown) => {
        if (!ignore) setError(errorMessage(requestError));
      })
      .finally(() => {
        if (!ignore) setIsLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedId) return;

    let ignore = false;
    requestJson<ApiResponse<Order>>(`/brand-portal/orders/${selectedId}`)
      .then((response) => {
        if (ignore) return;
        setOrders((current) =>
          current.map((order) => (order.id === selectedId ? { ...order, ...response.data } : order)),
        );
      })
      .catch((requestError: unknown) => {
        if (!ignore) setError(errorMessage(requestError));
      });

    return () => {
      ignore = true;
    };
  }, [selectedId]);

  const filteredOrders = useMemo(
    () =>
      orders.filter((order) => {
        const matchSearch = order.id.toLowerCase().includes(search.toLowerCase());
        const matchStatus = filterStatus.length === 0 || filterStatus.includes(order.status);
        return matchSearch && matchStatus && isInPeriod(order, filterPeriod);
      }),
    [filterPeriod, filterStatus, orders, search],
  );

  const hasActiveFilters = filterPeriod.length > 0 || filterStatus.length > 0;

  const selectOrder = (id: string) => {
    setSelectedId(id);
  };

  const confirmOrder = async (id: string) => {
    try {
      const response = await requestJson<ApiResponse<OrderAction>>(`/brand-portal/orders/${id}/confirm`, {
        method: "POST",
      });
      setOrders((current) =>
        current.map((order) => (order.id === id ? { ...order, ...response.data } : order)),
      );
    } catch (requestError) {
      setError(errorMessage(requestError));
    }
  };

  const shipOrder = async (id: string) => {
    const trackingNumber = trackingByOrder[id]?.trim();
    if (!trackingNumber) {
      return;
    }

    try {
      const response = await requestJson<ApiResponse<OrderAction>>(`/brand-portal/orders/${id}/ship`, {
        method: "POST",
        body: { tracking_number: trackingNumber },
      });
      setOrders((current) =>
        current.map((order) => (order.id === id ? { ...order, ...response.data } : order)),
      );
    } catch (requestError) {
      setError(errorMessage(requestError));
    }
  };

  const resetFilters = () => {
    setFilterPeriod([]);
    setFilterStatus([]);
  };

  return (
    <section className="p-4 md:p-8">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3 md:mb-6">
        <div>
          <h1 className="text-foreground">Заказы</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">{orders.length} подзаказов · {filteredOrders.length} в списке</p>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2 md:gap-3">
        <div className="relative min-w-[220px] flex-1 sm:max-w-xs">
          <Search size={14} strokeWidth={1.5} className="absolute left-3 top-1/2 z-10 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Поиск по ID заказа"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="pl-9"
          />
        </div>
        <FilterDropdown label="Период" options={PERIOD_OPTIONS} selected={filterPeriod} onChange={setFilterPeriod} />
        <FilterDropdown
          label="Статус"
          options={STATUS_OPTIONS}
          selected={filterStatus}
          onChange={setFilterStatus}
          renderOption={(option) => <OrderStatusBadge status={option} />}
        />
        {hasActiveFilters && (
          <Button variant="ghost" size="sm" onClick={resetFilters} className="text-muted-foreground">
            <X size={13} strokeWidth={1.5} />
            Сбросить
          </Button>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div>
          <div className="hidden overflow-x-auto rounded-md border border-border bg-card md:block">
            <Table className="min-w-[860px]">
              <TableHeader>
                <TableRow className="bg-muted/50 hover:bg-muted/50">
                  <TableHead className="px-4">Заказ (ID)</TableHead>
                  <TableHead>Дата</TableHead>
                  <TableHead>Основной заказ</TableHead>
                  <TableHead>Товары</TableHead>
                  <TableHead>Сумма</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead>SLA</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={7} className="px-5 py-10 text-center text-sm text-muted-foreground">
                      Загрузка заказов...
                    </TableCell>
                  </TableRow>
                ) : filteredOrders.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="px-5 py-10 text-center text-sm text-muted-foreground">
                      Заказы не найдены
                    </TableCell>
                  </TableRow>
                ) : filteredOrders.map((order) => {
                  const sla = getSlaDeadline(order);
                  return (
                    <TableRow
                      key={order.id}
                      onClick={() => selectOrder(order.id)}
                      className={selectedId === order.id ? "cursor-pointer bg-accent" : "cursor-pointer"}
                    >
                      <TableCell className="px-4 text-foreground">{order.id}</TableCell>
                      <TableCell className="text-muted-foreground">{formatDate(order.created_at)}</TableCell>
                      <TableCell className="text-foreground">{order.parent_order_id ?? "—"}</TableCell>
                      <TableCell className="text-muted-foreground">{order.items.length}</TableCell>
                      <TableCell className="text-foreground">{formatCurrency(orderItemsTotal(order))}</TableCell>
                      <TableCell><OrderStatusBadge status={order.status} /></TableCell>
                      <TableCell>
                        {sla ? <SlaTimer label={sla.label} deadline={sla.deadline} /> : <span className="text-sm text-muted-foreground">—</span>}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>

          <div className="space-y-3 md:hidden">
            {isLoading && (
              <div className="rounded-md border border-border bg-card p-5 text-center text-sm text-muted-foreground">
                Загрузка заказов...
              </div>
            )}
            {!isLoading && filteredOrders.length === 0 && (
              <div className="rounded-md border border-border bg-card p-5 text-center text-sm text-muted-foreground">
                Заказы не найдены
              </div>
            )}
            {!isLoading && filteredOrders.map((order) => {
              const sla = getSlaDeadline(order);
              return (
                <Card key={order.id} className="rounded-md" onClick={() => selectOrder(order.id)}>
                  <CardContent className="space-y-3 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm text-foreground">{order.id}</p>
                        <p className="text-xs text-muted-foreground">{formatDate(order.created_at)}</p>
                      </div>
                      <OrderStatusBadge status={order.status} />
                    </div>
                    <div className="flex items-center justify-between gap-4 text-sm">
                      <span className="text-muted-foreground">{order.parent_order_id ?? "—"}</span>
                      <span className="text-foreground">{formatCurrency(orderItemsTotal(order))}</span>
                    </div>
                    {sla && <SlaTimer label={sla.label} deadline={sla.deadline} />}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>

        <aside className="hidden min-h-[640px] rounded-md border border-border bg-card lg:block">
          <OrderDetail
            order={selectedOrder}
            trackingValue={selectedOrder ? trackingByOrder[selectedOrder.id] ?? "" : ""}
            onTrackingChange={(value) => {
              if (selectedOrder) {
                setTrackingByOrder((current) => ({ ...current, [selectedOrder.id]: value }));
              }
            }}
            onConfirm={confirmOrder}
            onShip={shipOrder}
          />
        </aside>
      </div>

      <Sheet open={isDetailSheetLayout && !!selectedOrder} onOpenChange={(open) => !open && setSelectedId(null)}>
        <SheetContent side="bottom" className="max-h-[86vh] rounded-t-xl p-0">
          <SheetHeader className="sr-only">
            <SheetTitle>Детали заказа</SheetTitle>
            <SheetDescription>Информация о выбранном подзаказе</SheetDescription>
          </SheetHeader>
          <OrderDetail
            order={selectedOrder}
            trackingValue={selectedOrder ? trackingByOrder[selectedOrder.id] ?? "" : ""}
            onTrackingChange={(value) => {
              if (selectedOrder) {
                setTrackingByOrder((current) => ({ ...current, [selectedOrder.id]: value }));
              }
            }}
            onConfirm={confirmOrder}
            onShip={shipOrder}
          />
        </SheetContent>
      </Sheet>
    </section>
  );
}
