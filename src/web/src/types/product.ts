export interface Product {
  id: string;
  apiId?: string;
  brand: string;
  name: string;
  category: string;
  subcategory: string;
  price: number;
  originalPrice?: number;
  badge?: "New arrival" | "Sale";
  sizes: string[];
  images: string[];
  description: string;
  inStock: boolean;
  gender: "Men" | "Women" | "Unisex";
  material?: string;
  careInstructions?: string;
  season?: string;
  variantIdsBySize?: Record<string, string>;
}

export const CATEGORY_LABELS: Record<string, string> = {
  "New arrivals": "Новинки",
  Sale: "Sale",
  Clothing: "Одежда",
  Footwear: "Обувь",
  Accessories: "Аксессуары",
  Lifestyle: "Лайфстайл",
  Coats: "Пальто",
  Hoodies: "Худи",
  Pants: "Брюки",
  "T-Shirts": "Футболки",
  Jeans: "Джинсы",
  Jackets: "Куртки",
  Knitwear: "Трикотаж",
  Underwear: "Нижнее белье",
  Boots: "Ботинки",
  Sneakers: "Кроссовки",
  Sandals: "Сандалии",
  Loafers: "Лоферы",
  Bags: "Сумки",
  Belts: "Ремни",
  Hats: "Головные уборы",
  Scarves: "Шарфы",
};

export const BADGE_LABELS: Record<string, string> = {
  "New arrival": "Новинка",
  Sale: "Sale",
};
