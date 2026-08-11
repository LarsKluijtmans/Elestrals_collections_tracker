# Elestral Vault web image — nginx serving the pre-built SPA.
#
# The build happens on the HOST, not in this image, because `@lars-kluijtmans/react-auth` and
# `react-login` are NOT published to npm (both 404). They resolve from the sibling ../auth
# checkout via `scripts/use-local-sdks.ps1`, which cannot run inside a build container.
#
#   powershell -ExecutionPolicy Bypass -File scripts\use-local-sdks.ps1
#   cd frontend && npm run build          # bakes .env.production into dist/
#   docker compose build elestrals-web    # this image only copies dist/
#
# Every VITE_* value is baked into the bundle at build time and is therefore PUBLIC. There is
# no client secret in it — the login client is a public PKCE client, which is the entire reason
# it does not need one.
#
# Once the react SDKs are on npm this can become a normal two-stage build.
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY dist/ /usr/share/nginx/html/

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null 2>&1 || exit 1
