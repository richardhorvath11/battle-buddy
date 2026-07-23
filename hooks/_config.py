"""Read-only workspace-config view shared by every hook (research R6).

Not a hook: the underscore marks a module shipped beside its consumers.
Reads exactly one source — ``<root>/.claude/settings.json`` → ``battleBuddy``
block — per the local-state protocol's config table. Malformed anything is
treated as absent (fail open) with a human-readable notice the caller surfaces
in diagnostics; this module never raises on bad config and never writes.

Python 3.9-compatible, stdlib only (Constitution Platform Constraints).
"""

import json
import os

DEFAULT_TRIAGE_TURN_CAP = 15
SETTINGS_RELPATH = os.path.join(".claude", "settings.json")


class ConfigView(object):
    """Immutable snapshot of the battleBuddy config block for one invocation.

    - ``turn_cap``: int, ``budgets.triageTurnCap`` (default 15 when absent/invalid)
    - ``bindings``: dict ``capability.operation -> tool name``, or None when the
      map is absent/malformed (tripwire disabled, ``capability`` omitted)
    - ``config_present``: the ``battleBuddy`` block exists (FR-015 feed)
    - ``settings_error``: the settings file exists but could not be read —
      distinct from a missing block, so a user-facing warning can name the
      real cause instead of prescribing the wrong remedy
    - ``notices``: diagnostics accumulated while reading (fail-open visibility)
    """

    def __init__(self, turn_cap, bindings, config_present, notices,
                 settings_error=False):
        self.turn_cap = turn_cap
        self.bindings = bindings
        self.config_present = config_present
        self.notices = list(notices)
        self.settings_error = settings_error

    def capabilities_for(self, tool):
        """Reverse lookup: capabilities whose bound tool equals ``tool``.

        The capability is the key's prefix before the first ``.``; a tool
        serving operations of several capabilities classifies as the set of
        matching capabilities (protocol doc rule). Empty set when bindings are
        absent or the tool is unbound.
        """
        if not self.bindings or not tool:
            return set()
        capabilities = set()
        for key, bound_tool in self.bindings.items():
            if bound_tool == tool:
                capabilities.add(key.split(".", 1)[0])
        return capabilities


def load_config(root):
    """Build a ConfigView from ``<root>/.claude/settings.json``. Never raises."""
    notices = []
    raw, settings_error = _read_settings(root, notices)
    block = raw.get("battleBuddy") if isinstance(raw, dict) else None
    config_present = isinstance(block, dict)
    if block is not None and not config_present:
        notices.append("battleBuddy config block is not an object; treated as absent")
        block = None
    if block is None:
        block = {}

    turn_cap = _read_turn_cap(block, notices)
    bindings = _read_bindings(block, notices)
    return ConfigView(turn_cap, bindings, config_present, notices,
                      settings_error)


def _read_settings(root, notices):
    """Return (parsed settings, settings_error)."""
    path = os.path.join(str(root), SETTINGS_RELPATH)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), False
    except FileNotFoundError:
        return {}, False
    except (OSError, ValueError) as exc:
        notices.append("workspace config unreadable (%s); treated as absent" % exc)
        return {}, True


def _read_turn_cap(block, notices):
    budgets = block.get("budgets")
    if budgets is None:
        return DEFAULT_TRIAGE_TURN_CAP
    if not isinstance(budgets, dict):
        notices.append("budgets is not an object; default turn cap applies")
        return DEFAULT_TRIAGE_TURN_CAP
    cap = budgets.get("triageTurnCap")
    if cap is None:
        return DEFAULT_TRIAGE_TURN_CAP
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 0:
        notices.append(
            "budgets.triageTurnCap %r is not a non-negative int; default applies" % (cap,)
        )
        return DEFAULT_TRIAGE_TURN_CAP
    return cap


def _read_bindings(block, notices):
    bindings = block.get("bindings")
    if bindings is None:
        return None
    if not isinstance(bindings, dict):
        notices.append("bindings is not an object; tripwire disabled")
        return None
    valid = {}
    for key, value in bindings.items():
        if not isinstance(key, str) or "." not in key or not isinstance(value, str):
            notices.append("binding entry %r ignored (want 'capability.operation' -> tool name)" % (key,))
            continue
        valid[key] = value
    return valid
