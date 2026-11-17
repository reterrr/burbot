"""Restricted Python-syntax parser. Never calls eval/exec or instantiates user classes."""

import ast
import base64
import hashlib
import io
import keyword
import math
import re
import tokenize
from copy import deepcopy
from typing import Any

from pydantic import Field, ValidationError

from business_layer.services.schema_language import LanguageModel, Sema, SourceLocation
from business_layer.services.validation import validate_value

BUILTINS = {
    "String": "string",
    "Text": "text",
    "Integer": "integer",
    "BigInteger": "biginteger",
    "Float": "float",
    "Decimal": "decimal",
    "Boolean": "boolean",
    "Date": "date",
    "DateTime": "datetime",
    "UUID": "uuid",
    "JSON": "json",
    "Source": "source",
    "Reference": "reference",
}
OPTIONS = {
    "persistent_key",
    "nullable",
    "unique",
    "index",
    "primary_key",
    "default",
    "min_length",
    "max_length",
    "pattern",
    "gt",
    "ge",
    "lt",
    "le",
    "precision",
    "scale",
}


class SeedObject(LanguageModel):
    name: str
    entity: str
    values: dict[str, Any]
    location: SourceLocation


class Program(LanguageModel):
    schema: Sema.Schema
    objects: list[SeedObject] = Field(default_factory=list, max_length=1000)
    seed_order: list[str] = Field(default_factory=list)


def table_name(name: str, namespace: str = ""):
    digest = hashlib.sha256(f"{namespace}\0{name}".encode()).digest()
    return "e_" + base64.b32encode(digest).decode().lower().rstrip("=")


class Parser:
    def __init__(self, code, *, namespace="", table_names=None, context_schema=None):
        if not isinstance(code, str) or len(code) > 100_000:
            raise Sema.SemaException(
                "Source must be text of at most 100000 characters",
                SourceLocation(1, 1, 1, 1),
                code="SYNTAX_ERROR",
            )
        self.code, self.lines = code, code.splitlines()
        self.namespace, self.table_names = namespace, table_names or {}
        self.context_schema = context_schema
        self.enums, self.entities, self.seed_nodes = {}, {}, {}

    def location(self, node):
        def column(line, byte):
            source = self.lines[line - 1] if line <= len(self.lines) else ""
            return len(source.encode()[:byte].decode("utf-8", errors="ignore")) + 1

        return SourceLocation(
            node.lineno,
            column(node.lineno, node.col_offset),
            node.end_lineno,
            column(node.end_lineno, node.end_col_offset),
        )

    def fail(self, message, node, code="SYNTAX_ERROR"):
        raise Sema.SemaException(message, self.location(node), code=code)

    def parse(self):
        for line_number, line in enumerate(self.lines, 1):
            prefix = re.match(r"[ \t]*", line).group()
            if "\t" in prefix:
                column = prefix.index("\t") + 1
                raise Sema.SemaException(
                    "Use spaces for indentation",
                    SourceLocation(line_number, column, line_number, column + 1),
                    code="SYNTAX_ERROR",
                )
        try:
            for token in tokenize.generate_tokens(io.StringIO(self.code).readline):
                text = token.string
                unsupported = token.type == tokenize.OP and text == ";"
                if token.type == tokenize.STRING:
                    stripped = text[1:] if text[:1] in ("r", "R") else text
                    unsupported |= (
                        not stripped.startswith(("'", '"'))
                        or stripped.startswith(("'" * 3, '"' * 3))
                        or "\\N{" in stripped
                    )
                if unsupported:
                    raise Sema.SemaException(
                        "Unsupported portable-language syntax",
                        SourceLocation(
                            token.start[0], token.start[1] + 1, token.end[0], token.end[1] + 1
                        ),
                        code="SYNTAX_ERROR",
                    )
            tree = ast.parse(self.code)
        except (SyntaxError, RecursionError, tokenize.TokenError) as error:
            line = getattr(error, "lineno", 1) or 1
            col = getattr(error, "offset", 1) or 1
            raise Sema.SemaException(
                str(getattr(error, "msg", error)),
                SourceLocation(line, col, line, col + 1),
                code="SYNTAX_ERROR",
            ) from error
        if sum(1 for _ in ast.walk(tree)) > 20_000:
            self.fail("Program is too complex", tree.body[0])
        classes = []
        symbols = set()
        for node in tree.body:
            if self.docstring(node):
                continue
            if isinstance(node, ast.ClassDef):
                self.identifier(node.name, node)
                if node.name in symbols or node.name in Sema.RESERVED_ENTITY_NAMES:
                    self.fail(f"Duplicate or reserved name '{node.name}'", node, "SEMANTIC_ERROR")
                symbols.add(node.name)
                if (
                    node.decorator_list
                    or len(node.bases) != 1
                    or not isinstance(node.bases[0], ast.Name)
                    or node.bases[0].id not in ("Entity", "Enum")
                ):
                    self.fail("Classes must inherit only Entity or Enum, without decorators", node)
                if node.body and node.body[0].lineno == node.lineno:
                    self.fail("Use an indented class body", node)
                classes.append(node)
                if node.bases[0].id == "Enum":
                    self.enums[node.name] = self.enum(node)
                else:
                    self.entities[node.name] = node
            elif (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call)
            ):
                name = node.targets[0].id
                self.identifier(name, node)
                if name in symbols or name in Sema.RESERVED_ENTITY_NAMES:
                    self.fail(f"Duplicate or reserved name '{name}'", node, "SEMANTIC_ERROR")
                symbols.add(name)
                self.seed_nodes[name] = node
            else:
                self.fail(
                    "Only enum/entity declarations and named entity constructions are allowed", node
                )
        if len(self.seed_nodes) > 1000:
            self.fail("At most 1000 seed objects are allowed", next(iter(self.seed_nodes.values())))
        if not classes and self.context_schema is not None:
            schema = self.context_schema.model_copy(deep=True)
            self.enums = {enum.name: enum for enum in schema.enums}
        else:
            schema = Sema.Schema(
                entities=[self.entity(node) for node in self.entities.values()],
                enums=list(self.enums.values()),
            )
        Sema().validate(schema)
        seeds = [self.seed(name, node) for name, node in self.seed_nodes.items()]
        return analyze_program(Program(schema=schema, objects=seeds))

    def identifier(self, name, node):
        if not name.isidentifier() or keyword.iskeyword(name) or name.startswith("_"):
            self.fail(f"Invalid identifier '{name}'", node, "SEMANTIC_ERROR")

    @staticmethod
    def docstring(node):
        return (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )

    def enum(self, node):
        if node.keywords:
            self.fail("Enums do not accept class options", node)
        members = []
        for item in node.body:
            if self.docstring(item):
                continue
            if isinstance(item, ast.Expr) and isinstance(item.value, ast.Name):
                name, value = item.value.id, item.value.id
            elif (
                isinstance(item, ast.Assign)
                and len(item.targets) == 1
                and isinstance(item.targets[0], ast.Name)
            ):
                name, value = item.targets[0].id, self.literal(item.value, enum_values=False)
                if type(value) not in (str, int):
                    self.fail("Enum values must be strings or integers", item)
            else:
                self.fail("Enum members must be bare names or literal assignments", item)
            members.append(Sema.EnumMember(name=name, value=value, location=self.location(item)))
        return Sema.EnumDefinition(name=node.name, members=members, location=self.location(node))

    def entity(self, node):
        explicit = None
        for option in node.keywords:
            if option.arg != "tablename" or explicit is not None:
                self.fail("Only one tablename class option is supported", option)
            explicit = self.literal(option.value)
        fields = []
        for item in node.body:
            if self.docstring(item) or isinstance(item, ast.Pass):
                continue
            if (
                isinstance(item, ast.Assign)
                and len(item.targets) == 1
                and isinstance(item.targets[0], ast.Name)
                and item.targets[0].id == "__tablename__"
            ):
                if explicit is not None:
                    self.fail("Duplicate tablename", item)
                explicit = self.literal(item.value)
                continue
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                fields.append(self.field(item.target.id, item.annotation, item, item.value))
            elif (
                isinstance(item, ast.Assign)
                and len(item.targets) == 1
                and isinstance(item.targets[0], ast.Name)
            ):
                fields.append(self.field(item.targets[0].id, item.value, item))
            else:
                self.fail("Entity bodies contain only field declarations", item)
        tablename = explicit if explicit is not None else self.table_names.get(node.name)
        if tablename is None:
            tablename = table_name(node.name, self.namespace)
        try:
            return Sema.Entity(
                name=node.name, fields=fields, tablename=tablename, location=self.location(node)
            )
        except ValidationError as error:
            self.fail(str(error), node, "SEMANTIC_ERROR")

    def field(self, name, expression, node, default=None):
        options, args = {}, []
        if isinstance(expression, ast.Call):
            args = expression.args
            for option in expression.keywords:
                if option.arg not in OPTIONS or option.arg in options:
                    self.fail(f"Unknown or repeated field option '{option.arg}'", option)
                options[option.arg] = self.literal(option.value)
            expression = expression.func
        if not isinstance(expression, ast.Name):
            self.fail("Field types must be built-in, entity, or enum names", node)
        symbol = expression.id
        if symbol == "Reference":
            if len(args) != 1:
                self.fail("Reference requires exactly one target entity", node)
            target = args[0]
            reference = target.id if isinstance(target, ast.Name) else self.literal(target)
            kind, extra = "reference", {"reference": reference}
        elif args:
            self.fail("Only Reference accepts positional field arguments", node)
        elif symbol in BUILTINS:
            kind, extra = BUILTINS[symbol], {}
        elif symbol in self.enums:
            kind, extra = "enum", {"enum_type": symbol}
        elif symbol in self.entities:
            kind, extra = "reference", {"reference": symbol}
        else:
            self.fail(f"Unknown type '{symbol}'", node, "SEMANTIC_ERROR")
        if default is not None:
            if "default" in options:
                self.fail("Default specified twice", node)
            options["default"] = self.literal(default)
        try:
            return Sema.Field(
                name=name,
                type=kind,
                location=self.location(node),
                has_default="default" in options,
                **extra,
                **options,
            )
        except ValidationError as error:
            self.fail(str(error), node, "SEMANTIC_ERROR")

    def literal(self, node, *, enum_values=True, depth=0):
        if depth > 64:
            self.fail("Literal nesting exceeds 64 levels", node)
        if isinstance(node, ast.Constant) and type(node.value) in (
            str,
            int,
            float,
            bool,
            type(None),
        ):
            value = node.value
            if type(value) in (int, float):
                source = ast.get_source_segment(self.code, node)
                if not re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", source):
                    self.fail("Use decimal numeric literals", node)
            if type(value) is int and abs(value) > 2**53 - 1:
                self.fail("Integer exceeds the portable safe-integer range", node)
            if type(value) is float:
                if not math.isfinite(value):
                    self.fail("Number must be finite", node)
                if value.is_integer() and abs(value) <= 2**53 - 1:
                    value = int(value)
            return value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = self.literal(node.operand, enum_values=False, depth=depth + 1)
            if type(value) not in (int, float):
                self.fail("Unary signs require numbers", node)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.List):
            return [self.literal(item, depth=depth + 1) for item in node.elts]
        if isinstance(node, ast.Dict):
            result = {}
            for key_node, value_node in zip(node.keys, node.values, strict=True):
                if key_node is None:
                    self.fail("Dictionary expansion is not supported", node)
                key = self.literal(key_node, depth=depth + 1)
                if not isinstance(key, str) or key in result:
                    self.fail("JSON object keys must be unique strings", key_node)
                result[key] = self.literal(value_node, depth=depth + 1)
            return result
        if (
            enum_values
            and isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in self.enums
        ):
            enum = self.enums[node.value.id]
            for member in enum.members:
                if member.name == node.attr:
                    return member.value
            self.fail(f"Unknown enum member '{node.value.id}.{node.attr}'", node, "SEMANTIC_ERROR")
        self.fail("Expected a JSON literal or enum member", node)

    def seed(self, name, node):
        call = node.value
        if not isinstance(call.func, ast.Name) or call.args:
            self.fail("Seed objects require EntityName(field=value, ...) syntax", call)
        values = {}
        for option in call.keywords:
            if option.arg is None or option.arg in values:
                self.fail("Seed fields must be unique named arguments", option)
            value = option.value
            if isinstance(value, ast.Name) and value.id not in ("True", "False", "None"):
                values[option.arg] = {"$ref": value.id}
            elif (
                isinstance(value, ast.Attribute)
                and isinstance(value.value, ast.Name)
                and value.attr == "id"
                and value.value.id in self.seed_nodes
            ):
                values[option.arg] = {"$ref": value.value.id}
            else:
                values[option.arg] = self.literal(value)
        return SeedObject(
            name=name, entity=call.func.id, values=values, location=self.location(node)
        )


def analyze_program(program: Program) -> Program:
    """Validate a parsed/client-supplied program and derive a dependency-safe seed order."""
    if len(program.objects) > 1000:
        raise Sema.SemaException(
            "At most 1000 seed objects are allowed", program.objects[1000].location
        )
    Sema().validate(program.schema)
    entities = {entity.name: entity for entity in program.schema.entities}
    seeds = {}
    for seed in program.objects:
        Sema().identifier(seed.name, seed)
        if (
            seed.name in seeds
            or seed.name in entities
            or seed.name in {enum.name for enum in program.schema.enums}
            or seed.name in Sema.RESERVED_ENTITY_NAMES
        ):
            raise Sema.SemaException(
                f"Duplicate or reserved seed name '{seed.name}'", seed.location
            )
        seeds[seed.name] = seed
    dependencies = {}
    for seed in program.objects:
        if seed.entity not in entities:
            raise Sema.SemaException(f"Unknown seed entity '{seed.entity}'", seed.location)
        fields = {field.name: field for field in entities[seed.entity].fields}
        unknown = set(seed.values) - fields.keys()
        if unknown:
            raise Sema.SemaException(f"Unknown seed fields: {sorted(unknown)}", seed.location)
        dependencies[seed.name] = set()
        for field in fields.values():
            if field.name not in seed.values:
                if field.has_default or field.default is not None:
                    seed.values[field.name] = deepcopy(field.default)
                elif not field.nullable:
                    raise Sema.SemaException(
                        f"Required seed field missing: {field.name}", seed.location
                    )
                else:
                    continue
            value = seed.values[field.name]
            if field.type == Sema.Type.REFERENCE and value is not None:
                target = (
                    seeds.get(value["$ref"])
                    if (
                        isinstance(value, dict)
                        and set(value) == {"$ref"}
                        and isinstance(value["$ref"], str)
                    )
                    else None
                )
                if target is None or target.entity != field.reference:
                    raise Sema.SemaException(
                        f"'{field.name}' must reference a seed of {field.reference}", seed.location
                    )
                dependencies[seed.name].add(target.name)
            else:
                try:
                    validate_value(value, field.model_dump())
                except (ValueError, TypeError, OverflowError) as error:
                    raise Sema.SemaException(
                        f"{seed.name}.{field.name}: {error}", seed.location
                    ) from error
    order, visiting, visited = [], set(), set()

    for root in seeds:
        stack = [(root, False)]
        while stack:
            name, exiting = stack.pop()
            if exiting:
                visiting.remove(name)
                visited.add(name)
                order.append(name)
                continue
            if name in visited:
                continue
            if name in visiting:
                raise Sema.SemaException(
                    "Cyclic seed references are not supported",
                    seeds[name].location,
                )
            visiting.add(name)
            stack.append((name, True))
            stack.extend((dependency, False) for dependency in reversed(sorted(dependencies[name])))
    program.seed_order = order
    return program


def compile_source(code: str, *, namespace="", table_names=None, context_schema=None) -> Program:
    return Parser(
        code, namespace=namespace, table_names=table_names, context_schema=context_schema
    ).parse()
