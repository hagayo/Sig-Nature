"use strict";

// Shared controller for three separate HTML pages. No third-party runtime.
const API_ENDPOINTS = Object.freeze({
  generate: "/api/generate",
  photo: "/api/analyze-photo",
  signature: "/api/analyze-signature"
});
const translations = {
  he: {
    navLabel:"ניווט ראשי",
    navGenerate:"יצירת חתימה", navPhoto:"ניתוח תמונה", navSignature:"ניתוח חתימה",
    titleGenerate:"חתימה בהשראת הפנים שלך", titlePhoto:"תנתח את התמונה שלי",
    titleSignature:"תנתח את החתימה שלי",
    fullName:"שם מלא", portrait:"תמונת פנים", signatureImage:"תמונת חתימה",
    apiKey:"מפתח API", generate:"יצירת חתימה",
    analyzePhoto:"נתח תמונה", analyzeSignature:"נתח חתימה",
    downloadPng:"הורדת חתימה PNG", downloadVideo:"הורדת סרטון MP4",
    working:"מעבד את הבקשה...", ready:"התוצאה מוכנה",
    serverError:"לא ניתן להשלים את הבקשה", missing:"השרת לא החזיר תוצאה תקינה",
    offline:"אין חיבור לשרת. נסה שוב.",
    invalidInput:"הקלט לא תקין. בדוק את השם והתמונה.",
    invalidKey:"מפתח ה-API נדחה. בדוק שהזנת מפתח תקין.",
    providerError:"הניתוח נכשל זמנית. נסה שוב.",
    noFace:"לא נמצאו פנים ברורות בתמונה.",
    noSignature:"לא זוהתה חתימה בתמונה.",
    missingName:"יש להזין שם מלא.",
    nameTooLong:"השם ארוך מדי ליצירת חתימה קריאה. יש לקצר אותו.",
    invalidNameScript:"נתמכים שמות בעברית ובאותיות לטיניות בלבד.",
    invalidImage:"יש לבחור תמונה מסוג JPEG, PNG או WebP.",
    imageTooLarge:"גודל התמונה המקסימלי הוא 8MB.",
    missingKey:"יש להזין מפתח API.",
    visualTraits:"מאפיינים חזותיים", writingEffects:"השפעה על החתימה",
    alt:"חתימה על רקע שקוף", videoLabel:"סרטון כתיבת החתימה",
    placeholder:"שם מלא", toggle:"English", toggleLabel:"Switch to English",
    impression:"התמונה משדרת", unknown:"מאפיינים מעורבים",
    joy:"שמחה", sadness:"עצב", anger:"כעס", tension:"מתח", calm:"רוגע",
    cute:"חמידות", tough:"קשיחות", villainous:"אווירה אפלה", friendly:"נחמדות",
    playful:"שובבות", elegance:"אלגנטיות", energy:"אנרגיה",
    confidence:"ביטחון", shyness:"איפוק", dramatic:"דרמטיות",
    head_tilt:"הטיית ראש", softness:"רכות", lighting_contrast:"ניגודיות",
    pressure:"לחץ עט", speed:"מהירות", roundness:"עגלגלות",
    width:"רוחב אותיות", height:"גובה אותיות", slant:"נטייה",
    irregularity:"אי סדירות", flourish:"סלסול סיום", rise:"שיפוע כתיבה",
    spacing:"ריווח", description:"תיאור", signatureImpression:"רושם אמנותי",
    line_pressure:"עובי הקו הנראה", rhythm:"קצב חזותי", connections:"חיבורים",
    legibility:"קריאות", letter_shapes:"צורות האותיות",
    baseline:"כיוון שורת הכתיבה", stroke_variation:"שינויי עובי"
  },
  en: {
    navLabel:"Main navigation",
    navGenerate:"Create signature", navPhoto:"Analyze photo",
    navSignature:"Analyze signature",
    titleGenerate:"A signature inspired by your face", titlePhoto:"Analyze my photo",
    titleSignature:"Analyze my signature",
    fullName:"Full name", portrait:"Face photo", signatureImage:"Signature image",
    apiKey:"API key", generate:"Create signature",
    analyzePhoto:"Analyze photo", analyzeSignature:"Analyze signature",
    downloadPng:"Download signature PNG", downloadVideo:"Download MP4 video",
    working:"Processing your request...", ready:"Result is ready",
    serverError:"Unable to complete the request", missing:"The server returned an invalid result",
    offline:"Cannot connect to the server. Try again.",
    invalidInput:"Invalid input. Check the name and image.",
    invalidKey:"The API key was rejected. Check the key.",
    providerError:"Analysis is temporarily unavailable. Try again.",
    noFace:"No clearly visible face was found in the image.",
    noSignature:"No recognizable signature was found in the image.",
    missingName:"Enter your full name.",
    nameTooLong:"The name is too long for a legible signature.",
    invalidNameScript:"Only Hebrew and Latin-script names are supported.",
    invalidImage:"Choose a JPEG, PNG or WebP image.",
    imageTooLarge:"Maximum image size is 8 MB.",
    missingKey:"Enter an API key.",
    visualTraits:"Visual impressions", writingEffects:"Signature effects",
    alt:"Signature on transparent background", videoLabel:"Signature writing video",
    placeholder:"Your full name", toggle:"עברית", toggleLabel:"מעבר לעברית",
    impression:"This photo conveys", unknown:"a mix of impressions",
    joy:"Joy", sadness:"Sadness", anger:"Anger", tension:"Tension", calm:"Calm",
    cute:"Cuteness", tough:"Toughness", villainous:"Dark mood", friendly:"Friendliness",
    playful:"Playfulness", elegance:"Elegance", energy:"Energy",
    confidence:"Confidence", shyness:"Restraint", dramatic:"Dramatic flair",
    head_tilt:"Head tilt", softness:"Softness", lighting_contrast:"Contrast",
    pressure:"Pen pressure", speed:"Speed", roundness:"Roundness",
    width:"Letter width", height:"Letter height", slant:"Slant",
    irregularity:"Irregularity", flourish:"Final flourish", rise:"Writing rise",
    spacing:"Spacing", description:"Description", signatureImpression:"Creative impression",
    line_pressure:"Visible stroke weight", rhythm:"Visual flow", connections:"Connections",
    legibility:"Legibility", letter_shapes:"Letter shapes",
    baseline:"Writing baseline", stroke_variation:"Stroke variation"
  }
};

const mode = document.body?.dataset?.page || "generate";
const form = document.querySelector(
  mode === "generate" ? "#signature-form"
  : mode === "photo" ? "#photo-analysis-form" : "#signature-analysis-form"
);
const status = document.querySelector("#status");
const results = document.querySelector("#results");
const toggle = document.querySelector("#language-toggle");
const titleKey = mode === "generate" ? "titleGenerate"
  : mode === "photo" ? "titlePhoto" : "titleSignature";
let language = "he";
try {
  if (typeof localStorage !== "undefined" &&
      localStorage.getItem("sig-nature-language") === "en") language = "en";
} catch (_) { /* Browser storage is optional. */ }
let statusKey = null;
let statusDetails = "";
let latestAnalysis = null;

function translate(key) {
  return translations[language][key] || key;
}

function renderLanguage() {
  document.documentElement.lang = language;
  document.documentElement.dir = language === "he" ? "rtl" : "ltr";
  document.title = translate(titleKey) + " | Sig-Nature";
  document.querySelectorAll("[data-i18n]").forEach(element => {
    element.textContent = translate(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach(element => {
    element.setAttribute("aria-label", translate(element.dataset.i18nAriaLabel));
  });
  const name = document.querySelector("#full-name");
  if (name) name.placeholder = translate("placeholder");
  if (mode === "generate") {
    document.querySelector("#signature-preview").alt = translate("alt");
    document.querySelector("#animation-preview").setAttribute(
      "aria-label", translate("videoLabel")
    );
  }
  toggle.textContent = translate("toggle");
  toggle.setAttribute("aria-label", translate("toggleLabel"));
  if (statusKey) status.textContent = translate(statusKey) + statusDetails;
  if (latestAnalysis) showAnalysis(latestAnalysis);
}

toggle.addEventListener("click", () => {
  language = language === "he" ? "en" : "he";
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem("sig-nature-language", language);
    }
  } catch (_) { /* The interface still works without storage. */ }
  renderLanguage();
});

function setStatus(key, detail = "", error = false) {
  statusKey = key;
  statusDetails = detail;
  status.dataset.error = String(error);
  status.setAttribute("role", error ? "alert" : "status");
  status.setAttribute("aria-live", error ? "assertive" : "polite");
  status.textContent = translate(key) + detail;
}

function clearStatus() {
  statusKey = null;
  statusDetails = "";
  status.textContent = "";
  status.dataset.error = "false";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
}

function showMetrics(container, data) {
  container.replaceChildren();
  for (const [key, value] of Object.entries(data)) {
    if (value === null || value === undefined ||
        typeof value === "object" || (typeof value === "number" && !Number.isFinite(value))) {
      continue;
    }
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
      .filter(([key]) => !["head_tilt", "lighting_contrast"].includes(key))
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4).filter(([, score]) => score >= .55)
      .map(([key]) => translate(key));
    const cues = Array.isArray(data.cues) ? data.cues : [];
    description.textContent = data.summary
      ? [data.summary, ...cues.map(cue => "• " + cue), data.vibe]
          .filter(Boolean).join("\n")
      : translate("impression") + ": " +
          (leaders.join(", ") || translate("unknown"));
    showMetrics(info, data.traits);
    showMetrics(document.querySelector("#writing-details"), data.writing_style);
  } else {
    description.textContent = [data.analysis.description, data.analysis.impression]
      .filter(Boolean).join("\n\n");
    showMetrics(info, data.analysis.features);
  }
}

function localAssetUrl(value) {
  return typeof value === "string" && value.startsWith("/") &&
    !value.startsWith("//") ? value : null;
}

function showGenerated(data) {
  const png = localAssetUrl(data.signature_png_url);
  const mp4 = localAssetUrl(data.animation_mp4_url);
  if (!png || !mp4) return false;
  document.querySelector("#signature-preview").src = png;
  document.querySelector("#download-png").href = png;
  document.querySelector("#animation-preview").src = mp4;
  document.querySelector("#download-video").href = mp4;
  return true;
}

function resetResults() {
  results.hidden = true;
  latestAnalysis = null;
  if (mode === "generate") {
    const video = document.querySelector("#animation-preview");
    video.pause?.();
    video.removeAttribute?.("src");
    video.load?.();
  }
  clearStatus();
}

const imageInput = document.querySelector(
  mode === "generate" ? "#portrait" : "#analysis-image"
);
imageInput?.addEventListener("change", () => {
  if (form?.dataset.busy !== "true") resetResults();
});
document.querySelector("#full-name")?.addEventListener("input", () => {
  if (form?.dataset.busy !== "true") resetResults();
});

function responseErrorKey(code, message) {
  if (code === 400 || code === 401 || code === 403) return "invalidKey";
  if (code === 413) return "imageTooLarge";
  if (code === 415) return "invalidImage";
  if (code === 422) {
    if (/face|פנים/i.test(message)) return "noFace";
    if (/signature|חתימה/i.test(message)) return "noSignature";
    if (/too long|exceeds.*limit/i.test(message)) return "nameTooLong";
    if (/letters|script|characters|unicode|control/i.test(message)) {
      return "invalidNameScript";
    }
    return "invalidInput";
  }
  if (code === 429 || code === 502 || code === 503) return "providerError";
  return "serverError";
}

if (form) form.addEventListener("submit", async event => {
  event.preventDefault();
  if (form.dataset.busy === "true") return;

  const upload = imageInput?.files?.[0];
  if (!upload || (upload.type &&
      !["image/jpeg", "image/png", "image/webp"].includes(upload.type))) {
    setStatus("invalidImage", "", true);
    return;
  }
  if (typeof upload.size === "number" && upload.size > 8 * 1024 * 1024) {
    setStatus("imageTooLarge", "", true);
    return;
  }
  const fullName = mode === "generate"
    ? document.querySelector("#full-name").value.trim() : "";
  if (mode === "generate" && !fullName) {
    setStatus("missingName", "", true);
    return;
  }
  const keyField = document.querySelector("#api-key");
  if (!keyField.value.trim()) {
    setStatus("missingKey", "", true);
    return;
  }
  resetResults();
  const button = document.querySelector(mode === "generate" ? "#generate" : "#analyze");
  const data = new FormData();
  if (mode === "generate") {
    data.set("full_name", fullName);
    data.set("portrait", upload);
  } else {
    data.set("image", upload);
    data.set("language", language);
  }
  data.set("api_key", keyField.value.trim());
  keyField.value = "";
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  form.dataset.busy = "true";
  form.setAttribute("aria-busy", "true");
  setStatus("working");
  try {
    const response = await fetch(API_ENDPOINTS[mode], {
      method: "POST", body: data, cache: "no-store"
    });
    if (!response.ok) {
      const failure = await response.json().catch(() => ({}));
      const detail = typeof failure.detail === "string" ? failure.detail : "";
      setStatus(responseErrorKey(response.status, detail),
        " (" + response.status + ")", true);
      return;
    }
    const payload = await response.json();
    if (!payload || typeof payload !== "object") {
      setStatus("missing", "", true);
      return;
    }
    if (mode === "generate") {
      if (!showGenerated(payload)) {
        setStatus("missing", "", true);
        return;
      }
    } else {
      if (mode === "photo"
          ? !payload.traits || !payload.writing_style
          : !payload.analysis?.features) {
        setStatus("missing", "", true);
        return;
      }
      latestAnalysis = payload;
      showAnalysis(payload);
    }
    results.hidden = false;
    setStatus("ready");
  } catch (_) {
    setStatus("offline", "", true);
  } finally {
    button.disabled = false;
    button.setAttribute("aria-busy", "false");
    form.dataset.busy = "false";
    form.setAttribute("aria-busy", "false");
  }
});
renderLanguage();
