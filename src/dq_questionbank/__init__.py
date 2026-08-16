"""Database-neutral tools for structured educational questions."""

from .exceptions import (
    FormatDetectionError,
    FormatError,
    FormatLoadError,
    FormatWriteError,
    PluginDiscoveryError,
    QuestionBankError,
    SchemaError,
    SchemaNotFoundError,
    SchemaValidationError,
    SchemaVersionError,
)
from .interfaces import AIProvider, QuestionExporter, QuestionImporter, StorageAdapter
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
from .plugins import PLUGIN_ENTRY_POINT_GROUP, available_plugins, discover_plugins
from .registry import FormatRegistry, default_registry
from .schema import load_schema, schema_path
from .storage import FilesystemStorageAdapter
from .validation import (
    ValidationIssue,
    validate_question,
    validate_question_set,
    validate_with_schema,
)

__all__ = [
    "FormatDetectionError",
    "FormatError",
    "FormatLoadError",
    "FormatWriteError",
    "PluginDiscoveryError",
    "QuestionBankError",
    "FormatRegistry",
    "FilesystemStorageAdapter",
    "PLUGIN_ENTRY_POINT_GROUP",
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
    "QuestionExporter",
    "QuestionImporter",
    "SourceMetadata",
    "StorageAdapter",
    "TaxonomyRef",
    "AIProvider",
    "ValidationIssue",
    "list_migrations",
    "load_schema",
    "available_plugins",
    "default_registry",
    "discover_plugins",
    "migrate",
    "register_migration",
    "schema_path",
    "validate_question",
    "validate_question_set",
    "validate_with_schema",
]

__version__ = "0.2.1"
