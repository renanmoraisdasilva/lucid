import { expect, test, type APIRequestContext } from "@playwright/test";

async function clearConversations(request: APIRequestContext): Promise<void> {
  const response = await request.get("/api/conversations?limit=20");
  if (!response.ok()) {
    return;
  }
  const body = (await response.json()) as { items: Array<{ id: string; title: string }> };
  for (const item of body.items) {
    // Only remove this suite's own conversations; never touch the developer's data.
    if (item.title.startsWith("e2e ")) {
      await request.delete(`/api/conversations/${item.id}`);
    }
  }
}

test.beforeEach(async ({ request }) => {
  await clearConversations(request);
});

test("sends a message and renders the streamed reply", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "How can Lucid help today?" })).toBeVisible();

  await page.getByLabel("Message Lucid").fill("e2e hello from the browser");
  await page.getByLabel("Message Lucid").press("Enter");

  await expect(page.getByRole("main").getByText("e2e hello from the browser")).toBeVisible();
  await expect(page.getByText("Fake response.")).toBeVisible();
  await expect(page.getByLabel("Message Lucid")).toBeEnabled();
  await expect(
    page.getByRole("button", { name: "e2e hello from the browser", exact: true }),
  ).toBeVisible();
});

test("keeps the conversation after a reload", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Message Lucid").fill("e2e persist me");
  await page.getByLabel("Message Lucid").press("Enter");
  await expect(page.getByText("Fake response.")).toBeVisible();

  await page.reload();

  await page.getByRole("button", { name: "e2e persist me", exact: true }).click();
  await expect(page.getByText("Fake response.")).toBeVisible();
});

test("deletes a conversation after confirmation", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Message Lucid").fill("e2e delete me");
  await page.getByLabel("Message Lucid").press("Enter");
  await expect(page.getByText("Fake response.")).toBeVisible();

  await page.getByRole("button", { name: "Delete conversation e2e delete me" }).click();
  const dialog = page.getByRole("dialog", { name: "Delete conversation?" });
  await expect(dialog).toBeVisible();

  await dialog.getByRole("button", { name: "Delete" }).click();

  await expect(dialog).toBeHidden();
  await expect(page.getByRole("button", { name: "e2e delete me", exact: true })).toBeHidden();
  await expect(page.getByRole("heading", { name: "How can Lucid help today?" })).toBeVisible();
});
