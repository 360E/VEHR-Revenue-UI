import { expect, test, type Page } from "@playwright/test";

const baseApi = "http://127.0.0.1:8000";

const preferencesPayload = {
  last_active_module: "care_delivery",
  sidebar_collapsed: false,
  copilot_enabled: false,
  allowed_modules: [
    "care_delivery",
    "call_center",
    "workforce",
    "revenue_cycle",
    "governance",
    "administration",
  ],
  granted_permissions: [
    "clients:read",
    "patients:read",
    "forms:read",
    "documents:read",
    "tasks:read_self",
    "calls:read",
    "leads:read",
    "staff:read",
    "workforce:read",
    "billing:read",
    "audit:read",
    "admin:org_settings",
    "users:manage",
  ],
};

async function mockAppShell(page: Page) {
  await page.route(`${baseApi}/api/v1/auth/me`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "user-1",
        email: "visual-test@example.com",
        full_name: "Visual Test User",
        role: "admin",
        organization_id: "org-1",
      }),
    });
  });

  await page.route(`${baseApi}/api/v1/me/preferences`, async (route) => {
    const method = route.request().method();
    if (method === "PATCH") {
      const body = route.request().postDataJSON() as { last_active_module?: string | null };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...preferencesPayload,
          last_active_module: body?.last_active_module ?? preferencesPayload.last_active_module,
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(preferencesPayload),
    });
  });

  await page.route(`${baseApi}/api/v1/patients`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { id: "patient-001", first_name: "Alex", last_name: "Miller" },
        { id: "patient-002", first_name: "Jordan", last_name: "Rivera" },
        { id: "patient-003", first_name: "Taylor", last_name: "Chen" },
      ]),
    });
  });
}

test("launcher tiles visual and full-tile navigation", async ({ page }) => {
  await mockAppShell(page);

  await page.goto("/directory");
  await expect(page.getByTestId("directory-launcher")).toBeVisible();
  await expect(page.getByTestId("directory-module-grid").getByText(/^Open$/)).toHaveCount(0);
  await expect(page.getByTestId("directory-launcher")).toHaveScreenshot("launcher-tiles.png");

  await page.getByTestId("directory-module-care_delivery").click();
  await expect(page).toHaveURL(/\/clients$/);
  await expect(page.getByRole("main").getByRole("heading", { name: "Clients" })).toBeVisible();
});

test("sidebar visual uses strong theme without letter icon blocks", async ({ page }) => {
  await mockAppShell(page);

  await page.goto("/clients");
  await expect(page.locator("nav[aria-label='Section navigation']")).toBeVisible();
  await expect(
    page.locator("nav[aria-label='Section navigation'] span[class*='h-7'][class*='w-7']"),
  ).toHaveCount(0);
  await expect(page).toHaveScreenshot("sidebar-clients-theme.png", { fullPage: true });
});
