#!/usr/bin/env python3
"""bb-fingerprint — the one shared fingerprint implementation (design §5.2, D-4).

    fingerprint = hex(sha256(normalize(service) + "|" + normalize(alert_type)))[:16]

Normalization rules, version ``bb.fp.v1`` (the golden corpus at
tests/fixtures/fingerprint/golden.json is their executable form; any
behavioral change REQUIRES a version bump and a re-fingerprint pass — silent
drift breaks exact-match recall, the retrieval path the tier-0 memory
flywheel rides on):

1. Both inputs: lowercase, trim, collapse internal whitespace to single spaces.
2. ``alert_type`` only, in this order (earlier rules win):
   UUIDs → ``<id>``; ISO timestamps (date-time or bare date) → ``<ts>``;
   IPv4 addresses → ``<host>``; dotted hostnames (≥3 labels) → ``<host>``;
   hex strings ≥8 chars containing ≥1 letter → ``<id>``;
   integers ≥3 digits → ``<n>``.
3. ``service`` is the catalog ``metadata.name`` — already canonical; only
   rule 1 applies (digits in service names are identity, never volatile).

Empty or all-volatile inputs yield deterministic outputs with flags — never
an exception — so callers can apply the §5.2 resolution ladder.

Python 3.9-compatible, stdlib only.
"""

import hashlib
import json
import re
import sys

VERSION = "bb.fp.v1"
FINGERPRINT_LENGTH = 16

# Applied to the already lowercased/collapsed alert_type, in order.
VOLATILE_RULES = (
    ("uuid", re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
    ), "<id>"),
    ("iso_timestamp", re.compile(
        r"\b\d{4}-\d{2}-\d{2}"
        r"(?:[t ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:z|[+-]\d{2}:?\d{2})?)?\b"
    ), "<ts>"),
    ("ipv4", re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "<host>"),
    ("hostname", re.compile(
        r"\b[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
        r"(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?){2,}\b"
    ), "<host>"),
    ("hex_id", re.compile(
        r"\b(?=[0-9a-f]{8,}\b)(?=[0-9]*[a-f])[0-9a-f]+\b"
    ), "<id>"),
    ("integer", re.compile(r"\b\d{3,}\b"), "<n>"),
)

PLACEHOLDERS = ("<id>", "<ts>", "<host>", "<n>")

_WHITESPACE = re.compile(r"\s+")


def _basic_normalize(text):
    return _WHITESPACE.sub(" ", str(text).strip()).lower()


def normalize_service(service):
    """Rule 1 only — the service name is already canonical (catalog name)."""
    return _basic_normalize(service)


def normalize_alert_type(alert_type):
    """Rules 1 + 2: volatile tokens collapse so repeat alerts fingerprint
    identically while distinct alert shapes stay distinct."""
    text = _basic_normalize(alert_type)
    for _name, pattern, placeholder in VOLATILE_RULES:
        text = pattern.sub(placeholder, text)
    return text


def _flags(service_normalized, alert_normalized):
    flags = []
    if not service_normalized:
        flags.append("empty_service")
    if not alert_normalized:
        flags.append("empty_alert_type")
    elif all(token in PLACEHOLDERS for token in alert_normalized.split(" ")):
        flags.append("all_volatile_alert_type")
    return flags


def fingerprint(service, alert_type):
    """Deterministic fingerprint record: identical inputs give identical
    16-hex-char outputs on every supported platform and Python version."""
    service_normalized = normalize_service(service)
    alert_normalized = normalize_alert_type(alert_type)
    digest = hashlib.sha256(
        (service_normalized + "|" + alert_normalized).encode("utf-8")
    ).hexdigest()
    return {
        "version": VERSION,
        "fingerprint": digest[:FINGERPRINT_LENGTH],
        "service_normalized": service_normalized,
        "alert_type_normalized": alert_normalized,
        "flags": _flags(service_normalized, alert_normalized),
    }


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        sys.stderr.write("usage: bb-fingerprint SERVICE ALERT_TYPE\n")
        return 2
    sys.stdout.write(json.dumps(fingerprint(argv[0], argv[1]), sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
