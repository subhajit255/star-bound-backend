import pytest
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import BigInteger
from sqlalchemy.dialects.mysql import LONGTEXT, DECIMAL


@compiles(BigInteger, "sqlite")
def compile_big_int_sqlite(type_, compiler, **kw):
    """Maps BigInteger to SQLite INTEGER so auto-increment primary keys work seamlessly in test runs."""
    return "INTEGER"


@compiles(LONGTEXT, "sqlite")
def compile_longtext_sqlite(type_, compiler, **kw):
    """Maps MySQL LONGTEXT to SQLite TEXT in test runs."""
    return "TEXT"


@compiles(DECIMAL, "sqlite")
def compile_decimal_sqlite(type_, compiler, **kw):
    """Maps MySQL DECIMAL to SQLite NUMERIC in test runs."""
    return "NUMERIC"
