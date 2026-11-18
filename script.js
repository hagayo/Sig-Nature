// The backend contract is intentionally isolated here for later Python integration.
// POST multipart/form-data to /api/generate with full_name, portrait and api_key.
// Expected JSON: { signature_png_url: string, animation_webm_url: string }.
// Do not put production API keys in client-side code or logs.
const API_ENDPOINT = "/api/generate";
const form = document.querySelector("#signature-form");
const status = document.querySelector("#status");
const results = document.querySelector("#results");
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  results.hidden = true;
  const button = document.querySelector("#generate");
  const data = new FormData();
  data.set("full_name", document.querySelector("#full-name").value.trim());
  data.set("portrait", document.querySelector("#portrait").files[0]);
  data.set("api_key", document.querySelector("#api-key").value);
  button.disabled = true;
  status.textContent = "יוצר חתימה...";
  try {
    const response = await fetch(API_ENDPOINT, { method: "POST", body: data });
    if (!response.ok) throw new Error("שגיאה מהשרת (" + response.status + ")");
    const payload = await response.json();
    if (!payload.signature_png_url || !payload.animation_webm_url) throw new Error("השרת לא החזיר את שני הקבצים");
    document.querySelector("#signature-preview").src = payload.signature_png_url;
    document.querySelector("#download-png").href = payload.signature_png_url;
    document.querySelector("#animation-preview").src = payload.animation_webm_url;
    document.querySelector("#download-video").href = payload.animation_webm_url;
    results.hidden = false;
    status.textContent = "הקבצים מוכנים";
  } catch (error) {
    status.textContent = error.message === "Failed to fetch" ? "לא ניתן להתחבר לשרת. ממשק זה ממתין לחיבור Python." : error.message;
  } finally {
    button.disabled = false;
  }
});