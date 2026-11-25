import { expect, type APIRequestContext, type Locator, type Page, test } from "@playwright/test";

const apiBase = "http://127.0.0.1:18000/api/v1";
const brandBase = "http://127.0.0.1:3201";

type ProductStatus = "active" | "hidden" | "archived";

interface CategoryItem {
  id: string;
  name: string;
  children: CategoryItem[];
}

interface ProductListItem {
  id: string;
  name: string;
  slug: string;
  available_sizes: string[];
}

interface ProductDetail {
  id: string;
  name: string;
  slug: string;
  product_status: ProductStatus;
  variants: Array<{
    id: string;
    size: string;
    sku: string;
    price_rub: number | string | null;
    compare_at_price_rub: number | string | null;
    stock_quantity: number;
    is_active: boolean;
  }>;
}

interface ApiResponse<T> {
  data: T;
}

interface CategoryOption {
  label: string;
}

function flattenCategories(categories: CategoryItem[], prefix = ""): CategoryOption[] {
  return categories.flatMap((category) => {
    const label = `${prefix}${category.name}`;
    const children = flattenCategories(category.children, `${label} / `);

    return category.children.length === 0 ? [{ label }] : children;
  });
}

async function pickLeafCategory(request: APIRequestContext): Promise<CategoryOption> {
  const response = await request.get(`${apiBase}/categories`);
  expect(response.ok()).toBe(true);
  const payload = (await response.json()) as ApiResponse<CategoryItem[]>;
  const categories = flattenCategories(payload.data);

  expect(categories.length).toBeGreaterThan(0);
  return categories[0];
}

function fieldByLabel(page: Page, label: string): Locator {
  return page
    .locator("label", { hasText: new RegExp(`^${label}$`) })
    .locator("xpath=..")
    .locator("input, textarea")
    .first();
}

function variantInput(page: Page, columnIndex: number): Locator {
  return page
    .getByRole("row")
    .filter({ has: page.locator("input") })
    .first()
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

async function loginToBrandPortal(page: Page): Promise<void> {
  await page.goto(`${brandBase}/login`);
  await page.getByLabel("Email").fill("brand@example.invalid");
  await page.getByLabel("Пароль").fill(process.env.DEMO_BRAND_PASSWORD ?? "");
  await page.getByRole("button", { name: "Войти" }).click();
  await expect(page.getByRole("heading", { name: "Статистика" })).toBeVisible();
}

async function getPublicProduct(
  request: APIRequestContext,
  slug: string,
): Promise<ProductDetail | null> {
  const response = await request.get(`${apiBase}/products/${slug}`);
  if (response.status() === 404) return null;

  expect(response.ok()).toBe(true);
  const payload = (await response.json()) as ApiResponse<ProductDetail>;
  return payload.data;
}

async function expectPublicListContains(
  request: APIRequestContext,
  slug: string,
): Promise<ProductListItem> {
  let product: ProductListItem | undefined;

  await expect
    .poll(async () => {
      const response = await request.get(`${apiBase}/products?per_page=100`);
      expect(response.ok()).toBe(true);
      const payload = (await response.json()) as ApiResponse<ProductListItem[]>;
      product = payload.data.find((item) => item.slug === slug);
      return Boolean(product);
    })
    .toBe(true);

  return product as ProductListItem;
}

async function expectPublicProductDetail(
  request: APIRequestContext,
  slug: string,
): Promise<ProductDetail> {
  let product: ProductDetail | null = null;

  await expect
    .poll(async () => {
      product = await getPublicProduct(request, slug);
      return product !== null;
    })
    .toBe(true);

  if (!product) throw new Error(`Public product ${slug} was not returned.`);
  return product;
}

async function expectPublicProductHidden(request: APIRequestContext, slug: string): Promise<void> {
  await expect
    .poll(async () => {
      const listResponse = await request.get(`${apiBase}/products?per_page=100`);
      expect(listResponse.ok()).toBe(true);
      const listPayload = (await listResponse.json()) as ApiResponse<ProductListItem[]>;
      const detailResponse = await request.get(`${apiBase}/products/${slug}`);

      return {
        inList: listPayload.data.some((item) => item.slug === slug),
        detailStatus: detailResponse.status(),
      };
    })
    .toEqual({ inList: false, detailStatus: 404 });
}

test.describe("QA-003 Brand Portal catalog publication", () => {
  test.skip(
    process.env.STI_008_FULL_STACK !== "1",
    "Run after the real backend, seed data, and frontend preview servers are available.",
  );

  test("publishes Brand Portal CRUD changes to Customer Web public catalog", async ({
    page,
    request,
  }) => {
    const category = await pickLeafCategory(request);
    const suffix = Date.now().toString(36);
    const productName = `Fictional Studio Cotton Tee ${suffix}`;
    const slug = `qa-003-publication-smoke-${suffix}`;
    const sku = `QA003-${suffix}`.toUpperCase();
    const vendorCode = `QA-003-VENDOR-${suffix}`.toUpperCase();
    const size = "QA-003";

    await loginToBrandPortal(page);
    await page.goto(`${brandBase}/catalog`);
    await expect(page.getByRole("heading", { name: "Каталог товаров" })).toBeVisible();
    await expect(page.locator('a[href="/catalog/upload"]')).toHaveCount(0);
    await page.goto(`${brandBase}/catalog/upload`);
    await expect(page.getByText("Страница не найдена")).toBeVisible();

    await page.goto(`${brandBase}/catalog/new`);
    await expect(page.getByRole("heading", { name: "Новый товар" })).toBeVisible();
    await fieldByLabel(page, "Name").fill(productName);
    await fieldByLabel(page, "Slug").fill(slug);
    await selectByVisualLabel(page, "Category", category.label);
    await fieldByLabel(page, "Description").fill("QA-003 CRUD publication smoke product.");
    await fieldByLabel(page, "Fabric").fill("100% test cotton");
    await fieldByLabel(page, "Price").fill("3590");
    await fieldByLabel(page, "Season").fill("QA26");
    await page.getByRole("tab", { name: "Варианты" }).click();
    await variantInput(page, 1).fill(vendorCode);
    await variantInput(page, 2).fill(size);
    await variantInput(page, 3).fill("Black");
    await variantInput(page, 4).fill(sku);
    await variantInput(page, 5).fill("3590");
    await variantInput(page, 7).fill("3");
    await page.getByRole("button", { name: "Сохранить" }).click();

    await expect(page.getByRole("heading", { name: "Каталог товаров" })).toBeVisible();
    await expect(page.getByRole("row").filter({ hasText: productName })).toBeVisible();

    const listedProduct = await expectPublicListContains(request, slug);
    expect(listedProduct.name).toBe(productName);
    expect(listedProduct.available_sizes).toContain(size);
    const detailProduct = await expectPublicProductDetail(request, slug);
    expect(detailProduct.name).toBe(productName);
    expect(detailProduct.variants.some((variant) => variant.size === size && variant.stock_quantity > 0)).toBe(
      true,
    );

    await page.goto("/shop");
    await expect(page.getByText(productName)).toBeVisible();
    await page.goto(`/product/${slug}`);
    await expect(page.getByRole("heading", { name: productName })).toBeVisible();
    await expect(page.getByRole("button", { name: size })).toBeVisible();

    await page.goto(`${brandBase}/catalog`);
    await page.getByRole("row").filter({ hasText: productName }).getByRole("link", { name: productName }).click();
    await expect(page.getByRole("heading", { name: "Редактировать товар" })).toBeVisible();
    await page.getByRole("tab", { name: "Варианты" }).click();
    await variantInput(page, 7).fill("0");
    await page.getByRole("button", { name: "Сохранить" }).click();

    await expect(page.getByRole("heading", { name: "Каталог товаров" })).toBeVisible();
    await expect
      .poll(async () =>
        (await getPublicProduct(request, slug))?.variants.some(
          (variant) => variant.size === size && variant.is_active && variant.stock_quantity > 0,
        ) ?? true,
      )
      .toBe(false);
    await page.goto(`/product/${slug}`);
    await expect(page.getByRole("heading", { name: productName })).toBeVisible();
    await expect(page.getByRole("button", { name: size })).toHaveCount(0);

    await page.goto(`${brandBase}/catalog`);
    const catalogRow = page.getByRole("row").filter({ hasText: productName });
    await expect(catalogRow).toBeVisible();
    await catalogRow.getByRole("button", { name: "Архивировать товар" }).click();
    await expect(catalogRow.getByText("Архив")).toBeVisible();

    await expectPublicProductHidden(request, slug);
    await page.goto("/shop");
    await expect(page.getByText(productName)).toHaveCount(0);
    await page.goto(`/product/${slug}`);
    await expect(page.getByRole("heading", { name: "Товар не найден" })).toBeVisible();
  });
});
