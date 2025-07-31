"""
Comprehensive Python import parsing and relationship testing.
Tests all possible Python import patterns and verifies IMPORTS relationships.
"""

import os
import sys
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from codebase_rag.graph_updater import GraphUpdater
from codebase_rag.parser_loader import load_parsers


@pytest.fixture
def python_imports_project(temp_repo: Path) -> Path:
    """Create a comprehensive Python project with all import patterns."""
    project_path = temp_repo / "python_imports_test"
    project_path.mkdir()

    # Create package structure
    (project_path / "package").mkdir()
    (project_path / "package" / "__init__.py").write_text("")
    (project_path / "package" / "subpackage").mkdir()
    (project_path / "package" / "subpackage" / "__init__.py").write_text("")
    (project_path / "package" / "subpackage" / "deep").mkdir()
    (project_path / "package" / "subpackage" / "deep" / "__init__.py").write_text("")

    # Module files for testing
    (project_path / "utils.py").write_text("def helper(): pass")
    (project_path / "models.py").write_text("class User: pass")
    (project_path / "package" / "module.py").write_text("def func(): pass")
    (project_path / "package" / "subpackage" / "nested.py").write_text(
        "class Nested: pass"
    )

    return project_path


def test_standard_library_imports(
    python_imports_project: Path,
    mock_ingestor: MagicMock,
) -> None:
    """Test standard library import parsing and relationship creation."""
    test_file = python_imports_project / "stdlib_imports.py"
    test_file.write_text(
        """
# Standard library imports - basic
import os
import sys
import json
import re

# Standard library imports - from imports
from pathlib import Path
from collections import defaultdict, Counter, deque
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Union, Any

# Standard library imports - with aliases
import sqlite3 as db
import urllib.parse as urlparse
from urllib.request import urlopen as fetch
from collections import defaultdict as ddict

# Standard library imports - nested modules
from email.mime.text import MIMEText
from xml.etree.ElementTree import Element
from http.server import HTTPServer
"""
    )

    parsers, queries = load_parsers()
    updater = GraphUpdater(
        ingestor=mock_ingestor,
        repo_path=python_imports_project,
        parsers=parsers,
        queries=queries,
    )
    updater.run()

    import_relationships = [
        c
        for c in cast(MagicMock, mock_ingestor.ensure_relationship_batch).call_args_list
        if c.args[1] == "IMPORTS"
    ]

    stdlib_imports = [
        call for call in import_relationships if "stdlib_imports" in call.args[0][2]
    ]

    # Should have multiple standard library imports
    assert len(stdlib_imports) >= 15, (
        f"Expected at least 15 stdlib imports, found {len(stdlib_imports)}"
    )

    # Verify specific imports exist
    imported_modules = [call.args[2][2] for call in stdlib_imports]
    expected_modules = [
        "os",
        "sys",
        "json",
        "re",
        "pathlib.Path",
        "collections.defaultdict",
        "datetime.datetime",
        "typing.List",
        "sqlite3",
        "urllib.parse",
        "email.mime.text.MIMEText",
        "xml.etree.ElementTree.Element",
    ]

    for expected in expected_modules:
        assert any(expected in module for module in imported_modules), (
            f"Missing stdlib import: {expected}\nFound: {imported_modules}"
        )


def test_relative_imports(
    python_imports_project: Path,
    mock_ingestor: MagicMock,
) -> None:
    """Test relative import parsing and relationship creation."""

    # Test file in root
    test_file = python_imports_project / "relative_imports.py"
    test_file.write_text(
        """
# Relative imports from current directory
from . import utils
from .models import User
from .package import module

# Cannot test parent relative imports from root level
"""
    )

    # Test file in package
    package_test = python_imports_project / "package" / "relative_test.py"
    package_test.write_text(
        """
# Same level relative imports
from . import module
from .subpackage import nested

# Parent relative imports
from .. import utils, models
from ..models import User

# Deep relative imports
from .subpackage.deep import something
"""
    )

    # Test file in nested package
    nested_test = python_imports_project / "package" / "subpackage" / "nested_test.py"
    nested_test.write_text(
        """
# Same level and parent imports
from . import nested
from .. import module
from ...utils import helper
from ...models import User
"""
    )

    parsers, queries = load_parsers()
    updater = GraphUpdater(
        ingestor=mock_ingestor,
        repo_path=python_imports_project,
        parsers=parsers,
        queries=queries,
    )
    updater.run()

    import_relationships = [
        c
        for c in cast(MagicMock, mock_ingestor.ensure_relationship_batch).call_args_list
        if c.args[1] == "IMPORTS"
    ]

    # Test relative imports from different levels
    relative_imports = [
        call
        for call in import_relationships
        if any(
            test_file in call.args[0][2]
            for test_file in ["relative_imports", "relative_test", "nested_test"]
        )
    ]

    assert len(relative_imports) >= 8, (
        f"Expected at least 8 relative imports, found {len(relative_imports)}"
    )

    # Check that relative imports are resolved correctly
    imported_modules = [call.args[2][2] for call in relative_imports]
    project_name = python_imports_project.name

    expected_patterns = [
        f"{project_name}.utils",
        f"{project_name}.models",
        f"{project_name}.package.module",
        f"{project_name}.package.subpackage.nested",
    ]

    for pattern in expected_patterns:
        assert any(pattern in module for module in imported_modules), (
            f"Missing relative import pattern: {pattern}\nFound: {imported_modules}"
        )


def test_complex_import_patterns(
    python_imports_project: Path,
    mock_ingestor: MagicMock,
) -> None:
    """Test complex import patterns including wildcards, conditionals, etc."""
    test_file = python_imports_project / "complex_imports.py"
    test_file.write_text(
        """
# Wildcard imports
from os import *
from typing import *
from package.module import *

# Multiple imports from same module
from collections import (
    defaultdict,
    Counter,
    OrderedDict,
    deque,
    namedtuple,
)

# Complex nested imports with aliases
from package.subpackage.nested import Class as NestedClass
from very.deep.nested.module import function as deep_fn

# Mixed import styles
from datetime import datetime, timezone
import json, pickle, csv

# Conditional imports
import sys
if sys.version_info >= (3, 8):
    from typing import TypedDict, Protocol
else:
    from typing_extensions import TypedDict, Protocol

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None
    HAS_NUMPY = False

# Dynamic imports in functions
def load_optional():
    try:
        from optional_package import feature
        return feature
    except ImportError:
        return None

# Imports inside classes
class DataProcessor:
    def __init__(self):
        from pandas import DataFrame
        self.df_class = DataFrame
"""
    )

    parsers, queries = load_parsers()
    updater = GraphUpdater(
        ingestor=mock_ingestor,
        repo_path=python_imports_project,
        parsers=parsers,
        queries=queries,
    )
    updater.run()

    import_relationships = [
        c
        for c in cast(MagicMock, mock_ingestor.ensure_relationship_batch).call_args_list
        if c.args[1] == "IMPORTS"
    ]

    complex_imports = [
        call for call in import_relationships if "complex_imports" in call.args[0][2]
    ]

    # Should have many complex imports
    assert len(complex_imports) >= 12, (
        f"Expected at least 12 complex imports, found {len(complex_imports)}"
    )

    imported_modules = [call.args[2][2] for call in complex_imports]

    # Test wildcard imports are captured (they're stored as *module patterns)
    wildcard_patterns = ["os", "typing"]
    for pattern in wildcard_patterns:
        # Wildcard imports should appear as target modules
        assert any(pattern in module for module in imported_modules), (
            f"Missing wildcard import target: {pattern}\nFound modules: {imported_modules}"
        )

    # Test multiple imports from same module
    collections_imports = [m for m in imported_modules if "collections" in m]
    assert len(collections_imports) >= 3, (
        f"Expected multiple collections imports, found: {collections_imports}"
    )

    # Test conditional imports
    conditional_imports = [m for m in imported_modules if "typing" in m or "numpy" in m]
    assert conditional_imports, (
        f"Expected conditional imports, found: {conditional_imports}"
    )


def test_third_party_framework_imports(
    python_imports_project: Path,
    mock_ingestor: MagicMock,
) -> None:
    """Test third-party framework import patterns."""
    test_file = python_imports_project / "framework_imports.py"
    test_file.write_text(
        """
# Flask imports
from flask import Flask, request, jsonify, abort, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required

# Django imports
from django.db import models
from django.contrib.auth.models import User
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import path, include

# Data science imports
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from matplotlib import pyplot as plt
import seaborn as sns

# Testing imports
import pytest
from unittest.mock import MagicMock, patch, Mock
from pytest import fixture, raises

# FastAPI imports
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field, validator

# SQLAlchemy imports
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session

# Marshmallow imports
from marshmallow import Schema, fields, validate, post_load, pre_dump
"""
    )

    parsers, queries = load_parsers()
    updater = GraphUpdater(
        ingestor=mock_ingestor,
        repo_path=python_imports_project,
        parsers=parsers,
        queries=queries,
    )
    updater.run()

    import_relationships = [
        c
        for c in cast(MagicMock, mock_ingestor.ensure_relationship_batch).call_args_list
        if c.args[1] == "IMPORTS"
    ]

    framework_imports = [
        call for call in import_relationships if "framework_imports" in call.args[0][2]
    ]

    # Should have many framework imports
    assert len(framework_imports) >= 25, (
        f"Expected at least 25 framework imports, found {len(framework_imports)}"
    )

    imported_modules = [call.args[2][2] for call in framework_imports]

    # Test specific framework categories
    framework_categories = {
        "flask": ["flask", "flask_sqlalchemy", "flask_migrate"],
        "django": ["django.db", "django.contrib", "django.http"],
        "data_science": ["pandas", "numpy", "sklearn", "matplotlib"],
        "testing": ["pytest", "unittest.mock"],
        "fastapi": ["fastapi", "pydantic"],
        "sqlalchemy": ["sqlalchemy"],
        "marshmallow": ["marshmallow"],
    }

    for category, expected_modules in framework_categories.items():
        category_imports = [
            m for m in imported_modules if any(exp in m for exp in expected_modules)
        ]
        assert category_imports, (
            f"Missing {category} imports, expected patterns: {expected_modules}"
        )


def test_import_aliases_and_renaming(
    python_imports_project: Path,
    mock_ingestor: MagicMock,
) -> None:
    """Test import aliases and renaming patterns."""
    test_file = python_imports_project / "alias_imports.py"
    test_file.write_text(
        """
# Simple aliases
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import tensorflow as tf

# From imports with aliases
from collections import defaultdict as ddict
from pathlib import Path as FilePath
from datetime import datetime as dt, timezone as tz
from typing import List as ListType, Dict as DictType

# Complex nested aliases
from package.subpackage.nested import Class as MyClass
from very.long.module.name import function as short_fn
from another.deep.package import (
    LongClassName as Short,
    another_long_function as fn,
    CONSTANT_VALUE as CONST,
)

# Multiple aliases from same module
from os import (
    path as ospath,
    environ as env,
    getcwd as pwd,
)

# Alias conflicts and resolution
from json import loads as json_loads
from pickle import loads as pickle_loads
from yaml import load as yaml_load
"""
    )

    parsers, queries = load_parsers()
    updater = GraphUpdater(
        ingestor=mock_ingestor,
        repo_path=python_imports_project,
        parsers=parsers,
        queries=queries,
    )
    updater.run()

    import_relationships = [
        c
        for c in cast(MagicMock, mock_ingestor.ensure_relationship_batch).call_args_list
        if c.args[1] == "IMPORTS"
    ]

    alias_imports = [
        call for call in import_relationships if "alias_imports" in call.args[0][2]
    ]

    # Should have many aliased imports
    assert len(alias_imports) >= 15, (
        f"Expected at least 15 aliased imports, found {len(alias_imports)}"
    )

    imported_modules = [call.args[2][2] for call in alias_imports]

    # Test that original module names are preserved in relationships
    expected_original_modules = [
        "numpy",
        "pandas",
        "matplotlib.pyplot",
        "tensorflow",
        "collections.defaultdict",
        "pathlib.Path",
        "datetime.datetime",
        "os.path",
        "os.environ",
        "os.getcwd",
        "json.loads",
        "pickle.loads",
    ]

    for expected in expected_original_modules:
        assert any(expected in module for module in imported_modules), (
            f"Missing aliased import: {expected}\nFound: {imported_modules}"
        )


def test_import_error_handling(
    python_imports_project: Path,
    mock_ingestor: MagicMock,
) -> None:
    """Test that import parsing handles syntax errors gracefully."""
    test_file = python_imports_project / "error_imports.py"
    test_file.write_text(
        """
# Valid imports
import os
from pathlib import Path

# Malformed imports (should not crash parser)
# import
# from import something
# import .relative

# Valid imports after errors
import json
from datetime import datetime

# Complex valid imports
from collections import (
    defaultdict,
    Counter,
)

# Edge cases
from . import  # incomplete relative import
import sys, json  # trailing comma handled gracefully
"""
    )

    parsers, queries = load_parsers()
    updater = GraphUpdater(
        ingestor=mock_ingestor,
        repo_path=python_imports_project,
        parsers=parsers,
        queries=queries,
    )

    # Should not raise an exception
    updater.run()

    import_relationships = [
        c
        for c in cast(MagicMock, mock_ingestor.ensure_relationship_batch).call_args_list
        if c.args[1] == "IMPORTS"
    ]

    error_file_imports = [
        call for call in import_relationships if "error_imports" in call.args[0][2]
    ]

    # Should still parse valid imports despite errors
    assert len(error_file_imports) >= 4, (
        f"Expected at least 4 valid imports despite errors, found {len(error_file_imports)}"
    )

    imported_modules = [call.args[2][2] for call in error_file_imports]
    expected_valid = ["os", "pathlib.Path", "json", "datetime.datetime"]

    for expected in expected_valid:
        assert any(expected in module for module in imported_modules), (
            f"Missing valid import after error: {expected}"
        )


def test_import_relationships_comprehensive(
    python_imports_project: Path,
    mock_ingestor: MagicMock,
) -> None:
    """Comprehensive test ensuring all import types create proper relationships."""
    # Create a master test file with all patterns
    test_file = python_imports_project / "comprehensive_imports.py"
    test_file.write_text(
        """
# Every Python import pattern in one file
import os, sys, json
from pathlib import Path
from collections import defaultdict as ddict, Counter
from . import utils
from ..parent import something
from typing import *
import sqlite3 as db
from datetime import (
    datetime,
    timezone as tz,
    timedelta,
)

# Framework imports
from flask import Flask, request
import pandas as pd
import numpy as np

# Conditional imports
try:
    from optional import feature
except ImportError:
    feature = None

if True:
    from conditional import module
"""
    )

    parsers, queries = load_parsers()
    updater = GraphUpdater(
        ingestor=mock_ingestor,
        repo_path=python_imports_project,
        parsers=parsers,
        queries=queries,
    )
    updater.run()

    # Verify all relationship types exist
    all_relationships = cast(
        MagicMock, mock_ingestor.ensure_relationship_batch
    ).call_args_list

    import_relationships = [c for c in all_relationships if c.args[1] == "IMPORTS"]
    defines_relationships = [c for c in all_relationships if c.args[1] == "DEFINES"]

    # Should have comprehensive import coverage
    comprehensive_imports = [
        call
        for call in import_relationships
        if "comprehensive_imports" in call.args[0][2]
    ]

    assert len(comprehensive_imports) >= 15, (
        f"Expected at least 15 comprehensive imports, found {len(comprehensive_imports)}"
    )

    # Verify relationship structure
    for relationship in comprehensive_imports:
        # Each relationship should have proper structure
        assert len(relationship.args) == 3, "Import relationship should have 3 args"
        assert relationship.args[1] == "IMPORTS", "Second arg should be 'IMPORTS'"

        source_module = relationship.args[0][2]
        target_module = relationship.args[2][2]

        # Source should be our test module
        assert "comprehensive_imports" in source_module, (
            f"Source module should contain test file name: {source_module}"
        )

        # Target should be a valid module name
        assert isinstance(target_module, str) and target_module, (
            f"Target module should be non-empty string: {target_module}"
        )

    # Test that import parsing doesn't interfere with other relationships
    assert defines_relationships, "Should still have DEFINES relationships"

    print("✅ Import relationship validation passed:")
    print(f"   - IMPORTS relationships: {len(import_relationships)}")
    print(f"   - DEFINES relationships: {len(defines_relationships)}")
    print(f"   - Comprehensive test imports: {len(comprehensive_imports)}")
