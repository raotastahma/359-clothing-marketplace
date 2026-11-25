import { useEffect, useMemo, useState } from "react";
import { CalendarDays, ChevronDown, Info, Search, X } from "lucide-react";
import { requestJson, type PaginatedApiResponse } from "../api";
import { PAYOUT_STATUS_COLORS } from "./constants";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";
import { Checkbox } from "./ui/checkbox";
import { Input } from "./ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./ui/table";

const PAYOUT_STATUS_LABELS: Record<PayoutStatus, string> = {
  pending: "Ожидает выплаты",
  scheduled: "Запланировано",
  processing: "В обработке",
  completed: "Выплачено",
  paid: "Выплачено",
  failed: "Ошибка",
};

type PayoutStatus = "pending" | "scheduled" | "processing" | "completed" | "paid" | "failed";

type ApiPayout = {
  id: string;
  sub_order_id: string;
  amount: number;
  commission_rate: number;
  status: PayoutStatus;
  scheduled_at: string;
  completed_at: string | null;
  created_at: string;
};

type Payout = {
  id: string;
  period: string;
  items_total: number;
  commission_amount: number;
  payout_amount: number;
  commission_rate: number;
  scheduled_at: string;
  status: PayoutStatus;
};

type FilterDropdownProps = {
  label: string;
  options: string[];
  selected: string[];
  onChange: (value: string[]) => void;
  getOptionLabel?: (option: string) => string;
};

const formatCurrency = (value: number) =>
  new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(value);

const formatDate = (value: string) =>
  new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));

const formatPeriod = (value: string) =>
  new Intl.DateTimeFormat("ru-RU", {
    month: "long",
    year: "numeric",
  }).format(new Date(value));

const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : "Не удалось загрузить выплаты.";

function mapPayout(payout: ApiPayout): Payout {
  const payoutAmount = Number(payout.amount);
  const commissionRate = Number(payout.commission_rate);
  const itemsTotal = commissionRate >= 1 ? payoutAmount : payoutAmount / (1 - commissionRate);

  return {
    id: payout.id,
    period: formatPeriod(payout.scheduled_at),
    items_total: itemsTotal,
    commission_amount: itemsTotal - payoutAmount,
    payout_amount: payoutAmount,
    commission_rate: commissionRate,
    scheduled_at: payout.scheduled_at,
    status: payout.status,
  };
}

function FilterDropdown({ label, options, selected, onChange, getOptionLabel }: FilterDropdownProps) {
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
              <span className="text-sm text-foreground">{getOptionLabel ? getOptionLabel(option) : option}</span>
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

export function Finances() {
  const [search, setSearch] = useState("");
  const [periods, setPeriods] = useState<string[]>([]);
  const [statuses, setStatuses] = useState<string[]>([]);
  const [payouts, setPayouts] = useState<Payout[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;

    setIsLoading(true);
    setError(null);
    requestJson<PaginatedApiResponse<ApiPayout>>("/brand-portal/payouts?per_page=100")
      .then((response) => {
        if (!ignore) setPayouts(response.data.map(mapPayout));
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

  const periodOptions = useMemo(() => Array.from(new Set(payouts.map((payout) => payout.period))), [payouts]);
  const statusOptions = useMemo(() => Array.from(new Set(payouts.map((payout) => payout.status))), [payouts]);

  const filteredPayouts = useMemo(
    () =>
      payouts.filter((payout) => {
        const query = search.toLowerCase();
        const matchesSearch =
          payout.period.toLowerCase().includes(query) ||
          PAYOUT_STATUS_LABELS[payout.status].toLowerCase().includes(query);
        const matchesPeriod = periods.length === 0 || periods.includes(payout.period);
        const matchesStatus = statuses.length === 0 || statuses.includes(payout.status);
        return matchesSearch && matchesPeriod && matchesStatus;
      }),
    [payouts, periods, search, statuses],
  );

  const pendingPayouts = payouts.filter((payout) => ["pending", "scheduled", "processing"].includes(payout.status));
  const pendingAmount = pendingPayouts.reduce((sum, payout) => sum + payout.payout_amount, 0);
  const completedAmount = payouts.filter((payout) => ["completed", "paid"].includes(payout.status)).reduce(
    (sum, payout) => sum + payout.payout_amount,
    0,
  );
  const nextPayout = pendingPayouts
    .slice()
    .sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at))[0];
  const commissionRate = payouts[0]?.commission_rate;

  return (
    <section className="p-4 md:p-8">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3 md:mb-6">
        <div>
          <h1 className="text-foreground">Финансы</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">Выплаты, комиссии и история расчётов</p>
        </div>
      </div>

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardContent className="p-4 md:p-5">
            <div className="mb-3 text-xs uppercase tracking-wider text-muted-foreground">Баланс</div>
            <div className="text-2xl text-foreground">{formatCurrency(pendingAmount)}</div>
            <p className="mt-1 text-xs text-muted-foreground">К выплате</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 md:p-5">
            <div className="mb-3 text-xs uppercase tracking-wider text-muted-foreground">Ожидает выплаты</div>
            <div className="text-2xl text-foreground">{nextPayout ? formatDate(nextPayout.scheduled_at) : "—"}</div>
            <p className="mt-1 text-xs text-muted-foreground">Ближайшая выплата</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 md:p-5">
            <div className="mb-3 text-xs uppercase tracking-wider text-muted-foreground">Выплачено всего</div>
            <div className="text-2xl text-foreground">{formatCurrency(completedAmount)}</div>
            <p className="mt-1 text-xs text-muted-foreground">Завершённые выплаты</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 md:p-5">
            <div className="mb-3 text-xs uppercase tracking-wider text-muted-foreground">Комиссия</div>
            <div className="text-2xl text-foreground">{commissionRate === undefined ? "—" : `${commissionRate * 100}%`}</div>
            <p className="mt-1 text-xs text-muted-foreground">Индивидуальная ставка бренда</p>
          </CardContent>
        </Card>
      </div>

      <div className="mb-5 flex gap-2 rounded-md border border-border bg-muted/50 p-3 text-sm text-muted-foreground">
        <Info size={15} strokeWidth={1.5} className="mt-0.5 shrink-0" />
        <p>Выплаты производятся 2 раза в месяц — 1-го и 15-го числа, но не ранее 14 дней после доставки заказа.</p>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2 md:gap-3">
        <div className="relative min-w-[220px] flex-1 sm:max-w-xs">
          <Search size={14} strokeWidth={1.5} className="absolute left-3 top-1/2 z-10 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Поиск по периоду или статусу"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="pl-9"
          />
        </div>
        <FilterDropdown label="Период" options={periodOptions} selected={periods} onChange={setPeriods} />
        <FilterDropdown
          label="Статус"
          options={statusOptions}
          selected={statuses}
          onChange={setStatuses}
          getOptionLabel={(option) => PAYOUT_STATUS_LABELS[option as PayoutStatus]}
        />
        {(periods.length > 0 || statuses.length > 0) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setPeriods([]);
              setStatuses([]);
            }}
            className="text-muted-foreground"
          >
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

      <div className="space-y-3 md:hidden">
        {isLoading && (
          <div className="rounded-md border border-border bg-card p-5 text-center text-sm text-muted-foreground">
            Загрузка выплат...
          </div>
        )}
        {!isLoading && filteredPayouts.length === 0 && (
          <div className="rounded-md border border-border bg-card p-5 text-center text-sm text-muted-foreground">
            Выплаты не найдены
          </div>
        )}
        {!isLoading && filteredPayouts.map((payout) => (
          <Card key={payout.id}>
            <CardContent className="p-4">
              <div className="mb-3 flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm text-foreground">{payout.period}</div>
                  <div className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
                    <CalendarDays size={12} strokeWidth={1.5} />
                    {formatDate(payout.scheduled_at)}
                  </div>
                </div>
                <Badge className={PAYOUT_STATUS_COLORS[payout.status] ?? PAYOUT_STATUS_COLORS.pending}>{PAYOUT_STATUS_LABELS[payout.status]}</Badge>
              </div>
              <div className="grid grid-cols-2 gap-3 border-t border-border pt-3 text-sm">
                <div>
                  <div className="text-xs text-muted-foreground">Сумма</div>
                  <div className="text-foreground">{formatCurrency(payout.items_total)}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Комиссия</div>
                  <div className="text-foreground">{formatCurrency(payout.commission_amount)}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">К выплате</div>
                  <div className="text-foreground">{formatCurrency(payout.payout_amount)}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Статус</div>
                  <div className="text-foreground">{PAYOUT_STATUS_LABELS[payout.status]}</div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="hidden overflow-hidden rounded-md border border-border bg-card md:block">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50 hover:bg-muted/50">
              <TableHead className="px-5">Период</TableHead>
              <TableHead className="px-5 text-right">Сумма</TableHead>
              <TableHead className="px-5 text-right">Комиссия</TableHead>
              <TableHead className="px-5 text-right">К выплате</TableHead>
              <TableHead className="px-5">Дата выплаты</TableHead>
              <TableHead className="px-5">Статус</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={6} className="px-5 py-10 text-center text-sm text-muted-foreground">
                  Загрузка выплат...
                </TableCell>
              </TableRow>
            ) : filteredPayouts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="px-5 py-10 text-center text-sm text-muted-foreground">
                  Выплаты не найдены
                </TableCell>
              </TableRow>
            ) : filteredPayouts.map((payout) => (
              <TableRow key={payout.id}>
                <TableCell className="px-5 py-3 text-foreground">{payout.period}</TableCell>
                <TableCell className="px-5 py-3 text-right text-muted-foreground">{formatCurrency(payout.items_total)}</TableCell>
                <TableCell className="px-5 py-3 text-right text-muted-foreground">{formatCurrency(payout.commission_amount)}</TableCell>
                <TableCell className="px-5 py-3 text-right text-foreground">{formatCurrency(payout.payout_amount)}</TableCell>
                <TableCell className="px-5 py-3 text-muted-foreground">{formatDate(payout.scheduled_at)}</TableCell>
                <TableCell className="px-5 py-3">
                  <Badge className={PAYOUT_STATUS_COLORS[payout.status] ?? PAYOUT_STATUS_COLORS.pending}>{PAYOUT_STATUS_LABELS[payout.status]}</Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </section>
  );
}
