import { MenuItem, TextField } from "@mui/material";
import { useTranslation } from "react-i18next";
import { LANGUAGE_LABELS, SUPPORTED_LANGUAGES } from "../locales";
import type { SupportedLanguage } from "../locales";

// Switches the shared i18next instance; the language detector persists the choice to
// localStorage, so the whole app (login form included) re-renders in the chosen language.
export function LanguageSwitcher() {
  const { i18n, t } = useTranslation("app");
  const resolved = (i18n.resolvedLanguage ?? i18n.language ?? "en") as string;
  const current: SupportedLanguage = (SUPPORTED_LANGUAGES as readonly string[]).includes(resolved)
    ? (resolved as SupportedLanguage)
    : "en";

  return (
    <TextField
      select
      size="small"
      variant="standard"
      value={current}
      onChange={(event) => void i18n.changeLanguage(event.target.value)}
      label={t("language")}
      sx={{ minWidth: 120 }}
    >
      {SUPPORTED_LANGUAGES.map((lng) => (
        <MenuItem key={lng} value={lng}>
          {LANGUAGE_LABELS[lng]}
        </MenuItem>
      ))}
    </TextField>
  );
}
