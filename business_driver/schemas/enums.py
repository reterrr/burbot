from enum import StrEnum


class BusinessEntityFieldDataType(StrEnum):
    TEXT = "TEXT"
    URL = "URL"
    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    MONEY = "MONEY"
    PERCENTAGE = "PERCENTAGE"
    DATE = "DATE"
    DATETIME = "DATETIME"
    BOOLEAN = "BOOLEAN"


class BusinessEntityFieldCardinality(StrEnum):
    ONE = "ONE"
    MANY = "MANY"


class ConfirmedBy(StrEnum):
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"
