export const en = {
  app: {
    title: "Elestral Vault",
    logout: "Sign out",
    signIn: "Sign in",
    language: "Language",
    loadError: "Could not load your profile",

    auth: {
      redirecting: "Taking you to sign in…",
      manual: "If nothing happens, continue manually.",
      continueToSignIn: "Continue to sign in",
    },

    profile: {
      title: "Profile",
      subtitle: "Your account and how your collection behaves.",

      accountSection: "Account",
      accountHint:
        "These come from your platform account and are edited there, not here.",
      email: "Email",
      username: "Display name",
      subject: "User id",
      enriched: "Enriched from the platform",
      enrichedYes: "Yes",
      enrichedNo: "No — showing what your token carries",
      manageAccount: "Manage your account",

      preferencesSection: "Preferences",
      handle: "Handle",
      handleHelp:
        "Used for your public collection link. Letters, numbers, hyphen and underscore, 3–32 characters.",
      handlePlaceholder: "not set",
      visibility: "Collection visibility",
      visibilityHelp: "Who can open your collection.",
      visibilityPrivate: "Private — only you",
      visibilityLink: "Anyone with the link",
      visibilityPublic: "Public — listed and searchable",
      currency: "Currency",
      currencyHelp: "Used to display values. Nothing is converted yet.",
      conditionScale: "Condition scale",
      conditionScaleHelp: "Which grading vocabulary the app shows.",
      conditionScaleTcg: "TCGplayer (NM, LP, MP, HP, DMG)",
      conditionScaleCardmarket: "Cardmarket (MT, NM, EX, GD, LP, PL, PO)",

      save: "Save changes",
      saving: "Saving…",
      saved: "Saved",
      discard: "Discard",
      noChanges: "No unsaved changes",

      errorHandleTaken: "That handle is already taken.",
      errorInvalid: "That value is not allowed.",
      errorGeneric: "Could not save your changes.",
    },
  },
};

export type AppResources = typeof en;
