import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../../index.html", import.meta.url), "utf8");
const lines = html.split(/\r?\n/);
const hebrew = /[\u05D0-\u05EA]/u;
const latin = /[A-Za-z]/u;

function sourceLine(selector) {
  const id = selector.match(/^#([\w-]+)$/)?.[1];
  if (!id) return "unknown";
  const index = lines.findIndex(line => new RegExp(`\\bid=["']${id}["']`).test(line));
  return index < 0 ? "unknown" : String(index + 1);
}

test("language toggle renders only permitted scripts in visible UI", async ({ page }) => {
  await page.goto("/");
  const failures = [];

  for (const lang of ["he", "en", "he"]) {
    if ((await page.locator("html").getAttribute("lang")) !== lang) {
      await page.locator("#language-toggle").click();
    }
    await expect(page.locator("html")).toHaveAttribute("lang", lang);
    await expect(page.locator("html")).toHaveAttribute("dir", lang === "he" ? "rtl" : "ltr");

    const elements = await page.locator("h1, [data-i18n], #language-toggle, #full-name, #signature-preview, #status").evaluateAll(nodes =>
      nodes.filter(node => node.getClientRects().length > 0)
        .map(node => ({
          selector: node.id ? `#${node.id}` : node.hasAttribute("data-i18n") ? `[data-i18n="${node.getAttribute("data-i18n")}"]` : node.tagName.toLowerCase(),
          tag: node.tagName.toLowerCase(),
          id: node.id,
          text: node.textContent?.trim() || "",
          placeholder: node.getAttribute("placeholder") || "",
          alt: node.getAttribute("alt") || ""
        }))
    );

    for (const el of elements) {
      for (const [field, value] of Object.entries({ text: el.text, placeholder: el.placeholder, alt: el.alt })) {
        if (!value) continue;
        if (el.id === "language-toggle" && field === "text") continue;
        if (el.tag === "h1" && value === "Sig-Nature") continue;
        // API, PNG, Python and other explicitly untranslated technical tokens.
        const normalized = lang === "he" ? value.replace(/\b(?:API|PNG|Python|WebM)\b/g, "") : value;
        const invalid = [...normalized].filter(ch => (lang === "he" ? latin : hebrew).test(ch));
        if (invalid.length) {
          const selector = el.id ? `#${el.id}` : el.selector;
          failures.push(`index.html:${sourceLine(selector)} | language=${lang} | element=${selector} | field=${field} | actual=${JSON.stringify(value)} | invalid=${JSON.stringify(invalid)} | expected=${lang === "he" ? "Hebrew script only (technical terms excluded)" : "Latin script only"}`);
        }
      }
    }
  }

  expect(failures, failures.join("\n")).toEqual([]);
});

test("language toggle preserves user-provided Hebrew text", async ({ page }) => {
  await page.goto("/");
  await page.locator("#full-name").fill("שם משתמש");
  await page.locator("#language-toggle").click();
  await expect(page.locator("#full-name")).toHaveValue("שם משתמש");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
});
