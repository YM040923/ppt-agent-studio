from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any


ToolArguments = Mapping[str, Any]
ToolHandler = Callable[[ToolArguments], "ToolResult | Awaitable[ToolResult]"]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object"})

    def __post_init__(self) -> None:
        name = self.name.strip()
        description = self.description.strip()
        if not name:
            raise ValueError("tool name is required")
        if not description:
            raise ValueError("tool description is required")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": dict(self.input_schema),
        }


@dataclass(frozen=True)
class ToolResult:
    payload: dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"tool already registered: {definition.name}")
        self._definitions[definition.name] = definition
        self._handlers[definition.name] = handler

    def definitions(self) -> list[ToolDefinition]:
        return list(self._definitions.values())

    async def run(self, name: str, arguments: ToolArguments) -> ToolResult:
        definition = self._definitions.get(name)
        handler = self._handlers.get(name)
        if handler is None or definition is None:
            raise KeyError(f"unknown tool: {name}")
        self._validate_arguments(definition, arguments)
        result = handler(arguments)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, ToolResult):
            raise TypeError(f"tool returned unsupported result: {name}")
        return result

    @staticmethod
    def _validate_arguments(definition: ToolDefinition, arguments: ToolArguments) -> None:
        if not isinstance(arguments, Mapping):
            raise ValueError(f"tool arguments must be an object: {definition.name}")
        required = definition.input_schema.get("required", [])
        if isinstance(required, list):
            for name in required:
                if isinstance(name, str) and name not in arguments:
                    raise ValueError(f"missing required tool argument: {name}")

        properties = definition.input_schema.get("properties", {})
        if not isinstance(properties, Mapping):
            return
        for name, schema in properties.items():
            if not isinstance(name, str) or name not in arguments or not isinstance(schema, Mapping):
                continue
            expected_type = schema.get("type")
            if isinstance(expected_type, str) and not _matches_json_type(arguments[name], expected_type):
                raise ValueError(f"invalid tool argument type: {name}")


def _matches_json_type(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, Mapping)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True
