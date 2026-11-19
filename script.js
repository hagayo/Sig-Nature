// One browser controller for three HTML pages, shared RTL/LTR and API handling.
const API_ENDPOINTS = {
  generate: "/api/generate",
  photo: "/api/analyze-photo",
  signature: "/api/analyze-signature"
};
const translations = {
  he: {
    navGenerate:"יצירת חתימה",navPhoto:"ניתוח תמונה",navSignature:"ניתוח חתימה",
    titleGenerate:"חתימה בהשראת הפנים שלך",titlePhoto:"תנתח את התמונה שלי",
    titleSignature:"תנתח את החתימה שלי",
    fullName:"שם מלא",portrait:"תמונת פנים",signatureImage:"תמונת חתימה",apiKey:"מפתח API",
    generate:"יצירת חתימה",analyzePhoto:"נתח תמונה",analyzeSignature:"נתח חתימה",
    downloadPng:"הורדת חתימה PNG",downloadVideo:"הורדת סרטון MP4",
    working:"מעבד תמונה...",ready:"התוצאה מוכנה",serverError:"שגיאה מהשרת",
    missing:"השרת לא החזיר תוצאה תקינה",offline:"לא ניתן להתחבר לשרת.",
    visualTraits:"מאפיינים חזותיים",writingEffects:"השפעה על החתימה",
    alt:"חתימה על רקע שקוף",placeholder:"שם מלא",
    toggle:"English",toggleLabel:"Switch to English",
    impression:"התמונה משדרת",unknown:"מאפיינים מעורבים",
    joy:"שמחה",sadness:"עצב",anger:"כעס",tension:"מתח",calm:"רוגע",
    cute:"חמידות",tough:"קשיחות",villainous:"אווירה אפלה",friendly:"נחמדות",
    playful:"שובבות",elegance:"אלגנטיות",energy:"אנרגיה",confidence:"ביטחון",
    shyness:"איפוק",dramatic:"דרמטיות",head_tilt:"הטיית ראש",softness:"רכות",
    lighting_contrast:"ניגודיות",
    pressure:"לחץ עט",speed:"מהירות",roundness:"עגלגלות",width:"רוחב אותיות",
    height:"גובה אותיות",slant:"נטייה",irregularity:"אי סדירות",
    flourish:"סלסול סיום",rise:"שיפוע כתיבה",spacing:"ריווח",
    description:"תיאור",signatureImpression:"רושם אמנותי",
    line_pressure:"לחץ הקו",rhythm:"קצב",connections:"חיבורים",
    legibility:"קריאות",letter_shapes:"צורות האותיות",
    baseline:"כיוון שורת הכתיבה",stroke_variation:"שינויי עובי"
  },
  en: {
    navGenerate:"Create signature",navPhoto:"Analyze photo",navSignature:"Analyze signature",
    titleGenerate:"A signature inspired by your face",titlePhoto:"Analyze my photo",
    titleSignature:"Analyze my signature",
    fullName:"Full name",portrait:"Face photo",signatureImage:"Signature image",apiKey:"API key",
    generate:"Create signature",analyzePhoto:"Analyze photo",analyzeSignature:"Analyze signature",
    downloadPng:"Download signature PNG",downloadVideo:"Download MP4 video",
    working:"Analyzing image...",ready:"Result is ready",serverError:"Server error",
    missing:"The server did not return a valid result",offline:"Cannot connect to the server.",
    visualTraits:"Visual impressions",writingEffects:"Signature effects",
    alt:"Signature on transparent background",placeholder:"Your full name",
    toggle:"עברית",toggleLabel:"מעבר לעברית",
    impression:"This photo conveys",unknown:"a mix of impressions",
    joy:"Joy",sadness:"Sadness",anger:"Anger",tension:"Tension",calm:"Calm",
    cute:"Cuteness",tough:"Toughness",villainous:"Dark mood",friendly:"Friendliness",
    playful:"Playfulness",elegance:"Elegance",energy:"Energy",confidence:"Confidence",
    shyness:"Restraint",dramatic:"Dramatic flair",head_tilt:"Head tilt",softness:"Softness",
    lighting_contrast:"Contrast",
    pressure:"Pen pressure",speed:"Speed",roundness:"Roundness",width:"Letter width",
    height:"Letter height",slant:"Slant",irregularity:"Irregularity",
    flourish:"Final flourish",rise:"Writing rise",spacing:"Spacing",
    description:"Description",signatureImpression:"Creative impression",
    line_pressure:"Line pressure",rhythm:"Rhythm",connections:"Connections",
    legibility:"Legibility",letter_shapes:"Letter shapes",
    baseline:"Writing baseline",stroke_variation:"Stroke variation"
  }
};
let language = "he";
try {
  if (typeof localStorage !== "undefined"
      && localStorage.getItem("sig-nature-language") === "en") language = "en";
} catch (_) { /* preferences are optional */ }
let statusKey = null;
let statusDetails = "";
const mode = document.body?.dataset?.page || "generate";
const form = document.querySelector(
  mode === "generate" ? "#signature-form"
  : mode === "photo" ? "#photo-analysis-form" : "#signature-analysis-form"
);
const status = document.querySelector("#status");
const results = document.querySelector("#results");
const toggle = document.querySelector("#language-toggle");
let latestAnalysis = null;

function translate(key) { return translations[language][key] || key; }
function renderLanguage() {
  document.documentElement.lang = language;
  document.documentElement.dir = language === "he" ? "rtl" : "ltr";
  document.querySelectorAll("[data-i18n]").forEach(el => {
    el.textContent = translate(el.dataset.i18n);
  });
  const name = document.querySelector("#full-name");
  if (mode === "generate") {
    name.placeholder = translate("placeholder");
    document.querySelector("#signature-preview").alt = translate("alt");
  }
  toggle.textContent = translate("toggle");
  toggle.setAttribute("aria-label", translate("toggleLabel"));
  if (statusKey) status.textContent = translate(statusKey) + statusDetails;
  if (latestAnalysis) showAnalysis(latestAnalysis);
}
toggle.addEventListener("click", () => {
  language = language === "he" ? "en" : "he";
  try {
    if (typeof localStorage !== "undefined")
      localStorage.setItem("sig-nature-language", language);
  } catch (_) { /* preferences are optional */ }
  renderLanguage();
});
function setStatus(key, details = "", error = false) {
  statusKey = key;
  statusDetails = details;
  status.dataset.error = String(error);
  status.textContent = translate(key) + details;
}
function showMetrics(container, data) {
  container.replaceChildren();
  for (const [key, value] of Object.entries(data)) {
    const title = document.createElement("dt");
    title.textContent = translate(key);
    const detail = document.createElement("dd");
    detail.textContent = typeof value !== "number" ? String(value)
      : ["width", "height", "spacing"].includes(key) ? value.toFixed(2) + "×"
      : Math.round(value * 100) + "%";
    container.append(title, detail);
  }
}
function showAnalysis(data) {
  const info = document.querySelector("#analysis-details");
  const description = document.querySelector("#analysis-description");
  if (mode === "photo") {
    const leaders = Object.entries(data.traits)
      .filter(([name]) => !["head_tilt","lighting_contrast"].includes(name))
      .sort((a,b) => b[1]-a[1]).slice(0, 4)
      .filter(item => item[1] >= 0.55)
      .map(([name]) => translate(name));
    const visibleCues = Array.isArray(data.cues) ? data.cues : [];
    description.textContent = data.summary
      ? [data.summary, ...visibleCues.map(cue => "• " + cue), data.vibe]
          .filter(Boolean).join("\n")
      : translate("impression") + ": "
          + (leaders.join(", ") || translate("unknown"));
    showMetrics(info, data.traits);
    showMetrics(document.querySelector("#writing-details"), data.writing_style);
  } else {
    description.textContent = data.analysis.description + "\n\n"
      + data.analysis.impression;
    showMetrics(info, data.analysis.features);
  }
}
function showGenerated(data) {
  if (!data.signature_png_url || !data.animation_mp4_url) return false;
  document.querySelector("#signature-preview").src = data.signature_png_url;
  document.querySelector("#download-png").href = data.signature_png_url;
  document.querySelector("#animation-preview").src = data.animation_mp4_url;
  document.querySelector("#download-video").href = data.animation_mp4_url;
  return true;
}
if (form) form.addEventListener("submit", async event => {
  event.preventDefault();
  results.hidden = true;
  const button = document.querySelector(mode === "generate" ? "#generate" : "#analyze");
  const data = new FormData();
  if (mode === "generate") {
    data.set("full_name", document.querySelector("#full-name").value.trim());
    data.set("portrait", document.querySelector("#portrait").files[0]);
  } else {
    data.set("image", document.querySelector("#analysis-image").files[0]);
    data.set("language", language);
  }
  data.set("api_key", document.querySelector("#api-key").value);
  button.disabled = true;
  setStatus("working");
  try {
    const response = await fetch(API_ENDPOINTS[mode], {method:"POST",body:data});
    if (!response.ok) {
      const failure = await response.json().catch(() => ({}));
      setStatus("serverError", " (" + response.status + "): " + (failure.detail || ""), true);
      return;
    }
    const payload = await response.json();
    if (mode === "generate" ? !showGenerated(payload)
        : mode === "photo" ? !payload.traits || !payload.writing_style
        : !payload.analysis) {
      setStatus("missing", "", true);
      return;
    }
    if (mode !== "generate") {
      latestAnalysis = payload;
      showAnalysis(payload);
    }
    results.hidden = false;
    setStatus("ready");
  } catch (error) {
    setStatus("offline", "", true);
  } finally {
    button.disabled = false;
    document.querySelector("#api-key").value = "";
  }
});
renderLanguage();