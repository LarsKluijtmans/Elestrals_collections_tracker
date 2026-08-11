// This app's own "app" namespace.
//
// The login UI's "login" namespace used to be merged in here, because the embedded <LoginForm>
// read its strings from this same i18next instance. Sign-in is now a redirect to login-web,
// which owns and translates its own page — so merging those resources would ship strings
// nothing renders. The language choice still carries across: it is persisted to localStorage
// under a key the platform's own apps share.
import { en } from "./en";
import { nl } from "./nl";

export const SUPPORTED_LANGUAGES = ["en", "nl"] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

export const LANGUAGE_LABELS: Record<SupportedLanguage, string> = {
  en: "English",
  nl: "Nederlands",
};

export const resources = { en, nl };
