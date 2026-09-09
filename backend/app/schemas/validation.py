from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ValidationErrorItem(BaseModel):
    field: str
    code: str
    message: str


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    valid: bool
    errors: list[ValidationErrorItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EligibilityRuleResult(BaseModel):
    rule: str
    passed: bool
    observed: Any = None
    expected: str
    message: str


class EligibilityResult(BaseModel):
    eligible: bool
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checks: list[EligibilityRuleResult] = Field(default_factory=list)


class ApplicationValidationResponse(BaseModel):
    valid: bool
    errors: list[ValidationErrorItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    complete: bool
    missing_fields: list[str] = Field(default_factory=list)
    missing_documents: list[str] = Field(default_factory=list)
    eligibility: EligibilityResult
