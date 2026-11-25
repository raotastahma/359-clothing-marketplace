import { expect, type Page, test } from "@playwright/test";

const apiBase = "http://127.0.0.1:18000/api/v1";
const webBase = "http://127.0.0.1:3200";
const brandBase = "http://127.0.0.1:3201";
const remoteProductImageUrl = "https://catalog-images.example.test/aurora.png";

const brand = {
  id: "brand-359",
  name: "359 Studio",
  slug: "359-studio",
  logo_url: null,
  cover_url: null,
  founded_year: 2024,
  products_count: 3,
};

const brandSession = {
  brand: {
    id: brand.id,
    name: brand.name,
    slug: brand.slug,
    logo_url: brand.logo_url,
  },
  role: "owner",
};

const clothing = { name: "Clothing", slug: "clothing" };
const dresses = { id: "cat-dresses", name: "Dresses", slug: "dresses", gender: "women" };
const hoodies = { id: "cat-hoodies", name: "Hoodies", slug: "hoodies", gender: "unisex" };
const jackets = { id: "cat-jackets", name: "Jackets", slug: "jackets", gender: "men" };

const categories = [
  {
    id: "root-women",
    name: "Женское",
    slug: "women",
    gender: "women",
    sort_order: 1,
    children: [{ ...dresses, sort_order: 1, children: [] }],
  },
  {
    id: "root-men",
    name: "Мужское",
    slug: "men",
    gender: "men",
    sort_order: 2,
    children: [{ ...jackets, sort_order: 1, children: [] }],
  },
  {
    id: "root-unisex",
    name: "Унисекс",
    slug: "unisex",
    gender: "unisex",
    sort_order: 3,
    children: [{ ...hoodies, sort_order: 1, children: [] }],
  },
];

const products = [
  {
    id: "prod-aurora",
    name: "Платье Aurora",
    slug: "aurora-dress",
    brand,
    category: { ...dresses, parent: clothing },
    price_from: 12900,
    compare_at_price_from: null,
    is_new_arrival: true,
    images: [{ url: remoteProductImageUrl, alt_text: null, sort_order: 1 }],
    available_sizes: ["S", "M"],
  },
  {
    id: "prod-unified",
    name: "Худи Unified",
    slug: "unified-hoodie",
    brand,
    category: { ...hoodies, parent: clothing },
    price_from: 8900,
    compare_at_price_from: null,
    is_new_arrival: false,
    images: [{ url: "/logo.svg", alt_text: null, sort_order: 1 }],
    available_sizes: ["M"],
  },
  {
    id: "prod-north",
    name: "Куртка North",
    slug: "north-jacket",
    brand,
    category: { ...jackets, parent: clothing },
    price_from: 15900,
    compare_at_price_from: null,
    is_new_arrival: false,
    images: [{ url: "/logo.svg", alt_text: null, sort_order: 1 }],
    available_sizes: ["L"],
  },
];

const auroraDetail = {
  ...products[0],
  description: "Легкое платье для городского гардероба.\n\nТестовое описание для smoke flow.",
  fabric_composition: "100% хлопок",
  care_instructions: "Деликатная машинная стирка при 30°C",
  season: "SS 2026",
  base_price_rub: 12900,
  sale_price_rub: null,
  variants: [
    {
      id: "variant-aurora-s",
      product_id: "prod-aurora",
      size: "S",
      color: "Черный",
      sku: "AUR-S-BLK",
      price_rub: 12900,
      compare_at_price_rub: null,
      stock_quantity: 5,
      is_active: true,
    },
    {
      id: "variant-aurora-m",
      product_id: "prod-aurora",
      size: "M",
      color: "Черный",
      sku: "AUR-M-BLK",
      price_rub: 12900,
      compare_at_price_rub: null,
      stock_quantity: 3,
      is_active: true,
    },
  ],
  is_active: true,
  created_at: "2026-03-01T10:00:00Z",
};

const apparelSizingDetail = {
  ...auroraDetail,
  id: "prod-apparel-sizing",
  name: "Топ Size Order",
  slug: "apparel-size-order",
  variants: ["XL", "ONE SIZE", "M", "XS", "S"].map((size, index) => ({
    ...auroraDetail.variants[0],
    id: `variant-apparel-${size.toLowerCase().replace(" ", "-")}`,
    size,
    sku: `APPAREL-${index}`,
  })),
};

const footwearSizingDetail = {
  ...auroraDetail,
  id: "prod-footwear-sizing",
  name: "Кроссовки Size Order",
  slug: "footwear-size-order",
  category: {
    id: "cat-sneakers",
    name: "Sneakers",
    slug: "sneakers",
    gender: "unisex",
    parent: { name: "Footwear", slug: "footwear" },
  },
  variants: ["39", "37", "38"].map((size) => ({
    ...auroraDetail.variants[0],
    id: `variant-footwear-${size}`,
    size,
    sku: `FOOTWEAR-${size}`,
  })),
};

const brandCatalogProduct = {
  ...auroraDetail,
  product_status: "active",
  images: [{ id: "image-aurora", url: "/logo.svg", alt_text: null, sort_order: 0 }],
};

const createdImageRetryProduct = {
  ...brandCatalogProduct,
  id: "prod-image-retry",
  name: "Товар с повторной загрузкой",
  slug: "image-retry-product",
  variants: [
    {
      ...auroraDetail.variants[0],
      id: "variant-image-retry",
      product_id: "prod-image-retry",
      size: "M",
      sku: "IMAGE-RETRY-M",
    },
  ],
  images: [],
};

const orderSummary = {
  id: "ORD-SMOKE-1",
  status: "paid",
  total_amount: 12900,
  customer_delivery_cost: 0,
  created_at: "2026-03-04T10:30:00Z",
  sub_orders: [
    {
      id: "SUB-SMOKE-1",
      brand_name: "359 Studio",
      status: "paid",
      tracking_number: null,
      items_count: 1,
    },
  ],
};

const orderDetail = {
  ...orderSummary,
  items: [
    {
      id: "item-1",
      product_name: "Платье Aurora",
      product_slug: "aurora-dress",
      brand_name: "359 Studio",
      size: "S",
      quantity: 1,
      price_rub: 12900,
      image_url: null,
    },
  ],
};

const brandOrders = [
  {
    id: "SUB-SMOKE-1",
    parent_order_id: "ORD-SMOKE-1",
    status: "paid",
    created_at: "2026-03-04T10:30:00Z",
    confirmation_deadline: "2026-03-05T10:30:00Z",
    shipping_deadline: null,
    delivery_address: { city: "Москва", street: "ПВЗ Яндекс.Доставки" },
    items: [{ product_name: "Платье Aurora", size: "S", quantity: 1, unit_price: 12900 }],
    total_amount: 12900,
    items_total: 12900,
    commission_total: 1935,
    payout_amount: 10965,
    sla_status: "ok",
    tracking_number: null,
  },
];

const payouts = [
  {
    id: "PAYOUT-SMOKE-1",
    sub_order_id: "SUB-SMOKE-1",
    amount: 10965,
    commission_rate: 0.15,
    status: "scheduled",
    scheduled_at: "2026-03-15T10:00:00Z",
    completed_at: null,
    created_at: "2026-03-04T11:00:00Z",
  },
];

async function installApiMock(page: Page) {
  await page.route("https://catalog-images.example.test/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "image/png",
      body: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
        "base64",
      ),
    });
  });

  await page.route(`${apiBase}/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/v1", "");
    const method = request.method();

    if (method === "OPTIONS") {
      await route.fulfill({
        status: 204,
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-methods": "GET,POST,PATCH,DELETE,OPTIONS",
          "access-control-allow-headers": "content-type,authorization",
        },
      });
      return;
    }

    const json = async (payload: unknown) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: { "access-control-allow-origin": "*" },
        body: JSON.stringify(payload),
      });
    };

    if (method === "GET" && path === "/categories") {
      await json({ data: categories });
      return;
    }
    if (method === "POST" && path === "/brand-portal/auth/login") {
      await json({
        data: {
          ...brandSession,
          access_token: "brand-test-access-token",
          refresh_token: "brand-test-refresh-token",
          token_type: "bearer",
          expires_in: 3600,
        },
      });
      return;
    }
    if (method === "GET" && path === "/brand-portal/me") {
      await json({ data: brandSession });
      return;
    }
    if (method === "GET" && path === "/brand-portal/products") {
      await json({ data: [brandCatalogProduct], meta: { page: 1, per_page: 20, total: 1 } });
      return;
    }
    if (method === "GET" && path === "/brands") {
      await json({ data: [brand] });
      return;
    }
    if (method === "GET" && path === "/products") {
      const gender = url.searchParams.get("gender");
      const data =
        gender === "women"
          ? products.filter((product) => product.category.gender !== "men")
          : products;
      await json({ data, meta: { page: 1, per_page: 20, total: data.length } });
      return;
    }
    if (method === "GET" && path === "/products/aurora-dress") {
      await json({ data: auroraDetail });
      return;
    }
    if (method === "GET" && path === "/products/apparel-size-order") {
      await json({ data: apparelSizingDetail });
      return;
    }
    if (method === "GET" && path === "/products/footwear-size-order") {
      await json({ data: footwearSizingDetail });
      return;
    }
    if (method === "POST" && path === "/auth/send-code") {
      await json({ data: { message: "sent", expires_in: 60 } });
      return;
    }
    if (method === "POST" && path === "/auth/verify-code") {
      await json({
        data: {
          access_token: "test-access-token",
          refresh_token: "test-refresh-token",
          token_type: "bearer",
          expires_in: 3600,
          user: {
            id: "user-smoke",
            phone: "+79991234567",
            name: null,
            email: null,
            is_verified: true,
          },
        },
      });
      return;
    }
    if (method === "GET" && path === "/users/me") {
      await json({
        data: {
          id: "user-smoke",
          phone: "+79991234567",
          name: "QA Покупатель",
          email: null,
          is_verified: true,
        },
      });
      return;
    }
    if (method === "PATCH" && path === "/users/me") {
      await json({
        data: {
          id: "user-smoke",
          phone: "+79991234567",
          name: "QA Покупатель",
          email: null,
          is_verified: true,
        },
      });
      return;
    }
    if (path === "/users/me/favorites") {
      await json({ data: [products[0]], meta: { page: 1, per_page: 20, total: 1 } });
      return;
    }
    if (path.startsWith("/users/me/favorites/")) {
      await json({ data: {} });
      return;
    }
    if (path === "/users/me/addresses") {
      if (method === "POST") {
        await json({
          data: {
            id: "address-smoke",
            city: "Москва",
            street: "ПВЗ Яндекс.Доставки",
            apartment: null,
            postal_code: "",
            is_default: true,
          },
        });
        return;
      }
      await json({ data: [] });
      return;
    }
    if (path === "/cart/items") {
      if (method === "GET") {
        await json({ data: { items: [], total: 0, items_count: 0 } });
        return;
      }
      await json({ data: { items: [], total: 12900, items_count: 1 } });
      return;
    }
    if (method === "POST" && path === "/orders") {
      await json({
        data: {
          id: "ORD-SMOKE-1",
          status: "pending",
          total_amount: 12900,
          customer_delivery_cost: 0,
          items: orderDetail.items,
          payment_url: `${webBase}/order/success?id=ORD-SMOKE-1`,
        },
      });
      return;
    }
    if (method === "GET" && path === "/orders") {
      await json({ data: [orderSummary], meta: { page: 1, per_page: 20, total: 1 } });
      return;
    }
    if (method === "GET" && path === "/orders/ORD-SMOKE-1") {
      await json({ data: orderDetail });
      return;
    }
    if (method === "GET" && path === "/brand-portal/orders") {
      await json({ data: brandOrders, meta: { page: 1, per_page: 100, total: 1 } });
      return;
    }
    if (method === "GET" && path === "/brand-portal/orders/SUB-SMOKE-1") {
      await json({ data: brandOrders[0] });
      return;
    }
    if (method === "GET" && path === "/brand-portal/payouts") {
      await json({ data: payouts, meta: { page: 1, per_page: 100, total: 1 } });
      return;
    }

    await route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ error: { code: "NOT_MOCKED", message: path } }),
    });
  });
}

async function screenshot(page: Page, name: string) {
  await page.screenshot({ path: `test-results/sti-008/${name}.png`, fullPage: true });
}

function fieldByLabel(page: Page, label: string) {
  return page
    .locator("label", { hasText: new RegExp(`^${label}$`) })
    .locator("xpath=..")
    .locator("input, textarea")
    .first();
}

function variantInput(page: Page, columnIndex: number, rowIndex = 0) {
  return page
    .getByRole("row")
    .filter({ has: page.locator("input") })
    .nth(rowIndex)
    .locator("td")
    .nth(columnIndex)
    .locator("input");
}

async function selectByVisualLabel(page: Page, label: string, option: string): Promise<void> {
  await page
    .locator("label", { hasText: new RegExp(`^${label}$`) })
    .locator("xpath=..")
    .locator('button[role="combobox"]')
    .click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

async function loginToBrandPortal(page: Page, destination = brandBase): Promise<void> {
  await page.goto(destination);
  await expect(page.getByText("Вход для бренда", { exact: true })).toBeVisible();
  await page.getByLabel("Email").fill("brand@example.invalid");
  await page.getByLabel("Пароль").fill("synthetic-mocked-password");
  await page.getByRole("button", { name: "Войти" }).click();
}

test.beforeEach(async ({ page }) => {
  await installApiMock(page);
});

test("remote product images and local SVG placeholders retain their expected URLs", async ({ page }) => {
  const optimizedRemoteRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname === "/_next/image" && url.searchParams.get("url") === remoteProductImageUrl) {
      optimizedRemoteRequests.push(request.url());
    }
  });

  await page.goto(`${webBase}/shop`);
  await expect(page.getByRole("img", { name: "Платье Aurora", exact: true })).toHaveAttribute(
    "src",
    remoteProductImageUrl,
  );
  await expect(page.getByRole("img", { name: "Худи Unified", exact: true })).toHaveAttribute(
    "src",
    "/logo.svg",
  );

  await page.goto(`${webBase}/product/aurora-dress`);
  await expect(page.getByRole("img", { name: "Платье Aurora", exact: true })).toHaveAttribute(
    "src",
    remoteProductImageUrl,
  );
  expect(optimizedRemoteRequests).toEqual([]);
});

test("customer product detail maps care, season, apparel, footwear, and one size", async ({ page }) => {
  await page.goto(`${webBase}/product/aurora-dress`);
  await page.getByRole("button", { name: "Детали" }).click();
  await expect(page.getByText("Уход", { exact: true })).toBeVisible();
  await expect(page.getByText("Деликатная машинная стирка при 30°C", { exact: true })).toBeVisible();
  await expect(page.getByText("Сезон", { exact: true })).toBeVisible();
  await expect(page.getByText("SS 2026", { exact: true })).toBeVisible();

  await page.goto(`${webBase}/product/apparel-size-order`);
  await expect(page.getByRole("heading", { name: "Топ Size Order" })).toBeVisible();
  const apparelSizes = await page.locator("button").evaluateAll((buttons) =>
    buttons
      .map((button) => button.textContent?.trim())
      .filter((text): text is string => ["XS", "S", "M", "XL", "ONE SIZE"].includes(text)),
  );
  expect(apparelSizes).toEqual(["XS", "S", "M", "XL", "ONE SIZE"]);

  await page.goto(`${webBase}/product/footwear-size-order`);
  await expect(page.getByRole("heading", { name: "Кроссовки Size Order" })).toBeVisible();
  const footwearSizes = await page.locator("button").evaluateAll((buttons) =>
    buttons
      .map((button) => button.textContent?.trim())
      .filter((text): text is string => ["37", "38", "39"].includes(text)),
  );
  expect(footwearSizes).toEqual(["37", "38", "39"]);
});

test("customer web catalog to checkout, auth, profile, orders, and favorites smoke", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Перейти в каталог" }).click();
  await expect(page).toHaveURL(/\/shop$/);
  await expect(page.getByText("Платье Aurora")).toBeVisible();
  await screenshot(page, "01-customer-shop");

  await page.getByRole("button", { name: "В избранное" }).first().click();
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "Женское" })
    .click();
  await expect(page).toHaveURL(/\/shop\?gender=Women/);
  await expect(page.getByText("Платье Aurora")).toBeVisible();
  await expect(page.getByText("Худи Unified")).toBeVisible();
  await expect(page.getByText("Куртка North")).toHaveCount(0);
  await screenshot(page, "02-customer-gender-filter");

  await page.getByRole("link", { name: /Платье Aurora/ }).click();
  await expect(page).toHaveURL(/\/product\/aurora-dress/);
  await expect(page.getByRole("heading", { name: "Платье Aurora" })).toBeVisible();
  await page.getByRole("button", { name: "S" }).click();
  await page.getByRole("button", { name: "В корзину" }).click();
  await expect(page.getByRole("dialog", { name: "Корзина" })).toBeVisible();
  await expect(page.getByText("Размер: S")).toBeVisible();
  await screenshot(page, "03-customer-cart-drawer");

  await page.getByRole("link", { name: "Оформить заказ" }).click();
  await expect(page).toHaveURL(/\/checkout/);
  await page.getByLabel("ФИО").fill("QA Покупатель");
  await page.getByLabel("Телефон").fill("+7 999 123-45-67");
  await page.getByRole("button", { name: "Перейти к оплате" }).click();
  await expect(page.getByRole("heading", { name: "Оплата" })).toBeVisible();
  await screenshot(page, "04-customer-checkout-step-2");
  await page.getByRole("button", { name: "Перейти к оплате" }).click();
  await expect(page).toHaveURL(/\/order\/success\?id=ORD-SMOKE-1/);
  await expect(page.getByRole("heading", { name: "Оплата прошла успешно" })).toBeVisible();
  await screenshot(page, "05-customer-checkout-success");

  await page.goto("/login");
  await page.getByPlaceholder("(___) ___-__-__").fill("9991234567");
  await page.getByRole("button", { name: "Получить код" }).click();
  await expect(page.getByRole("heading", { name: "Введите код" })).toBeVisible();
  const otpInputs = page.locator('input[inputmode="numeric"]');
  for (const [index, digit] of ["1", "2", "3", "4"].entries()) {
    await otpInputs.nth(index).fill(digit);
  }
  await expect(page.getByRole("heading", { name: "Как вас зовут?" })).toBeVisible();
  await page.getByPlaceholder("Имя Фамилия").fill("QA Покупатель");
  await page.getByText("Согласен на обработку персональных данных").click();
  await page.getByRole("button", { name: "Продолжить" }).click();
  await expect(page).toHaveURL(/\/profile/);
  await expect(page.getByText("QA Покупатель")).toBeVisible();
  await expect(page.getByText("+79991234567")).toBeVisible();
  await expect(page.getByText("Заказы")).toBeVisible();
  await expect(page.getByText("Избранное")).toBeVisible();
  await screenshot(page, "06-customer-profile");

  await page.goto("/profile/orders");
  await expect(page.getByRole("heading", { name: "Заказы" })).toBeVisible();
  await expect(page.getByText("Заказ ORD-SMOKE-1")).toBeVisible();
  await screenshot(page, "07-customer-orders");

  await page.goto("/favorites");
  await expect(page.getByRole("heading", { name: "Избранное" })).toBeVisible();
  await expect(page.getByText("Платье Aurora")).toBeVisible();
  await screenshot(page, "08-customer-favorites");
});

test("brand portal dashboard, catalog, editor, orders, finances, and settings smoke", async ({
  page,
}) => {
  await loginToBrandPortal(page);
  await expect(page.getByRole("heading", { name: "Статистика" })).toBeVisible();
  await expect(page.getByText("Последние заказы")).toBeVisible();
  await screenshot(page, "09-brand-dashboard");

  await page.goto(`${brandBase}/catalog`);
  await expect(page.getByRole("heading", { name: "Каталог товаров" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Категория" })).toBeVisible();
  await screenshot(page, "10-brand-catalog");

  await page.goto(`${brandBase}/catalog/new`);
  await expect(page.getByRole("heading", { name: "Новый товар" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Основное" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Варианты" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Изображения" })).toBeVisible();
  await screenshot(page, "11-brand-product-editor");

  await page.goto(`${brandBase}/orders`);
  await expect(page.getByRole("heading", { name: "Заказы" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "SUB-SMOKE-1" })).toBeVisible();
  await page.getByRole("cell", { name: "SUB-SMOKE-1" }).click();
  await expect(page.getByText("Подзаказ", { exact: true })).toBeVisible();
  await screenshot(page, "12-brand-orders-detail");

  await page.goto(`${brandBase}/finances`);
  await expect(page.getByRole("heading", { name: "Финансы" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "К выплате" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Запланировано" })).toBeVisible();
  await screenshot(page, "13-brand-finances");

  await page.goto(`${brandBase}/settings`);
  await expect(page.getByRole("heading", { name: "Настройки" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Профиль бренда" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Уведомления" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Реквизиты" })).toBeVisible();
  await screenshot(page, "14-brand-settings");
});

test("brand portal retries a failed new-product image upload without creating a duplicate", async ({
  page,
}) => {
  let productCreateRequests = 0;
  let imageUploadRequests = 0;

  await page.route(`${apiBase}/brand-portal/products**`, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");

    if (request.method() === "POST" && path === "/brand-portal/products") {
      productCreateRequests += 1;
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({ data: createdImageRetryProduct }),
      });
      return;
    }

    if (request.method() === "POST" && path === "/brand-portal/products/prod-image-retry/images") {
      imageUploadRequests += 1;
      await route.fulfill({
        status: imageUploadRequests === 1 ? 500 : 201,
        contentType: "application/json",
        body: JSON.stringify(
          imageUploadRequests === 1
            ? { error: { message: "Хранилище изображений недоступно" } }
            : {
                data: [
                  {
                    id: "image-retry",
                    url: "/logo.svg",
                    alt_text: null,
                    sort_order: 0,
                  },
                ],
              },
        ),
      });
      return;
    }

    if (request.method() === "GET" && path === "/brand-portal/products/prod-image-retry") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: createdImageRetryProduct }),
      });
      return;
    }

    if (request.method() === "PATCH" && path === "/brand-portal/products/prod-image-retry") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: createdImageRetryProduct }),
      });
      return;
    }

    await route.fallback();
  });

  await loginToBrandPortal(page, `${brandBase}/catalog/new`);
  await expect(page.getByRole("heading", { name: "Новый товар" })).toBeVisible();
  await fieldByLabel(page, "Name").fill("Товар с повторной загрузкой");
  await selectByVisualLabel(page, "Category", "Женское / Dresses");
  await page.getByRole("tab", { name: "Варианты" }).click();
  await variantInput(page, 2).fill("M");
  await variantInput(page, 4).fill("IMAGE-RETRY-M");
  await variantInput(page, 5).fill("12900");
  await page.getByRole("tab", { name: "Изображения" }).click();
  await page.locator('input[type="file"]').first().setInputFiles({
    name: "retry.png",
    mimeType: "image/png",
    buffer: Buffer.from("image"),
  });

  await page.getByRole("button", { name: "Сохранить" }).click();
  await expect(
    page.getByText(/Товар сохранён, но изображения не загружены: Хранилище изображений недоступно/),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/catalog\/prod-image-retry$/);
  await expect(page.getByRole("heading", { name: "Редактировать товар" })).toBeVisible();
  expect(productCreateRequests).toBe(1);

  await page.getByRole("button", { name: "Сохранить" }).click();
  await expect(
    page.getByText(/Товар сохранён, но изображения не загружены: Хранилище изображений недоступно/),
  ).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Каталог товаров" })).toBeVisible();
  expect(productCreateRequests).toBe(1);
  expect(imageUploadRequests).toBe(2);

  await page.goto(`${brandBase}/catalog/prod-image-retry`);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Редактировать товар" })).toBeVisible();
  await page.getByRole("button", { name: "Сохранить" }).click();
  await expect(page.getByRole("heading", { name: "Каталог товаров" })).toBeVisible();
  expect(productCreateRequests).toBe(1);
});

test("brand portal retries variant mutations after a later variant failure", async ({ page }) => {
  const variantRetryProduct = {
    ...brandCatalogProduct,
    id: "prod-variant-retry",
    name: "Товар с повторной записью вариантов",
    slug: "variant-retry-product",
    product_status: "archived",
    is_active: false,
    variants: [
      {
        ...auroraDetail.variants[0],
        id: "variant-to-delete",
        product_id: "prod-variant-retry",
        size: "S",
        sku: "EXISTING-S",
      },
    ],
    images: [],
  };
  let deletedVariantRequests = 0;
  let createdVariantRequests = 0;
  const productPayloads: Array<{ is_active?: boolean }> = [];

  await page.route(`${apiBase}/brand-portal/products/prod-variant-retry**`, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");

    if (request.method() === "GET" && path === "/brand-portal/products/prod-variant-retry") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: variantRetryProduct }),
      });
      return;
    }

    if (request.method() === "PATCH" && path === "/brand-portal/products/prod-variant-retry") {
      productPayloads.push(request.postDataJSON() as { is_active?: boolean });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: variantRetryProduct }),
      });
      return;
    }

    if (request.method() === "DELETE" && path === "/brand-portal/products/prod-variant-retry/variants/variant-to-delete") {
      deletedVariantRequests += 1;
      await route.fulfill({ status: 204 });
      return;
    }

    if (request.method() === "POST" && path === "/brand-portal/products/prod-variant-retry/variants") {
      createdVariantRequests += 1;
      if (createdVariantRequests === 2) {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ error: { message: "Не удалось создать второй вариант" } }),
        });
        return;
      }

      const variant = {
        ...auroraDetail.variants[0],
        id: createdVariantRequests === 1 ? "variant-created-first" : "variant-created-second",
        product_id: "prod-variant-retry",
        size: createdVariantRequests === 1 ? "M" : "L",
        sku: createdVariantRequests === 1 ? "RETRY-M" : "RETRY-L",
      };
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({ data: variant }),
      });
      return;
    }

    await route.fallback();
  });

  await loginToBrandPortal(page, `${brandBase}/catalog/prod-variant-retry`);
  await expect(page.getByRole("heading", { name: "Редактировать товар" })).toBeVisible();
  await selectByVisualLabel(page, "Status", "Активен");
  await page.getByRole("tab", { name: "Варианты" }).click();
  await page.getByRole("button", { name: "Удалить вариант" }).click();
  await page.getByRole("button", { name: "Add row" }).click();
  await page.getByRole("button", { name: "Add row" }).click();
  await variantInput(page, 2, 0).fill("M");
  await variantInput(page, 4, 0).fill("RETRY-M");
  await variantInput(page, 5, 0).fill("12900");
  await variantInput(page, 2, 1).fill("L");
  await variantInput(page, 4, 1).fill("RETRY-L");
  await variantInput(page, 5, 1).fill("12900");

  await page.getByRole("button", { name: "Сохранить" }).click();
  await expect(page.getByText("Не удалось создать второй вариант", { exact: true })).toBeVisible();
  expect(productPayloads[0]?.is_active).toBe(true);
  expect(deletedVariantRequests).toBe(1);
  expect(createdVariantRequests).toBe(2);

  await page.getByRole("button", { name: "Сохранить" }).click();
  await expect(page.getByRole("heading", { name: "Каталог товаров" })).toBeVisible();
  expect(deletedVariantRequests).toBe(1);
  expect(createdVariantRequests).toBe(3);
});
