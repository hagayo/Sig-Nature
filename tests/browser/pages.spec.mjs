import { test, expect } from "@playwright/test";

const sections = [
  {url: "/", mode: "generate", title: "יצירת חתימה"},
  {url: "/analyze-photo.html", mode: "photo", title: "ניתוח תמונה"},
  {url: "/analyze-signature.html", mode: "signature", title: "ניתוח חתימה"}
];

for (const section of sections) {
  test(`${section.mode}: same accessible navigation and localized page title`, async ({page}) => {
    await page.goto(section.url);
    await expect(page.locator("body")).toHaveAttribute("data-page", section.mode);
    await expect(page.locator("nav [aria-current='page']")).toHaveAttribute("href", section.url);
    await expect(page).toHaveTitle(new RegExp(section.title));
    await expect(page.locator("nav")).toHaveAttribute("aria-label", "ניווט ראשי");
    await page.locator("#language-toggle").click();
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
    await expect(page.locator("nav")).toHaveAttribute("aria-label", "Main navigation");
    await expect(page).toHaveTitle(/Sig-Nature/);
  });
}

test("language choice persists between the three separate pages", async ({page}) => {
  await page.goto("/");
  await page.locator("#language-toggle").click();
  await page.locator(".site-nav a[href='/analyze-photo.html']").click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("h1")).toHaveText("Analyze my photo");
  await page.locator(".site-nav a[href='/analyze-signature.html']").click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("h1")).toHaveText("Analyze my signature");
});

test("360px viewport has no horizontal body overflow on any page", async ({page}) => {
  await page.setViewportSize({width: 360, height: 740});
  for (const section of sections) {
    await page.goto(section.url);
    const widths = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      client: document.documentElement.clientWidth
    }));
    expect(widths.scroll, `overflow on ${section.url}`).toBeLessThanOrEqual(widths.client + 1);
    await expect(page.locator(".site-nav a[aria-current='page']")).toBeVisible();
  }
});

test("photo analysis renders evidence and localized 422 errors", async ({page}) => {
  await page.goto("/analyze-photo.html");
  const image = {name: "face.png", mimeType: "image/png", buffer: Buffer.from("mock-image")};
  await page.locator("#analysis-image").setInputFiles(image);
  await page.locator("#api-key").fill("temporary-test-key");
  await page.route("**/api/analyze-photo", async route => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        summary: "חיוך ברור",
        cues: ["הפה מחייך", "מבט ישיר"],
        vibe: "מראה שובב",
        traits: {joy: .88, tension: .24},
        writing_style: {pressure: .5, width: 1.2}
      })
    });
  });
  await page.locator("#analyze").click();
  await expect(page.locator("#results")).toBeVisible();
  await expect(page.locator("#analysis-description")).toContainText("מבט ישיר");
  await expect(page.locator("#analysis-details dt")).toHaveCount(2);
  await expect(page.locator("#api-key")).toHaveValue("");
  await page.unroute("**/api/analyze-photo");
  await page.route("**/api/analyze-photo", route => route.fulfill({
    status: 422, contentType: "application/json",
    body: JSON.stringify({detail: "No clearly visible face"})
  }));
  await page.locator("#api-key").fill("temporary-test-key");
  await page.locator("#analyze").click();
  await expect(page.locator("#status")).toHaveAttribute("role", "alert");
  await expect(page.locator("#status")).toContainText("לא נמצאו פנים ברורות");
  await expect(page.locator("#results")).toBeHidden();
});

test("new signature input clears earlier media instead of playing in background", async ({page}) => {
  await page.goto("/");
  await page.route("**/api/generate", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({
      signature_png_url: "/api/assets/" + "a".repeat(32) + "/signature.png",
      animation_mp4_url: "/api/assets/" + "a".repeat(32) + "/signature.mp4"
    })
  }));
  await page.locator("#full-name").fill("חגי און");
  await page.locator("#portrait").setInputFiles({
    name: "face.png", mimeType: "image/png", buffer: Buffer.from("mock-image")
  });
  await page.locator("#api-key").fill("temporary-test-key");
  await page.locator("#generate").click();
  await expect(page.locator("#results")).toBeVisible();
  await expect(page.locator("#animation-preview")).toHaveAttribute("src", /signature\.mp4/);
  await page.locator("#full-name").fill("שרה לוי");
  await expect(page.locator("#results")).toBeHidden();
  await expect(page.locator("#animation-preview")).not.toHaveAttribute("src", /signature\.mp4/);
});
