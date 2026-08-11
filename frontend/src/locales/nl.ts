import type { AppResources } from "./en";

// Typed against the English resources, so a key added there fails the build here until it is
// translated. That is deliberate — a missing translation should not be discovered by a user
// seeing an untranslated string.
export const nl: AppResources = {
  app: {
    title: "Elestral Vault",
    logout: "Uitloggen",
    signIn: "Inloggen",
    language: "Taal",
    loadError: "Je profiel kon niet worden geladen",

    auth: {
      redirecting: "Je wordt doorgestuurd naar het inloggen…",
      manual: "Gebeurt er niets? Ga dan handmatig verder.",
      continueToSignIn: "Verder naar inloggen",
    },

    profile: {
      title: "Profiel",
      subtitle: "Je account en hoe je verzameling zich gedraagt.",

      accountSection: "Account",
      accountHint:
        "Deze gegevens komen uit je platformaccount en worden daar gewijzigd, niet hier.",
      email: "E-mailadres",
      username: "Weergavenaam",
      subject: "Gebruikers-id",
      enriched: "Verrijkt vanuit het platform",
      enrichedYes: "Ja",
      enrichedNo: "Nee — dit komt uit je token",
      manageAccount: "Beheer je account",

      preferencesSection: "Voorkeuren",
      handle: "Gebruikersnaam",
      handleHelp:
        "Wordt gebruikt voor de openbare link naar je verzameling. Letters, cijfers, koppelteken en liggend streepje, 3–32 tekens.",
      handlePlaceholder: "niet ingesteld",
      visibility: "Zichtbaarheid van je verzameling",
      visibilityHelp: "Wie je verzameling kan openen.",
      visibilityPrivate: "Privé — alleen jij",
      visibilityLink: "Iedereen met de link",
      visibilityPublic: "Openbaar — vindbaar voor iedereen",
      currency: "Valuta",
      currencyHelp: "Wordt gebruikt om waarden te tonen. Er wordt nog niets omgerekend.",
      conditionScale: "Conditieschaal",
      conditionScaleHelp: "Welke conditiebenaming de app toont.",
      conditionScaleTcg: "TCGplayer (NM, LP, MP, HP, DMG)",
      conditionScaleCardmarket: "Cardmarket (MT, NM, EX, GD, LP, PL, PO)",

      save: "Wijzigingen opslaan",
      saving: "Opslaan…",
      saved: "Opgeslagen",
      discard: "Ongedaan maken",
      noChanges: "Geen niet-opgeslagen wijzigingen",

      errorHandleTaken: "Deze gebruikersnaam is al bezet.",
      errorInvalid: "Deze waarde is niet toegestaan.",
      errorGeneric: "Je wijzigingen konden niet worden opgeslagen.",
    },
  },
};
