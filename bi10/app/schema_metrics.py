from __future__ import annotations

METRICS_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["timezone", "currency", "metrics"],
    "properties": {
        "timezone": {"type": "string"},
        "currency": {"type": "string"},
        "marts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "files"],
                "properties": {
                    "id": {"type": "string"},
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                },
                "additionalProperties": True,
            },
        },
        "dimensions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "column", "type", "mart"],
                "properties": {
                    "id": {"type": "string"},
                    "column": {"type": "string"},
                    "type": {"type": "string"},
                    "mart": {"type": "string"},
                    "name": {"type": "string"},
                },
                "additionalProperties": True,
            },
        },
        "metrics": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "name", "mart", "sql"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "mart": {"type": "string"},
                    "sql": {"type": "string"},
                    "default_chart": {"type": "string"},
                    "unit": {"type": "string"},
                    "cap": {"type": "integer", "minimum": 1},
                },
                "additionalProperties": True,
            },
        },
    },
    "additionalProperties": True,
}

__all__ = ["METRICS_SCHEMA"]
