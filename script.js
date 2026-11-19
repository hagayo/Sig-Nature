// Backend contract: POST multipart/form-data to /api/generate.
// Expected JSON: { signature_png_url, animation_mp4_url }.
const API_ENDPOINT = "/api/generate";
const translations = {
  he: {fullName:"שם מלא",portrait:"תמונת פנים",apiKey:"מפתח API",generate:"הפעל",downloadPng:"הורדת חתימה PNG",downloadVideo:"הורדת סרטון",working:"יוצר חתימה...",ready:"הקבצים מוכנים",serverError:"שגיאה מהשרת",missing:"השרת לא החזיר את שני הקבצים",offline:"לא ניתן להתחבר לשרת.",alt:"חתימה על רקע שקוף",placeholder:"שם מלא",toggle:"English",toggleLabel:"Switch to English"},
  en: {fullName:"Full name",portrait:"Face photo",apiKey:"API key",generate:"Generate",downloadPng:"Download signature PNG",downloadVideo:"Download video",working:"Generating signature...",ready:"Files are ready",serverError:"Server error",missing:"The server did not return both files",offline:"Cannot connect to the server.",alt:"Signature on transparent background",placeholder:"Your full name",toggle:"עברית",toggleLabel:"מעבר לעברית"}
};
let language = "he";
let statusKey = null;
let statusDetails = "";
const form = document.querySelector("#signature-form");
const status = document.querySelector("#status");
const results = document.querySelector("#results");
const toggle = document.querySelector("#language-toggle");
function renderLanguage() {
  const t = translations[language];
  document.documentElement.lang = language;
  document.documentElement.dir = language === "he" ? "rtl" : "ltr";
  document.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t[el.dataset.i18n]; });
  document.querySelector("#full-name").placeholder = t.placeholder;
  document.querySelector("#signature-preview").alt = t.alt;
  toggle.textContent = t.toggle;
  toggle.setAttribute("aria-label", t.toggleLabel);
  if (statusKey) status.textContent = t[statusKey] + statusDetails;
}
toggle.addEventListener("click", () => { language = language === "he" ? "en" : "he"; renderLanguage(); });
function setStatus(key, details = "") { statusKey = key; statusDetails = details; status.textContent = translations[language][key] + details; }
form.addEventListener("submit", async event => {
  event.preventDefault();
  results.hidden = true;
  const button = document.querySelector("#generate");
  const data = new FormData();
  data.set("full_name", document.querySelector("#full-name").value.trim());
  data.set("portrait", document.querySelector("#portrait").files[0]);
  data.set("api_key", document.querySelector("#api-key").value);
  button.disabled = true;
  setStatus("working");
  try {
    const response = await fetch(API_ENDPOINT, {method:"POST",body:data});
    if (!response.ok) { const issue = await response.json().catch(() => ({})); setStatus("serverError", " (" + response.status + "): " + (issue.detail || "")); return; }
    const payload = await response.json();
    if (!payload.signature_png_url || !payload.animation_mp4_url) { setStatus("missing"); return; }
    document.querySelector("#signature-preview").src = payload.signature_png_url;
    document.querySelector("#download-png").href = payload.signature_png_url;
    document.querySelector("#animation-preview").src = payload.animation_mp4_url;
    document.querySelector("#download-video").href = payload.animation_mp4_url;
    document.querySelector("#api-key").value = "";
    results.hidden = false;
    setStatus("ready");
  } catch (error) {
    setStatus("offline");
  } finally {
    button.disabled = false;
  }
});
renderLanguage();