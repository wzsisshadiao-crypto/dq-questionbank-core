"""Predictable, catchable exception hierarchy for DQ QuestionBank Core."""

from __future__ import annotations


class QuestionBankError(Exception):
    """Base for every library-raised error."""

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class FormatError(QuestionBankError):
    """Raised when format detection, loading, or writing fails."""


class FormatDetectionError(FormatError):
    """No importer matches the input file extension or format name."""


class FormatLoadError(FormatError):
    """An importer failed while reading a file."""


class FormatWriteError(FormatError):
    """An exporter failed while writing a file."""


class SchemaError(QuestionBankError):
    """Schema-related: missing file, unsupported version, or structural mismatch."""


class SchemaNotFoundError(SchemaError):
    """The installed JSON Schema file is missing."""


class SchemaValidationError(SchemaError):
    """A document fails structural validation."""


class SchemaVersionError(SchemaError):
    """The document's schema_version is not supported by this library."""


class PluginDiscoveryError(QuestionBankError):
    """An installed plugin could not be selected, loaded, or registered."""


class ImportBundleError(QuestionBankError):
    """An import bundle or candidate-session transition failed closed."""


class StaleFindingError(QuestionBankError):
    """A quality finding was applied against content it no longer matches."""
