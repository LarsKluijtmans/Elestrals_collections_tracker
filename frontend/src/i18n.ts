// One shared i18next instance for the whole app. Imported once from main.tsx before render.
// Detects the language from a persisted choice (localStorage) then the browser, falling back to
// English.
//
// The storage key is shared with the platform's own apps on purpose: someone who picked Dutch
// on login-web arrives here already in Dutch, and vice versa.
import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";
import { resources, SUPPORTED_LANGUAGES } from "./locales";

export const LANGUAGE_STORAGE_KEY = "platform.lang";

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: "en",
    supportedLngs: [...SUPPORTED_LANGUAGES],
    nonExplicitSupportedLngs: true, // treat "nl-NL" as "nl"
    load: "languageOnly",
    defaultNS: "app",
    detection: {
      order: ["localStorage", "navigator"],
      lookupLocalStorage: LANGUAGE_STORAGE_KEY,
      caches: ["localStorage"],
    },
    interpolation: { escapeValue: false },
  });

export default i18n;
