// Shared status color mappings — single source of truth
// Uses Tailwind theme tokens for consistency with shadcn/ui

export const ORDER_STATUS_COLORS: Record<string, string> = {
  paid: "bg-yellow-100 text-yellow-800",
  processing: "bg-blue-100 text-blue-800",
  shipped: "bg-purple-100 text-purple-800",
  delivered: "bg-green-100 text-green-800",
  completed: "bg-gray-100 text-gray-600",
  cancelled_by_brand: "bg-red-100 text-red-800",
  cancelled_by_buyer: "bg-red-100 text-red-800",
  "Новый": "bg-primary text-primary-foreground",
  "Собирается": "bg-primary/70 text-primary-foreground",
  "Отправлен": "bg-muted-foreground text-primary-foreground",
  "Доставлен": "bg-muted text-foreground",
  "Отменён": "bg-muted text-muted-foreground",
};

export const PRODUCT_STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  hidden: "bg-yellow-100 text-yellow-800",
  archived: "bg-gray-100 text-gray-600",
  "Активен": "bg-muted text-foreground",
  "Скрыт": "bg-muted text-muted-foreground",
  "Архив": "bg-muted text-muted-foreground",
};

export const PAYOUT_STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  "Выплачено": "bg-muted text-foreground",
  "Ожидает": "bg-primary text-primary-foreground",
};
