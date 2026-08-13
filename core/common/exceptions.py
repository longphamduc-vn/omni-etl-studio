class OmniETLException(Exception):
    """Base exception class for all errors in omni-etl-studio."""
    pass


class WorkflowValidationError(OmniETLException):
    """Raised when JSON workflow schemas or catalog definitions fail validation."""
    pass


class EvaluatorError(OmniETLException):
    """Raised when variable resolution or JsonPath extraction fails."""
    pass


class FilterError(OmniETLException):
    """Raised during pre-call record filtering execution."""
    pass


class TransformationError(OmniETLException):
    """Raised when data transformation operators (DuckDB or Python) fail."""
    pass


class DriverError(OmniETLException):
    """Raised during protocol payload construction, network transport, or parsing."""
    pass


class StorageError(OmniETLException):
    """Raised during DuckDB schema creation, table registration, or SQL execution."""
    pass