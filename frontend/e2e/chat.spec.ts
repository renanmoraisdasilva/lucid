import { expect, test, type APIRequestContext } from "@playwright/test";

async function clearConversations(request: APIRequestContext): Promise<void> {
  const response = await request.get("/api/conversations?limit=20");
  if (!response.ok()) {
    return;
  }
  const body = (await response.json()) as { items: Array<{ id: string }> };
  for (const item of body.items) {
    await request.delete(`/api/conversations/${item.id}`);
  }
}

test.beforeEach(async ({ request }) => {
  await clearConversations(request);
});

test("sends a message and renders the streamed reply", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "How can Lucid help today?" })).toBeVisible();

  await page.getByLabel("Message Lucid").fill("Hello from the browser");
  await page.getByLabel("Message Lucid").press("Enter");

  await expect(page.getByText("Hello from the browser")).toBeVisible();
  await expect(page.getByText("Fake response.")).toBeVisible();
  await expect(page.getByLabel("Message Lucid")).toBeEnabled();
  await expect(
    page.getByRole("button", { name: "Hello from the browser", exact: true }),
  ).toBeVisible();
});

test("keeps the conversation after a reload", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Message Lucid").fill("Persist me");
  await page.getByLabel("Message Lucid").press("Enter");
  await expect(page.getByText("Fake response.")).toBeVisible();

  await page.reload();

  await page.getByRole("button", { name: "Persist me", exact: true }).click();
  await expect(page.getByText("Fake response.")).toBeVisible();
});

test("deletes a conversation after confirmation", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Message Lucid").fill("Delete me");
  await page.getByLabel("Message Lucid").press("Enter");
  await expect(page.getByText("Fake response.")).toBeVisible();

  await page.getByRole("button", { name: "Delete conversation Delete me" }).click();
  const dialog = page.getByRole("dialog", { name: "Delete conversation?" });
  await expect(dialog).toBeVisible();

  await dialog.getByRole("button", { name: "Delete" }).click();

  await expect(dialog).toBeHidden();
  await expect(page.getByRole("button", { name: "Delete me", exact: true })).toBeHidden();
  await expect(page.getByRole("heading", { name: "How can Lucid help today?" })).toBeVisible();
});
