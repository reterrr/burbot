"""Compatibility imports; language execution now belongs to BusinessService."""

from business_layer.schemas.execution import ExecutionResult
from business_layer.services.business import BusinessService as LanguageService

__all__ = ["LanguageService", "ExecutionResult"]
