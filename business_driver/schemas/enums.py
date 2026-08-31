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


class BusinessDefinitionStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"


class BusinessRelationCardinality(StrEnum):
    ONE_TO_ONE = "ONE_TO_ONE"
    ONE_TO_MANY = "ONE_TO_MANY"
    MANY_TO_ONE = "MANY_TO_ONE"
    MANY_TO_MANY = "MANY_TO_MANY"
