"""Uniform error envelope for bb-mock-mcp (contracts/operations.md).

Every rejected call surfaces as ``{"error": {"op", "code", "message"}}`` with
``message`` naming the violated expectation (spec FR-004). ``limit_exceeded``
is part of the closed code set but unassigned by v1 required ops — the
operations.md error tables put oversized-field rejections under
``invalid_input``.
"""

ERROR_CODES = ("invalid_input", "not_found", "limit_exceeded", "unknown_op")


class SeedError(ValueError):
    """A seed fixture failed validation. The message names the offending
    entry (spec Story 3 AS-2); loading is all-or-nothing, so nothing was
    applied."""


class ContractViolation(Exception):
    """Raised by stores and the facade's shape validation.

    The facade catches it and converts it to the uniform envelope, attaching
    the ``capability.op`` reference — raise sites only supply code + message.
    """

    def __init__(self, code, message):
        if code not in ERROR_CODES:
            raise ValueError("unknown error code: {!r}".format(code))
        super().__init__("[{}] {}".format(code, message))
        self.code = code
        self.message = message

    def envelope(self, op_ref):
        return {"error": {"op": op_ref, "code": self.code, "message": self.message}}
