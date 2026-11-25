import { expect, test } from "@playwright/test";

test("home page internal links resolve in the local portfolio demo", async ({ page, request }) => {
  await page.goto("/");
  const links = await page.locator("a[href]").evaluateAll((anchors) =>
    Array.from(new Set(anchors.map((anchor) => anchor.getAttribute("href") ?? "")))
      .filter((href) => href.startsWith("/") && !href.startsWith("//")),
  );
  expect(links.length).toBeGreaterThan(0);
  for (const href of links) {
    const response = await request.get(href);
    expect(response.status(), href).toBeLessThan(400);
  }
});
