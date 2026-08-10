// The merged i18next resource tree: this app's own "app" namespace plus the login UI's "login"
// namespace shipped by @lars-kluijtmans/react-login — so ONE instance and ONE language switch
// cover the whole app, login form included.
import { loginI18nResources } from "@lars-kluijtmans/react-login";
import { en } from "./en";
import { nl } from "./nl";

export const SUPPORTED_LANGUAGES = ["en", "nl"] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

export const LANGUAGE_LABELS: Record<SupportedLanguage, string> = {
  en: "English",
  nl: "Nederlands",
};

export const resources = {
  en: { ...en, ...loginI18nResources.en },
  nl: { ...nl, ...loginI18nResources.nl },
};
