import {
  ArrowUpRight,
  Banknote,
  PackageCheck,
  ReceiptText,
  RefreshCw,
  ShoppingBag,
} from "lucide-react";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./ui/table";
import { ORDER_STATUS_COLORS } from "./constants";

const metrics = [
  {
    label: "Выручка",
    value: "248 500 ₽",
    trend: "+12.5%",
    icon: Banknote,
  },
  {
    label: "Заказы",
    value: "43",
    trend: "+8.2%",
    icon: ShoppingBag,
  },
  {
    label: "Средний чек",
    value: "5 779 ₽",
    trend: "+3.4%",
    icon: ReceiptText,
  },
];

const recentOrders = [
  {
    id: "ORD-4821",
    date: "04.03.2026",
    customer: "Анна К.",
    amount: "4 990 ₽",
    status: "Новый",
  },
  {
    id: "ORD-4819",
    date: "04.03.2026",
    customer: "Игорь С.",
    amount: "12 480 ₽",
    status: "Собирается",
  },
  {
    id: "ORD-4818",
    date: "03.03.2026",
    customer: "Мария П.",
    amount: "7 300 ₽",
    status: "Отправлен",
  },
  {
    id: "ORD-4815",
    date: "03.03.2026",
    customer: "Ольга Н.",
    amount: "3 990 ₽",
    status: "Доставлен",
  },
  {
    id: "ORD-4811",
    date: "02.03.2026",
    customer: "Денис М.",
    amount: "9 850 ₽",
    status: "Отменён",
  },
];

const syncHistory = [
  { date: "04.03.2026 12:30", status: "Успешно", products: 248 },
  { date: "03.03.2026 12:30", status: "Успешно", products: 247 },
  { date: "02.03.2026 12:30", status: "Ошибка", products: 0 },
];

export function Dashboard() {
  return (
    <section className="p-4 md:p-6 space-y-6 overflow-y-auto">
      <div>
        <h1 className="text-xl text-foreground">Статистика</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Ключевые показатели бренда за текущий период
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {metrics.map((metric) => (
          <Card key={metric.label}>
            <CardContent className="p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-3">
                  <div className="text-sm text-muted-foreground">{metric.label}</div>
                  <div className="text-2xl text-foreground">{metric.value}</div>
                  <div className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                    <ArrowUpRight size={13} strokeWidth={1.5} />
                    <span>{metric.trend}</span>
                  </div>
                </div>
                <div className="w-10 h-10 rounded-md bg-muted flex items-center justify-center flex-shrink-0">
                  <metric.icon size={18} strokeWidth={1.5} className="text-foreground" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader className="p-5 pb-0">
          <CardTitle className="text-base text-foreground">Последние заказы</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="hidden md:block">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Заказ</TableHead>
                  <TableHead>Дата</TableHead>
                  <TableHead>Покупатель</TableHead>
                  <TableHead className="text-right">Сумма</TableHead>
                  <TableHead className="text-right">Статус</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentOrders.map((order) => (
                  <TableRow key={order.id}>
                    <TableCell className="text-foreground">{order.id}</TableCell>
                    <TableCell className="text-muted-foreground">{order.date}</TableCell>
                    <TableCell className="text-foreground">{order.customer}</TableCell>
                    <TableCell className="text-right text-foreground">{order.amount}</TableCell>
                    <TableCell className="text-right">
                      <Badge className={ORDER_STATUS_COLORS[order.status]}>
                        {order.status}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div className="md:hidden divide-y divide-border">
            {recentOrders.map((order) => (
              <div key={order.id} className="p-5 space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm text-foreground">{order.id}</div>
                    <div className="text-xs text-muted-foreground mt-1">{order.date}</div>
                  </div>
                  <Badge className={ORDER_STATUS_COLORS[order.status]}>
                    {order.status}
                  </Badge>
                </div>
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span className="text-muted-foreground">{order.customer}</span>
                  <span className="text-foreground">{order.amount}</span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="p-5 pb-0">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <CardTitle className="text-base text-foreground">YML синхронизация</CardTitle>
              <p className="text-sm text-muted-foreground mt-1">
                История обновления каталога
              </p>
            </div>
            <Button>
              <RefreshCw size={16} strokeWidth={1.5} />
              Синхронизировать
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-5">
          <div className="divide-y divide-border">
            {syncHistory.map((item) => (
              <div key={item.date} className="py-3 first:pt-0 last:pb-0 flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-sm text-foreground">{item.date}</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {item.products} товаров
                  </div>
                </div>
                <Badge variant="outline" className="gap-1">
                  <PackageCheck size={12} strokeWidth={1.5} />
                  {item.status}
                </Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
