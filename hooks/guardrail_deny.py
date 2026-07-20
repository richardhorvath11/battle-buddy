#!/usr/bin/env python3
"""PreToolUse deny layer — guardrail layer 1 (design §3.5; Constitution III).

Deterministic pattern matching over tool-call command text; matched calls are
exit-blocked outright (exit 2, reason on stderr), beneath and independent of
approval gates. Everything else is allowed. The hook itself fails open: any
internal error allows the call with the failure visible in diagnostics —
safety must never brick a session at 3am (spec FR-004).

Matching model (spec US1 AS-2's corpus-membership rule, made mechanical):
- Only command-shaped input fields are scanned (``command``, ``script``,
  ``sql``, …) — prose/data fields (commit messages, excerpts) are never
  evaluated.
- Patterns match the *scrubbed* command, in which only genuinely inert data
  positions are masked (``_scrub``): URLs, message-flag values (``-m``…), and
  grep-family search patterns. Everything else — including quoted flags and
  quoted paths, which are still the executed action — is scanned raw and
  over-matches. Masking quotes syntactically was the old, wrong model; it let
  a quoted flag/path slip the gate.
- A data span carrying command substitution (``$(…)``, backticks, ``${…}``,
  process substitution ``<(…)``/``>(…)``) is never masked — that content
  executes wherever it appears.
Over-match beyond the benign corpus is acceptable collateral (Constitution
III); the corpus is the decided boundary and narrowing happens by growing it.

The four v1 deny classes live in DENY_CLASSES below — in code, not config, so
a user-broken config file can never silently disable the layer (research R3).
``credential_scan`` carries the one context rule: it fires only when an
``error:auth`` outcome appears in the protocol's 10-line trace window — or in
degraded pattern-only mode when no trace exists yet (spec Assumptions).

On every block this hook appends the call's own ``denied:guardrail:<class>``
trace line (protocol: one line per tool call, including blocked ones).

Python 3.9-compatible, stdlib only.
"""

import json
import os
import re
import sys

import _config
import _state

# Command-field extraction and the trace line's summary derivation live in
# _state (shared with tool_trace so denied lines from concurrent PreToolUse
# hooks carry the same tool-call identity — the protocol's dedup key).

# Scrubbing masks *data positions* — text the shell does not execute — so a
# dangerous pattern that appears only as data (US1 AS-2) doesn't match, while
# anything in an executed position stays raw and over-matches (Constitution
# III's posture). Masking quotes syntactically was the wrong model: it let a
# quoted flag or path (`git push "--force"`, `cat "~/.ssh/id_rsa"`) slip the
# gate. We mask three inert positions instead:
#   - URLs (never executed);
#   - the value of a message flag (`-m "…"` commit/tag text);
#   - the search pattern of a grep-family tool.
# A span carrying command/process substitution (`$(…)`, backticks, `${…}`,
# `<(…)`, `>(…)`) is *never* masked — that content executes regardless of
# position.
_URL = re.compile(r"\bhttps?://\S+")
# Command substitution / process substitution execute wherever they appear —
# a span carrying any of these is never treated as inert data.
_CMDSUB = re.compile(r"\$\(|`|\$\{|<\(|>\(")
# Message-flag value: keep the flag, mask the argument (quoted or a bare run).
# Only genuine message flags — NOT `-C`, which is a directory/ref operand in
# tar/make/git/scp/ssh (an executed position), so masking its value re-opened
# an under-match (`scp -C ~/.ssh/id_rsa …`, `tar -C ~/.ssh …`).
_MESSAGE_FLAG_VALUE = re.compile(
    r"(?P<flag>(?:^|(?<=\s))(?:-m|--message|--reason))(?P<sep>=|\s+)"
    r"(?P<val>'[^']*'|\"[^\"]*\"|\S+)"
)
# Grep-family search pattern: the quoted FIRST positional argument only —
# reachable across flag tokens (`-r`, `--include=…`) but NOT across a bare word.
# A bare word is the search pattern, which makes any following quoted token a
# FILE operand (an executed read), so `grep secret "~/.ssh/id_rsa"` must not
# mask the credential path.
_GREP_PATTERN = re.compile(
    r"(?P<head>\b(?:egrep|fgrep|grep|rg|ag|ack)\b(?:\s+-{1,2}\S+)*\s+)"
    r"(?P<pat>'[^']*'|\"[^\"]*\")"
)

_HOMES = r"(?:~|\$HOME|/home/[\w.-]+|/Users/[\w.-]+)"


def _c(*patterns):
    return tuple(re.compile(p, re.IGNORECASE) for p in patterns)


# (name, human description, compiled patterns). Order = evaluation order;
# first matching class names the block. Patterns change only alongside the
# two fixture corpora — the corpus is the regression gate (FR-005).
DENY_CLASSES = (
    (
        "destructive_filesystem",
        "destructive filesystem operation",
        _c(
            r"\brm\s+-\w*(?:r\w*f|f\w*r)\w*\b",
            r"\brm\s+[^|;&]*--recursive\b[^|;&]*--force\b",
            r"\brm\s+[^|;&]*--force\b[^|;&]*--recursive\b",
            r"\brm\s+[^|;&]*-\w*r\b[^|;&]*\s-\w*f\b",
            r"\brm\s+[^|;&]*-\w*f\b[^|;&]*\s-\w*r\b",
            r"\brm\s+-\w*r\w*\s+(?:/|~(?:\s|/\s*$|$)|\$HOME\b|\*)",
            r"\bmkfs(?:\.\w+)?\b",
            r"\bdd\b[^|;&]*\bof=/dev/",
            r"\bshred\b[^|;&]*/dev/",
            r">\s*/dev/(?:sd|nvme|disk)",
        ),
    ),
    (
        "destructive_infra",
        "destructive cluster/cloud operation",
        _c(
            r"\bkubectl\s+delete\b",
            r"\bterraform\s+(?:destroy|apply)\b",
            r"\baws\s+ec2\s+terminate-instances\b",
            r"\baws\s+rds\s+delete-",
            r"\baws\s+iam\s+(?:create|delete|put|attach|detach|update|add|remove)\w*-",
            r"\bgcloud\s+compute\s+instances\s+delete\b",
            r"\bgcloud\s+projects\s+delete\b",
            r"\baz\s+vm\s+delete\b",
            r"\bhelm\s+(?:uninstall|delete)\b",
            r"\bdrop\s+(?:table|database|schema)\b",
            r"\btruncate\s+table\b",
        ),
    ),
    (
        "credential_scan",
        "credential scanning after an auth error",
        _c(
            _HOMES + r"/\.aws\b",
            _HOMES + r"/\.ssh/",
            _HOMES + r"/\.netrc\b",
            r"/etc/shadow\b",
            r"\bsecurity\s+(?:dump-keychain|find-generic-password|find-internet-password)\b",
            r"\b(?:env|printenv)\b[^|;&]*\|[^|;&]*\bgrep\b.*(?:secret|token|api.?key|password|credential)",
        ),
    ),
    (
        "verify_skip",
        "verification-skipping retry",
        _c(
            r"\bgit\s+push\b[^|;&]*(?:--force(?!-with-lease)\b|\s-f\b)",
            r"--no-verify\b",
            r"--skip-hooks\b",
            r"\bcurl\b[^|;&]*(?:\s-k\b|--insecure\b)",
            r"\bwget\b[^|;&]*--no-check-certificate\b",
            r"sslVerify\s*=\s*false",
            r"NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*0",
            r"PYTHONHTTPSVERIFY\s*=\s*0",
        ),
    ),
)

BLOCK_MESSAGE = (
    "battle-buddy guardrail blocked this call — %s (pattern class: %s). "
    "This deterministic deny layer blocks the matched class outright, with no "
    "inline bypass; choose a safe alternative or hand the action to the "
    "responder."
)


def _mask_inert(match, placeholder, group="val"):
    """Replace a data span with a placeholder — unless it carries command
    substitution, which executes wherever it appears and so stays raw."""
    span = match.group(group)
    if _CMDSUB.search(span):
        return match.group(0)
    return match.group(0)[: match.start(group) - match.start(0)] + placeholder


def _scrub(text):
    """Mask inert data positions so patterns match only executed content."""
    text = _URL.sub(
        lambda m: m.group(0) if _CMDSUB.search(m.group(0)) else "<url>", text
    )
    text = _MESSAGE_FLAG_VALUE.sub(lambda m: _mask_inert(m, "<msg>"), text)
    text = _GREP_PATTERN.sub(lambda m: _mask_inert(m, "<pat>", group="pat"), text)
    return text


def _auth_error_in_window(root):
    """True: auth error in the 10-line window. False: window present, clean,
    and fully parseable. None: no trace, unreadable, or any torn line in the
    window — the context is uncertain, so callers block conservatively rather
    than trust a window a corrupt line may have hidden the auth error from."""
    lines, trustworthy = _state.tail_trace_status(root)
    if not trustworthy or not lines:
        # No usable context: absent, unreadable, torn, or an empty trace all
        # mean "cannot clear this read" → conservative degraded block, uniformly.
        return None
    return any(
        line.get("outcome") == _state.OUTCOME_ERROR_AUTH for line in lines
    )


def _evaluate(payload):
    """Return (class_name, message) for a block, or None to allow."""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    texts = _state.command_texts(tool_input)
    if not texts:
        return None

    root = payload.get("cwd")
    if not isinstance(root, str) or not root:
        root = os.getcwd()

    scrubbed = [_scrub(text) for text in texts]
    for name, description, patterns in DENY_CLASSES:
        matched = any(
            pattern.search(text) for text in scrubbed for pattern in patterns
        )
        if not matched:
            continue
        if name == "credential_scan":
            # Context rule: block on an auth error in the recent-trace window,
            # or conservatively in pattern-only mode when no trace context is
            # available. Allow only when the window is present AND clean.
            context = _auth_error_in_window(root)
            if context is False:
                continue
            if context is None:
                # No auth context to cite — say so, rather than asserting an
                # auth error we cannot see (honest degraded-mode message).
                return name, BLOCK_MESSAGE % (
                    "credential-path read with no trace context to clear it",
                    name,
                )
        return name, BLOCK_MESSAGE % (description, name)
    return None


def _append_denied_line(payload, class_name):
    """Append the block's own trace line. Returns config notices (if any) so
    the caller can surface them in diagnostics (fail-open visibility)."""
    root = payload.get("cwd")
    if not isinstance(root, str) or not root:
        root = os.getcwd()
    tool = payload.get("tool_name", "")
    line = {
        "agent": _state.actor_key(payload.get("transcript_path", "")),
        "tool": tool,
        "summary": _state.summarize_tool_input(payload.get("tool_input")),
        "outcome": _state.OUTCOME_DENIED_GUARDRAIL_PREFIX + class_name,
    }
    # The runtime's tool-call id, when provided, is the protocol's exact
    # double-deny dedup key (both denying hooks stamp the same id).
    call_id = payload.get("tool_use_id")
    if isinstance(call_id, str) and call_id:
        line["call_id"] = call_id
    # capability rides the line from the binding map when present (protocol
    # doc; multi-capability tools serialize as a sorted comma-joined value).
    # The audit line must not be hostage to config health, so a config blow-up
    # degrades to an omitted capability + a notice, never a lost line.
    notices = []
    try:
        cfg = _config.load_config(root)
        capabilities = cfg.capabilities_for(tool)
        if capabilities:
            line["capability"] = ",".join(sorted(capabilities))
        notices = cfg.notices
    except Exception as exc:
        notices = ["capability lookup skipped (%s)" % exc]
    _state.append_trace(root, line)
    return notices


def run(stdin_text):
    """Pure entry point: stdin text -> (exit_code, stdout, stderr).

    Exit 0 allows; exit 2 blocks with the reason on stderr. Every failure
    path inside the hook allows (fail open) with a visible diagnostic.
    """
    try:
        payload = json.loads(stdin_text)
        if not isinstance(payload, dict):
            raise ValueError("hook payload is not a JSON object")
    except (ValueError, RecursionError) as exc:
        # RecursionError: a pathologically nested payload must fail open like
        # any other unreadable one, not escape run() as a traceback.
        return 0, "", "guardrail_deny fail-open: unreadable payload (%s)\n" % exc

    try:
        verdict = _evaluate(payload)
    except Exception as exc:  # any internal error must not block the session
        return 0, "", "guardrail_deny fail-open: internal error (%s)\n" % exc

    if verdict is None:
        return 0, "", ""

    class_name, message = verdict
    diagnostics = ""
    try:
        notices = _append_denied_line(payload, class_name)
        for notice in notices:
            diagnostics += "guardrail_deny config notice: %s\n" % notice
    except Exception as exc:
        # Bookkeeping failure never downgrades a deny — but stays visible.
        diagnostics = "guardrail_deny: denied-line append failed (%s)\n" % exc
    return 2, "", message + "\n" + diagnostics


def main():
    try:
        stdin_text = sys.stdin.read()
    except Exception as exc:
        sys.stderr.write("guardrail_deny fail-open: stdin unreadable (%s)\n" % exc)
        sys.exit(0)
    exit_code, stdout, stderr = run(stdin_text)
    try:
        if stdout:
            sys.stdout.write(stdout)
        if stderr:
            sys.stderr.write(stderr)
    except OSError:
        pass  # broken pipe on a dying runtime — keep the intended exit code
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
