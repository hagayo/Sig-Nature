import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("../script.js", import.meta.url), "utf8");

function setup() {
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) {
      elements.set(id, {
        value: "", files: [{ name: "portrait.png" }], dataset: {}, hidden: true,
        disabled: false, textContent: "", placeholder: "", src: "", href: "",
        attrs: {}, handlers: {},
        setAttribute(key, value) { this.attrs[key] = value; },
        addEventListener(type, fn) { this.handlers[type] = fn; }
      });
    }
    return elements.get(id);
  }
  const root = { lang: "", dir: "" };
  const context = {
    document: {
      documentElement: root,
      querySelector(selector) { return element(selector); },
      querySelectorAll() { return []; }
    },
    FormData: class {
      values = new Map();
      set(key, value) { this.values.set(key, value); }
    },
    fetch: async () => ({ ok: true, json: async () => ({
      signature_png_url: "/signature.png", animation_webm_url: "/signature.webm"
    }) })
  };
  vm.runInNewContext(source, context);
  return { element, root, context };
}

test("language toggle changes direction and preserves user input", () => {
  const { element, root } = setup();
  const name = element("#full-name");
  name.value = "Test User";
  assert.equal(root.dir, "rtl");
  element("#language-toggle").handlers.click();
  assert.equal(root.lang, "en");
  assert.equal(root.dir, "ltr");
  assert.equal(name.value, "Test User");
  element("#language-toggle").handlers.click();
  assert.equal(root.dir, "rtl");
});

test("submit sends user values and renders both results", async () => {
  const { element, context } = setup();
  let sent;
  context.fetch = async (url, options) => {
    sent = { url, options };
    return { ok: true, json: async () => ({
      signature_png_url: "/signature.png", animation_webm_url: "/signature.webm"
    }) };
  };
  element("#full-name").value = "Test User";
  element("#api-key").value = "temporary-test-key";
  await element("#signature-form").handlers.submit({ preventDefault() {} });
  assert.equal(sent.url, "/api/generate");
  assert.equal(sent.options.body.values.get("full_name"), "Test User");
  assert.equal(sent.options.body.values.get("api_key"), "temporary-test-key");
  assert.equal(element("#results").hidden, false);
  assert.equal(element("#download-png").href, "/signature.png");
  assert.equal(element("#download-video").href, "/signature.webm");
});
