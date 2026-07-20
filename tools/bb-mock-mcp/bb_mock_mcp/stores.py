"""In-memory stores per data-model.md. All state is per-instance; the only
ordered state is insertion order and the write log's ``seq``.

Semantic validation (required record keys, size limits, existence) lives here;
generic contract-shape validation (required payload fields, types) happens in
the facade before dispatch. Read ops return copies so tests mutating results
never corrupt store state — direct inspection uses the public attributes
(``records``, ``files``, ``entries``, ``alerts``/``history``).
"""

from datetime import datetime, timedelta, timezone

from .errors import ContractViolation


class MockRecordStore:
    """Ordered list of session-record field maps (contract: storage)."""

    def __init__(self, single_field_limit):
        self.records = []
        self._limit = single_field_limit

    def _check_field_sizes(self, fields):
        for key, value in fields.items():
            if isinstance(value, str) and len(value) > self._limit:
                raise ContractViolation(
                    "invalid_input",
                    "field '{}' is {} chars — exceeds the {}-char D-3 single-field "
                    "limit (design §5.4; callers divert overflow to an artifact "
                    "pointer)".format(key, len(value), self._limit),
                )

    def append_record(self, record):
        if not isinstance(record, dict):
            raise ContractViolation("invalid_input", "record must be a field map")
        session_id = record.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise ContractViolation(
                "invalid_input", "record.session_id must be a non-empty string"
            )
        self._check_field_sizes(record)
        self.records.append(dict(record))
        return {"session_id": session_id}

    def read_records(self, filter=None):
        if filter is not None and not isinstance(filter, dict):
            raise ContractViolation(
                "invalid_input", "filter must be a field-equality map"
            )
        filter = filter or {}
        matches = [
            dict(r)
            for r in self.records
            if all(r.get(k) == v for k, v in filter.items())
        ]
        return {"records": matches}

    def update_record(self, session_id, fields):
        if not isinstance(fields, dict) or not fields:
            raise ContractViolation(
                "invalid_input", "fields must be a non-empty partial field map"
            )
        self._check_field_sizes(fields)
        for record in self.records:
            if record.get("session_id") == session_id:
                record.update(fields)
                return {"session_id": session_id}
        raise ContractViolation(
            "not_found", "no record with session_id '{}'".format(session_id)
        )


class MockArtifactStore:
    """Map link -> {name, content}; links are 'art://' + monotonic counter —
    stable, opaque, deterministic across identical runs."""

    def __init__(self):
        self.files = {}
        self._counter = 0

    def put_file(self, name, content):
        if not isinstance(name, str) or not name:
            raise ContractViolation("invalid_input", "name must be a non-empty string")
        if not isinstance(content, str):
            raise ContractViolation("invalid_input", "content must be a string")
        self._counter += 1
        link = "art://{}".format(self._counter)
        self.files[link] = {"name": name, "content": content}
        return {"link": link}

    def get_file(self, link):
        if link not in self.files:
            raise ContractViolation(
                "not_found", "no artifact stored at link '{}'".format(link)
            )
        return dict(self.files[link])


class MockDiary:
    """Ordered entry list with an injected logical clock — no wall clock, so
    timestamps are deterministic (data-model.md)."""

    _EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __init__(self):
        self.entries = []
        self._clock = 0

    def append_entry(self, content):
        if not isinstance(content, str) or not content:
            raise ContractViolation(
                "invalid_input", "content must be a non-empty string"
            )
        self._clock += 1
        entry = {
            "link": "diary://{}".format(self._clock),
            "content": content,
            "at": (self._EPOCH + timedelta(seconds=self._clock)).isoformat(),
        }
        self.entries.append(entry)
        return {"link": entry["link"]}

    def read_recent(self, n):
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            raise ContractViolation("invalid_input", "n must be an integer >= 1")
        return {"entries": [dict(e) for e in reversed(self.entries[-n:])]}


class MockAlerting:
    """Seed-only (no mutating contract ops). ``alerts``: alert_id -> field map;
    ``history``: ordered oldest-to-newest, listed newest first."""

    REQUIRED_ALERT_FIELDS = ("alert_id", "service_hint", "description", "fired_at")

    def __init__(self):
        self.alerts = {}
        self.history = []

    def get_alert(self, alert_id):
        if alert_id not in self.alerts:
            raise ContractViolation(
                "not_found", "no alert with alert_id '{}'".format(alert_id)
            )
        return {"alert": dict(self.alerts[alert_id])}

    def list_alert_history(self, filter):
        if not isinstance(filter, dict):
            raise ContractViolation(
                "invalid_input", "filter must be a field-equality map"
            )
        matches = [
            dict(a)
            for a in reversed(self.history)
            if all(a.get(k) == v for k, v in filter.items())
        ]
        return {"alerts": matches}


class WriteLog:
    """Ordered {seq, capability, op, summary} for every mutating contract op;
    seed loading bypasses it (seeds are precondition state, not scenario
    writes)."""

    def __init__(self):
        self.entries = []

    def append(self, capability, op, summary):
        self.entries.append(
            {
                "seq": len(self.entries) + 1,
                "capability": capability,
                "op": op,
                "summary": summary,
            }
        )
