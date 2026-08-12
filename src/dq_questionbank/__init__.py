"""Database-neutral tools for structured educational questions."""

from .exceptions import (
    FormatDetectionError,
    FormatError,
    FormatLoadError,
    FormatWriteError,
    QuestionBankError,
    SchemaError,
    SchemaNotFoundError,
    SchemaValidationError,
    SchemaVersionError,
)
from .migration import list_migrations, migrate, register_migration
from .models import (
    Answer,
    Asset,
    Choice,
    Content,
    ContentBlock,
    Question,
    QuestionSet,
    SourceMetadata,
    TaxonomyRef,
)
from .schema import load_schema, schema_path
from .validation import ValidationIssue, validate_question, validate_question_set, validate_with_schema

__all__ = [
    "FormatDetectionError",
    "FormatError",
    "FormatLoadError",
    "FormatWriteError",
    "QuestionBankError",
    "SchemaError",
    "SchemaNotFoundError",
    "SchemaValidationError",
    "SchemaVersionError",
    "Answer",
    "Asset",
    "Choice",
    "Content",
    "ContentBlock",
    "Question",
    "QuestionSet",
    "SourceMetadata",
    "TaxonomyRef",
    "ValidationIssue",
    "list_migrations",
    "load_schema",
    "migrate",
    "register_migration",
    "schema_path",
    "validate_question",
    "validate_question_set",
    "validate_with_schema",
]

__version__ = "0.1.0"
__version__ = "0.2.0"
