from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class InvalidInputError(ValueError):
    pass


class InvalidConfigError(ValueError):
    pass


class ConversionError(RuntimeError):
    pass


class WriteError(RuntimeError):
    pass


class ConversionConfig(BaseModel):
    output_prefix: str
    output_name: str

    inline_threshold: int = 300
    concat_dims: list[str] = Field(default_factory=lambda: ["time"])
    identical_dims: list[str] | None = None
    overwrite_existing: bool = False

    @field_validator("output_name")
    @classmethod
    def _validate_output_name(cls, v: str) -> str:
        if not v:
            raise ValueError("output_name must be non-empty")
        if "/" in v or "\\" in v:
            raise ValueError("output_name must not contain path separators")
        if v.endswith(".json"):
            raise ValueError("output_name must not include .json suffix")
        return v


class ConversionResult(BaseModel):
    output_uri: str
    reference: dict[str, Any]
    inputs: list[str]
