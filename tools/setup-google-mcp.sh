#!/usr/bin/env bash
# setup-google-mcp.sh — register Google's first-party Workspace remote MCP
# servers with Claude Code, locally, for battle-buddy's Tier 3 (live-roster)
# testing. Dev/responder tooling — never shipped (tools/ is fenced from the
# plugin bundle by tests/unit/test_packaging.py).
#
# Why these servers: the recommended roster (templates/mcp.recommended.json)
# binds storage/artifacts/diary to community npm packages. Google now hosts
# official remote MCP endpoints for Sheets/Drive/Docs — per-user OAuth, no
# local server process, no service-account tension with the constitution's
# "per-responder credentials" constraint. This script wires them into Claude
# Code; capability names stay identical, so /doctor resolves the same four
# capabilities either way (Constitution VII: rosters carry zero privilege).
#
# Credential posture (FR-007, verified against this CLI version):
#   - The OAuth client SECRET is passed via the MCP_CLIENT_SECRET env var and
#     stored by Claude Code in the OS keychain — it never lands in .mcp.json,
#     ~/.claude.json, argv, or any committable file.
#   - The OAuth client ID does land in the scope's config; a client ID is
#     public by OAuth's design, not a secret.
#   - Default scope is "local" (per responder, per machine, never committed) —
#     matching the constitution's responder-scope rule.
#
# GCP prerequisites (once per person or team):
#   1. A Google Cloud project with an OAuth consent screen configured.
#   2. An OAuth client with the CLI's redirect URI registered. Claude Code's
#      OAuth callback is exactly (verified from CLI v2.1.220):
#          http://localhost:<port>/callback
#      This script fixes the port (default 8976) so the URI is deterministic:
#      register  http://localhost:8976/callback  under "Authorized redirect
#      URIs" on your OAuth client. Notes:
#      - https://claude.ai/api/mcp/auth_callback is the callback for
#        Claude.ai / Claude Desktop *connectors* — registering only that one
#        yields "Error 400: redirect_uri_mismatch" for the local CLI. The
#        same Web-application client can carry both URIs; keep claude.ai's
#        if you also use the connector UI, and add the localhost one.
#      - A "Desktop app" type client accepts loopback redirects on any port,
#        so it works without registering the URI; the fixed port is harmless
#        there too.
#   3. The corresponding Google APIs enabled for the project.
#   During the browser consent, review the scopes requested. The constitution
#   wants agent credentials read-only by default; storage/artifacts/diary are
#   the contractual write exceptions (they exist to be written).
#
# Usage:
#   export GOOGLE_OAUTH_CLIENT_ID="...apps.googleusercontent.com"
#   export GOOGLE_OAUTH_CLIENT_SECRET="..."          # never pass as a flag
#   tools/setup-google-mcp.sh                         # sheets drive docs
#   tools/setup-google-mcp.sh gmail calendar          # extras, if wanted
#   tools/setup-google-mcp.sh --scope project sheets  # team .mcp.json (ID only)
#   tools/setup-google-mcp.sh --dry-run               # print, don't execute
#   tools/setup-google-mcp.sh --remove                # undo (same scope rules)
#
# After it runs: restart the Claude Code session, run /mcp to complete each
# server's OAuth in the browser, then /doctor to re-resolve bindings.
set -euo pipefail

# ---------------------------------------------------------------------------
# product -> (server name, url). Names for battle-buddy's three capabilities
# follow the recommended-roster convention (capability-google-product) so a
# roster reads the same regardless of which binding backs it.
# bash-3.2-compatible (macOS default): no associative arrays.
# ---------------------------------------------------------------------------
server_name() {
  case "$1" in
    sheets)   echo "storage-google-sheets" ;;
    drive)    echo "artifacts-google-drive" ;;
    docs)     echo "diary-google-docs" ;;
    gmail)    echo "google-gmail" ;;
    slides)   echo "google-slides" ;;
    calendar) echo "google-calendar" ;;
    chat)     echo "google-chat" ;;
    people)   echo "google-people" ;;
    *)        return 1 ;;
  esac
}

server_url() {
  case "$1" in
    sheets)   echo "https://sheetsmcp.googleapis.com/mcp/v1" ;;
    drive)    echo "https://drivemcp.googleapis.com/mcp/v1" ;;
    docs)     echo "https://docsmcp.googleapis.com/mcp/v1" ;;
    gmail)    echo "https://gmailmcp.googleapis.com/mcp/v1" ;;
    slides)   echo "https://slidesmcp.googleapis.com/mcp/v1" ;;
    calendar) echo "https://calendarmcp.googleapis.com/mcp/v1" ;;
    chat)     echo "https://chatmcp.googleapis.com/mcp/v1" ;;
    people)   echo "https://people.googleapis.com/mcp/v1" ;;
    *)        return 1 ;;
  esac
}

ALL_PRODUCTS="sheets drive docs gmail slides calendar chat people"
DEFAULT_PRODUCTS="sheets drive docs"   # battle-buddy: storage, artifacts, diary

# ---------------------------------------------------------------------------
# args
# ---------------------------------------------------------------------------
SCOPE="local"
DRY_RUN=0
REMOVE=0
# Fixed by default so the redirect URI is deterministic and registrable:
# http://localhost:8976/callback (see GCP prerequisites above). Override with
# --callback-port; a fixed port only binds during the OAuth exchange.
CALLBACK_PORT="8976"
PRODUCTS=""

usage() { sed -n '2,54p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
  case "$1" in
    --scope)          SCOPE="$2"; shift 2 ;;
    --callback-port)  CALLBACK_PORT="$2"; shift 2 ;;
    --dry-run)        DRY_RUN=1; shift ;;
    --remove)         REMOVE=1; shift ;;
    -h|--help)        usage; exit 0 ;;
    --*)              echo "unknown flag: $1" >&2; exit 2 ;;
    *)                PRODUCTS="$PRODUCTS $1"; shift ;;
  esac
done
PRODUCTS="${PRODUCTS# }"
[ -n "$PRODUCTS" ] || PRODUCTS="$DEFAULT_PRODUCTS"

case "$SCOPE" in
  local|user|project) ;;
  *) echo "invalid --scope '$SCOPE' (local|user|project)" >&2; exit 2 ;;
esac

for p in $PRODUCTS; do
  server_name "$p" >/dev/null 2>&1 || {
    echo "unknown product '$p' (choose from: $ALL_PRODUCTS)" >&2; exit 2; }
done

command -v claude >/dev/null || { echo "claude CLI not found on PATH" >&2; exit 2; }

# ---------------------------------------------------------------------------
# remove mode — undo, then exit
# ---------------------------------------------------------------------------
if [ "$REMOVE" = 1 ]; then
  for p in $PRODUCTS; do
    name="$(server_name "$p")"
    if [ "$DRY_RUN" = 1 ]; then
      echo "would run: claude mcp remove $name -s $SCOPE"
    else
      claude mcp remove "$name" -s "$SCOPE" || true
    fi
  done
  exit 0
fi

# ---------------------------------------------------------------------------
# add mode
# ---------------------------------------------------------------------------
: "${GOOGLE_OAUTH_CLIENT_ID:?set GOOGLE_OAUTH_CLIENT_ID (…apps.googleusercontent.com)}"
: "${GOOGLE_OAUTH_CLIENT_SECRET:?set GOOGLE_OAUTH_CLIENT_SECRET (from the same OAuth client)}"

if [ "$SCOPE" = "project" ]; then
  cat >&2 <<'NOTE'
note: --scope project writes .mcp.json in this directory. Only the server URL
and the OAuth client ID land there (the secret goes to the OS keychain), but
review the file before committing — and each teammate still completes their
own OAuth consent, per-responder (constitution: responder scope is never
shared).
NOTE
fi

added=""
for p in $PRODUCTS; do
  name="$(server_name "$p")"
  url="$(server_url "$p")"
  # rebuild argv per server; --callback-port only when given
  set -- --transport http -s "$SCOPE" \
         --client-id "$GOOGLE_OAUTH_CLIENT_ID" --client-secret
  [ -n "$CALLBACK_PORT" ] && set -- "$@" --callback-port "$CALLBACK_PORT"
  set -- "$@" "$name" "$url"

  if [ "$DRY_RUN" = 1 ]; then
    echo "would run: MCP_CLIENT_SECRET=*** claude mcp add $*"
    continue
  fi
  # replace-if-present keeps reruns idempotent (a second run updates, never dupes)
  claude mcp remove "$name" -s "$SCOPE" >/dev/null 2>&1 || true
  MCP_CLIENT_SECRET="$GOOGLE_OAUTH_CLIENT_SECRET" claude mcp add "$@"
  added="$added $name"
done

[ "$DRY_RUN" = 1 ] && exit 0

cat <<DONE

added:$added (scope: $SCOPE)

next steps:
  1. confirm your OAuth client's "Authorized redirect URIs" includes
       http://localhost:${CALLBACK_PORT}/callback
     (https://claude.ai/api/mcp/auth_callback alone is the *connector*
     callback and yields Error 400: redirect_uri_mismatch for the CLI)
  2. restart your Claude Code session (new servers load at startup)
  3. run /mcp and complete the browser OAuth for each server
  4. battle-buddy roster check: sheets/drive/docs cover storage, artifacts and
     diary — the alerting capability still needs its own server (e.g. the
     PagerDuty MCP from templates/mcp.recommended.json)
  5. run /doctor to re-resolve bindings against the new roster
DONE
