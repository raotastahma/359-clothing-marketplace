// Checkout phone validation spec: seeds a cart and verifies delivery-step phone rules without touching login OTP.
import { expect, type Page, test } from "@playwright/test";

const checkoutCart = [
  {
    product: {
      id: "checkout-phone-test-product",
      apiId: "checkout-phone-test-product-api",
      brand: "359 Test Brand",
      name: "Checkout Phone Test Item",
      category: "Clothing",
      subcategory: "Hoodies",
      price: 3590,
      sizes: ["M"],
      images: [],
      description: "Focused checkout validation test item.",
      inStock: true,
      gender: "Unisex",
      variantIdsBySize: {
        M: "checkout-phone-test-variant",
      },
    },
    size: "M",
    quantity: 1,
  },
];

async function openCheckoutWithCart(page: Page): Promise<void> {
  await page.addInitScript((cartItems) => {
    window.localStorage.setItem("359-cart", JSON.stringify(cartItems));
  }, checkoutCart);

  await page.goto("/checkout");
  await expect(page.getByRole("heading", { name: "Оформление заказа" })).toBeVisible();
  await expect(page.getByText("Checkout Phone Test Item")).toBeVisible();
}

async function submitDeliveryPhone(page: Page, phone: string): Promise<void> {
  await page.getByLabel("ФИО").fill("QA Покупатель");
  await page.getByLabel("Телефон").fill(phone);
  await page.getByRole("button", { name: "Перейти к оплате" }).click();
}

async function expectDeliveryStep(page: Page): Promise<void> {
  await expect(page.getByRole("heading", { name: "Контакты" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Оплата" })).toHaveCount(0);
}

test.describe("checkout delivery phone validation", () => {
  test("rejects empty and invalid checkout phone values on the delivery step", async ({
    page,
  }) => {
    await openCheckoutWithCart(page);

    await submitDeliveryPhone(page, "");
    await expect(page.getByText("Укажите телефон")).toBeVisible();
    await expectDeliveryStep(page);

    await submitDeliveryPhone(page, "123456789");
    await expect(
      page.getByText("Укажите 10 цифр или 11 цифр с 7 или 8 в начале"),
    ).toBeVisible();
    await expectDeliveryStep(page);

    await submitDeliveryPhone(page, "9 999 123-45-67");
    await expect(
      page.getByText("Укажите 10 цифр или 11 цифр с 7 или 8 в начале"),
    ).toBeVisible();
    await expectDeliveryStep(page);
  });

  test("accepts valid 10-digit and 11-digit checkout phone values", async ({ page }) => {
    await openCheckoutWithCart(page);

    for (const phone of ["9991234567", "+7 999 123-45-67", "8 (999) 123-45-67"]) {
      await submitDeliveryPhone(page, phone);
      await expect(page.getByRole("heading", { name: "Оплата" })).toBeVisible();
      await page.getByRole("button", { name: "Назад" }).click();
      await expectDeliveryStep(page);
    }
  });
});
