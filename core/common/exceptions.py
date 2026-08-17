# ==============================================================================
# Filepath: core/common/exceptions.py
# Updated_at: 2026-08-16 17:25:00
# Description: Custom exception hierarchy.
# ==============================================================================


class PipelineError(Exception):
    """Base exception class for all pipeline errors."""

    pass


class BusinessError(PipelineError):
    """Exception raised for business-level API errors (errcode = -1)."""

    def __init__(self, code: int, msg: str, payload: dict = None):
        self.code = code
        self.msg = msg
        self.payload = payload or {}
        super().__init__(f"Business error [{code}]: {msg}")


class RetryError(PipelineError):
    """Exception raised when maximum retry attempts are exhausted."""

    pass


class EvaluatorError(PipelineError):
    """Exception raised during variable or JSONPath resolution."""

    pass


class DriverError(PipelineError):
    """Exception raised for protocol invocation errors."""

    pass