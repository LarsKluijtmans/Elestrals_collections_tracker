// /settings/profile — story 030, pulled forward from bolt 009.
//
// Two halves, deliberately separated: platform-owned identity is READ-ONLY here with a link to
// the platform's own account page, because that is where it is actually edited. App-owned
// preferences land in `user_profiles` via PATCH /api/v1/me.
//
// Every string comes from the `app` i18n namespace, so the page renders in EN and NL from the
// same switch that drives the rest of the shell.
import { useAuth } from "@lars-kluijtmans/react-auth";
import {
  Alert, Box, Button, Card, CardContent, Divider, MenuItem, Skeleton, Snackbar,
  Stack, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, fetchProfile, updateProfile } from "../api/backend";
import type { Profile, ProfilePatch } from "../api/backend";
import { env } from "../env";
import { LanguageSwitcher } from "../components/LanguageSwitcher";
import { DangerZone } from "../components/DangerZone";
import { ShareCard } from "../components/ShareCard";

const CURRENCIES = ["EUR", "USD", "GBP"] as const;

/** Only the fields this page owns; everything else on Profile is platform-owned. */
type Editable = Pick<
  Profile, "handle" | "collection_visibility" | "default_currency" | "condition_scale"
>;

function editableOf(p: Profile): Editable {
  return {
    handle: p.handle,
    collection_visibility: p.collection_visibility,
    default_currency: p.default_currency,
    condition_scale: p.condition_scale,
  };
}

function ReadOnly({ label, value }: { label: string; value: string }) {
  return (
    <Box>
      <Typography sx={{ fontSize: 11, color: "text.disabled", textTransform: "uppercase" }}>
        {label}
      </Typography>
      <Typography sx={{ fontSize: 14 }}>{value}</Typography>
    </Box>
  );
}

export function ProfilePage() {
  const { t } = useTranslation("app");
  const { getAccessToken } = useAuth();
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["profile"],
    queryFn: () => fetchProfile(getAccessToken),
  });

  const [draft, setDraft] = useState<Editable | null>(null);
  const [saved, setSaved] = useState(false);

  // Seed the form once the profile arrives, and re-seed after a save so "dirty" is computed
  // against what the server actually stored rather than what we hoped it would.
  useEffect(() => {
    if (data) setDraft(editableOf(data));
  }, [data]);

  const save = useMutation({
    mutationFn: (patch: ProfilePatch) => updateProfile(patch, getAccessToken),
    onSuccess: (updated) => {
      queryClient.setQueryData(["profile"], updated);
      setDraft(editableOf(updated));
      setSaved(true);
    },
  });

  if (isLoading || !draft) return <Skeleton variant="rounded" height={420} />;
  if (error || !data) return <Alert severity="error">{t("loadError")}</Alert>;

  const dirty = JSON.stringify(draft) !== JSON.stringify(editableOf(data));

  function set<K extends keyof Editable>(key: K, value: Editable[K]) {
    setDraft((d) => (d ? { ...d, [key]: value } : d));
  }

  function onSave() {
    if (!draft) return;
    // Send only what changed — the backend uses exclude_unset, so an omitted field is left
    // alone rather than nulled.
    const base = editableOf(data!);
    const patch: ProfilePatch = {};
    for (const key of Object.keys(draft) as (keyof Editable)[]) {
      if (draft[key] !== base[key]) (patch as Record<string, unknown>)[key] = draft[key];
    }
    save.mutate(patch);
  }

  // The backend's error codes are stable and safe to branch on; the messages are not.
  const failure = save.error;
  const failureText =
    failure instanceof ApiError
      ? failure.code === "handle_taken"
        ? t("profile.errorHandleTaken")
        : failure.code === "invalid_preference"
          ? t("profile.errorInvalid")
          : t("profile.errorGeneric")
      : failure
        ? t("profile.errorGeneric")
        : null;

  return (
    <Stack sx={{ gap: 3, maxWidth: 720 }}>
      <Box>
        <Typography variant="h1" sx={{ fontSize: 25, fontWeight: 650 }}>
          {t("profile.title")}
        </Typography>
        <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
          {t("profile.subtitle")}
        </Typography>
      </Box>

      {failureText && <Alert severity="error">{failureText}</Alert>}

      {/* --- platform-owned, read-only ------------------------------------------------ */}
      <Card variant="outlined">
        <CardContent>
          <Typography sx={{ fontSize: 16, fontWeight: 650, mb: 0.5 }}>
            {t("profile.accountSection")}
          </Typography>
          <Typography sx={{ fontSize: 12, color: "text.secondary", mb: 2 }}>
            {t("profile.accountHint")}
          </Typography>

          <Stack sx={{ gap: 2 }}>
            <ReadOnly label={t("profile.email")} value={data.email ?? "—"} />
            <ReadOnly label={t("profile.username")} value={data.username ?? "—"} />
            <ReadOnly label={t("profile.subject")} value={data.user_sub} />
            <ReadOnly
              label={t("profile.enriched")}
              value={data.enriched ? t("profile.enrichedYes") : t("profile.enrichedNo")}
            />
          </Stack>

          <Button
            size="small"
            sx={{ mt: 2, px: 0 }}
            href={`${env.loginApiUrl.replace(/\/$/, "")}/account`}
            target="_blank"
            rel="noreferrer"
          >
            {t("profile.manageAccount")}
          </Button>
        </CardContent>
      </Card>

      {/* --- app-owned, editable ------------------------------------------------------ */}
      <Card variant="outlined">
        <CardContent>
          <Typography sx={{ fontSize: 16, fontWeight: 650, mb: 2 }}>
            {t("profile.preferencesSection")}
          </Typography>

          <Stack sx={{ gap: 3 }}>
            <TextField
              label={t("profile.handle")}
              helperText={t("profile.handleHelp")}
              placeholder={t("profile.handlePlaceholder")}
              value={draft.handle ?? ""}
              onChange={(e) => set("handle", e.target.value || null)}
              size="small"
              slotProps={{ htmlInput: { minLength: 3, maxLength: 32 } }}
            />

            <TextField
              select
              label={t("profile.visibility")}
              helperText={t("profile.visibilityHelp")}
              value={draft.collection_visibility}
              onChange={(e) =>
                set("collection_visibility", e.target.value as Editable["collection_visibility"])
              }
              size="small"
            >
              <MenuItem value="private">{t("profile.visibilityPrivate")}</MenuItem>
              <MenuItem value="link">{t("profile.visibilityLink")}</MenuItem>
              <MenuItem value="public">{t("profile.visibilityPublic")}</MenuItem>
            </TextField>

            <TextField
              select
              label={t("profile.currency")}
              helperText={t("profile.currencyHelp")}
              value={draft.default_currency}
              onChange={(e) => set("default_currency", e.target.value)}
              size="small"
            >
              {CURRENCIES.map((c) => (
                <MenuItem key={c} value={c}>{c}</MenuItem>
              ))}
            </TextField>

            <TextField
              select
              label={t("profile.conditionScale")}
              helperText={t("profile.conditionScaleHelp")}
              value={draft.condition_scale}
              onChange={(e) =>
                set("condition_scale", e.target.value as Editable["condition_scale"])
              }
              size="small"
            >
              <MenuItem value="tcg">{t("profile.conditionScaleTcg")}</MenuItem>
              <MenuItem value="cardmarket">{t("profile.conditionScaleCardmarket")}</MenuItem>
            </TextField>

            <Divider />

            {/* The language switch lives here as well as in the top bar — a profile page is
                where someone looks for it. Both drive the same i18next instance. */}
            <Box>
              <LanguageSwitcher />
            </Box>
          </Stack>

          <Stack direction="row" sx={{ gap: 1.5, mt: 3, alignItems: "center" }}>
            <Button
              variant="contained"
              disabled={!dirty || save.isPending}
              onClick={onSave}
            >
              {save.isPending ? t("profile.saving") : t("profile.save")}
            </Button>
            <Button
              disabled={!dirty || save.isPending}
              onClick={() => setDraft(editableOf(data))}
            >
              {t("profile.discard")}
            </Button>
            {!dirty && (
              <Typography sx={{ fontSize: 12, color: "text.disabled" }}>
                {t("profile.noChanges")}
              </Typography>
            )}
          </Stack>
        </CardContent>
      </Card>

      <ShareCard visibility={data.collection_visibility} handle={data.handle} />

      <DangerZone />

      <Snackbar
        open={saved}
        autoHideDuration={3000}
        onClose={() => setSaved(false)}
        message={t("profile.saved")}
      />
    </Stack>
  );
}
