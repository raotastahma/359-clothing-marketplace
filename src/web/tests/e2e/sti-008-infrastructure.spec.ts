import { expect, test } from "@playwright/test";

const apiBase = "http://127.0.0.1:18000/api/v1";
const healthUrl = "http://127.0.0.1:18000/health";
const brandBase = "http://127.0.0.1:3201";

test.describe("STI-008 full-stack infrastructure", () => {
  test.skip(
    process.env.STI_008_FULL_STACK !== "1",
    "Run through npm run e2e:full-stack after the backend smoke harness starts services.",
  );

  test("backend health is available before browser CORS checks", async ({ request }) => {
    const response = await request.get(healthUrl);

    expect(response.ok()).toBe(true);
  });

  test("Customer Web origin can fetch products from the real backend", async ({ page }) => {
    await page.goto("/");

    const result = await page.evaluate(async (productsUrl) => {
      const response = await fetch(productsUrl);
      const body: unknown = await response.json();

      return {
        ok: response.ok,
        status: response.status,
        readableJson: body !== null && typeof body === "object",
      };
    }, `${apiBase}/products`);

    expect(result).toEqual({ ok: true, status: 200, readableJson: true });
  });

  test("Brand Portal origin can fetch products from the real backend", async ({ page }) => {
    await page.goto(brandBase);

    const result = await page.evaluate(async (productsUrl) => {
      const response = await fetch(productsUrl);
      const body: unknown = await response.json();

      return {
        ok: response.ok,
        status: response.status,
        readableJson: body !== null && typeof body === "object",
      };
    }, `${apiBase}/products`);

    expect(result).toEqual({ ok: true, status: 200, readableJson: true });
  });
});
