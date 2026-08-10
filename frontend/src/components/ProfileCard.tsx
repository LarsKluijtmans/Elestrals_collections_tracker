// Loads the profile from OUR backend (which validated the token and enriched via M2M).
//
// Platform-owned fields — email, display name — render read-only with a link to the
// platform's own /account, because that is where they are actually edited. App-owned
// preferences are editable and land in `user_profiles`.
import { useAuth } from "@lars-kluijtmans/react-auth";
import {
  Alert, Card, CardContent, Chip, CircularProgress, Divider, Link, Stack, Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { fetchProfile, reportClientEvent } from "../api/backend";
import type { Profile } from "../api/backend";
import { env } from "../env";

export function ProfileCard() {
  const { getAccessToken } = useAuth();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchProfile(getAccessToken)
      .then((p) => {
        if (!active) return;
        setProfile(p);
        void reportClientEvent({ message: "profile.viewed", component: "profile-card" });
      })
      .catch((e: unknown) => {
        if (active) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      active = false;
    };
  }, [getAccessToken]);

  if (error) return <Alert severity="error">Could not load your profile: {error}</Alert>;
  if (!profile) {
    return <Stack sx={{ py: 12, alignItems: "center" }}><CircularProgress /></Stack>;
  }

  const name = profile.username || profile.email || profile.user_sub;

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" sx={{ fontWeight: 700 }}>{name}</Typography>
        <Typography variant="body2" color="text.secondary">{profile.email ?? "—"}</Typography>

        <Divider sx={{ my: 4 }} />

        <Typography variant="overline" color="text.disabled">Platform account</Typography>
        <Stack spacing={2} sx={{ mt: 2 }}>
          <Row label="Subject" value={profile.user_sub} />
          <Row label="Email" value={profile.email} />
          <Row label="Display name" value={profile.username} />
        </Stack>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 3 }}>
          These are managed by the platform. Change them in{" "}
          <Link href={`${env.loginApiUrl.replace(/\/$/, "")}/account`} target="_blank" rel="noreferrer">
            your account settings
          </Link>
          .
        </Typography>

        <Divider sx={{ my: 4 }} />

        <Typography variant="overline" color="text.disabled">Vault preferences</Typography>
        <Stack spacing={2} sx={{ mt: 2 }}>
          <Row label="Handle" value={profile.handle} />
          <Row label="Collection visibility" value={profile.collection_visibility} />
          <Row label="Default currency" value={profile.default_currency} />
          <Row label="Condition scale" value={profile.condition_scale} />
        </Stack>

        <Stack direction="row" spacing={2} sx={{ mt: 4, alignItems: "center" }}>
          <Typography variant="body2" color="text.secondary">Identity enrichment</Typography>
          <Chip
            size="small"
            color={profile.enriched ? "success" : "default"}
            label={profile.enriched ? "live from auth-api" : "token claims only"}
          />
        </Stack>
      </CardContent>
    </Card>
  );
}

function Row({ label, value }: { label: string; value?: string | null }) {
  return (
    <Stack direction="row" spacing={4} sx={{ justifyContent: "space-between" }}>
      <Typography variant="body2" color="text.secondary">{label}</Typography>
      <Typography variant="body2" sx={{ fontFamily: "monospace", textAlign: "right", wordBreak: "break-all" }}>
        {value || "—"}
      </Typography>
    </Stack>
  );
}
