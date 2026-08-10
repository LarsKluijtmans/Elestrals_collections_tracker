/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_LOGIN_API_URL?: string;
  readonly VITE_LOGIN_CLIENT_ID?: string;
  readonly VITE_REDIRECT_URI?: string;
  readonly VITE_BACKEND_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
