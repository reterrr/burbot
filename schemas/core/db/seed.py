from db import TokenClass
from services.extraction.bs4_html_iter import TokenClassType

token_classes: dict[TokenClassType, TokenClass] = {
    TokenClassType.PERCENTAGE: TokenClass(
        name=TokenClassType.PERCENTAGE,
        regex=r"^[+-]?\d+(?:[.,]\d+)?%$",
    ),

    TokenClassType.INTEGER: TokenClass(
        name=TokenClassType.INTEGER,
        regex=r"^[+-]?\d+$",
    ),

    TokenClassType.DECIMAL: TokenClass(
        name=TokenClassType.DECIMAL,
        regex=r"^[+-]?\d+[.,]\d+$",
    ),

    TokenClassType.YEAR: TokenClass(
        name=TokenClassType.YEAR,
        regex=r"^(?:19|20)\d{2}$",
    ),

    TokenClassType.DATE: TokenClass(
        name=TokenClassType.DATE,
        regex=(
            r"^(?:"
            r"\d{4}-\d{2}-\d{2}"
            r"|"
            r"\d{2}[./-]\d{2}[./-]\d{4}"
            r")$"
        ),
    ),

    TokenClassType.TIME: TokenClass(
        name=TokenClassType.TIME,
        regex=r"^(?:[01]?\d|2[0-3]):[0-5]\d$",
    ),

    TokenClassType.CURRENCY: TokenClass(
        name=TokenClassType.CURRENCY,
        regex=r"^(?:zł|pln|eur|usd|€|\$)$",
    ),

    TokenClassType.EMAIL: TokenClass(
        name=TokenClassType.EMAIL,
        regex=r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$",
    ),

    TokenClassType.URL: TokenClass(
        name=TokenClassType.URL,
        regex=r"^(?:https?://|www\.)\S+$",
    ),

    TokenClassType.PHONE: TokenClass(
        name=TokenClassType.PHONE,
        regex=r"^\+?\d{7,15}$",
    ),

    TokenClassType.POSTAL_CODE: TokenClass(
        name=TokenClassType.POSTAL_CODE,
        regex=r"^\d{2}-\d{3}$",
    ),

    TokenClassType.BOOLEAN: TokenClass(
        name=TokenClassType.BOOLEAN,
        regex=r"^(?:true|false|yes|no|tak|nie)$",
    ),

    TokenClassType.IDENTIFIER: TokenClass(
        name=TokenClassType.IDENTIFIER,
        regex=r"^[A-Za-z0-9]+(?:[-_/][A-Za-z0-9]+)+$",
    ),

    TokenClassType.WORD: TokenClass(
        name=TokenClassType.WORD,
        regex=r"^[^\W\d_]+$",
    ),
}
