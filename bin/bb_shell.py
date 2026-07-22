#!/usr/bin/env python3
"""bb-shell — the shell adapter (design §6.3, §3.1, §11 D-2, D-9).

Four verbs, one config-selected backend, and a fail-soft rule::

    bb-shell open-pane <url|command> [--workspace <session-id>]
    bb-shell navigate-pane <pane> <url>
    bb-shell notify <message> [--level <info|warn|approval>]
    bb-shell close-workspace <session-id>

Three implementations sit behind one dispatcher:

* ``DegradedBackend`` — prints a link or message for every verb. The default,
  the non-Mac path (R-1), and the universal fallback. Fully functional
  (FR-003, FR-026); never an error state.
* ``CmuxBackend`` — speaks cmux's socket API (``cmux-socket`` v2: newline-
  delimited JSON over AF_UNIX). See ``bb-shell.cmux.md``.
* the fail-soft wrapper — any backend failure (socket absent, refused, timed
  out, died mid-write, error response, malformed reply) becomes the degraded
  output, with a diagnostic note on stderr and exit success (FR-005, §9's R-2
  row). A shell failure must never brick a session.

The one loud path is a **usage error** (unknown verb, malformed arguments):
those are caller bugs, not availability events, and exit 2.

The shim is a pure function of (arguments, config, socket behavior) ->
(exit code, output, protocol traffic): no persistent state, no backend-health
memory, no reads beyond config and its socket (FR-009). Repeated failures are
therefore independent, and recovery is automatic.

Python 3.9-compatible, stdlib only (Constitution Platform Constraints, D-1).
"""

import sys


def main(argv=None):
    """Entry point. Returns the process exit code."""
    if argv is None:
        argv = sys.argv[1:]
    sys.stderr.write("usage: bb-shell <open-pane|navigate-pane|notify|close-workspace> ...\n")
    return 2
