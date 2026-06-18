from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .dtos import JobPosting


@dataclass(frozen=True)
class JobFilterSet:
    expression: dict[str, Any] | None = None

    @classmethod
    def accept_all(cls) -> "JobFilterSet":
        return cls()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobFilterSet":
        if not isinstance(data, dict):
            raise ValueError("filter JSON must be an object")
        if not data:
            return cls.accept_all()
        return cls(expression=data)

    @property
    def enabled(self) -> bool:
        return self.expression is not None

    def apply(self, jobs: list[JobPosting]) -> list[JobPosting]:
        if not self.enabled:
            return jobs
        return [job for job in jobs if self.matches(job)]

    def matches(self, job: JobPosting) -> bool:
        if not self.expression:
            return True
        return self._matches_expression(self.expression, job.to_dict())

    def _matches_expression(self, expression: dict[str, Any], data: dict[str, Any]) -> bool:
        if "all" in expression:
            return all(self._matches_expression(item, data) for item in self._as_expression_list(expression["all"], "all"))
        if "any" in expression:
            return any(self._matches_expression(item, data) for item in self._as_expression_list(expression["any"], "any"))
        if "not" in expression:
            nested = expression["not"]
            if not isinstance(nested, dict):
                raise ValueError("not filter must be an object")
            return not self._matches_expression(nested, data)
        return self._matches_rule(expression, data)

    def _matches_rule(self, rule: dict[str, Any], data: dict[str, Any]) -> bool:
        fields = rule.get("fields") or rule.get("field")
        if fields is None:
            raise ValueError("filter rule requires field or fields")
        field_names = [str(fields)] if isinstance(fields, str) else [str(field) for field in fields]
        values = [self._field_value(data, field_name) for field_name in field_names]
        return any(self._value_matches_rule(value, rule) for value in values)

    def _value_matches_rule(self, value: Any, rule: dict[str, Any]) -> bool:
        case_sensitive = bool(rule.get("case_sensitive", False))
        if "exists" in rule:
            return (value is not None and value != "") is bool(rule["exists"])
        if "contains" in rule:
            return self._contains(value, rule["contains"], case_sensitive)
        if "not_contains" in rule:
            return not self._contains(value, rule["not_contains"], case_sensitive)
        if "equals" in rule:
            return self._normalize(value, case_sensitive) == self._normalize(rule["equals"], case_sensitive)
        if "not_equals" in rule:
            return self._normalize(value, case_sensitive) != self._normalize(rule["not_equals"], case_sensitive)
        if "regex" in rule:
            flags = 0 if case_sensitive else re.IGNORECASE
            return re.search(str(rule["regex"]), self._stringify(value), flags) is not None
        if "in" in rule:
            candidates = rule["in"]
            if not isinstance(candidates, list):
                raise ValueError("in filter must be a list")
            normalized_value = self._normalize(value, case_sensitive)
            return any(normalized_value == self._normalize(candidate, case_sensitive) for candidate in candidates)
        raise ValueError("filter rule requires an operator")

    @staticmethod
    def _as_expression_list(value: Any, key: str) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            raise ValueError(f"{key} filter must be a list")
        if not all(isinstance(item, dict) for item in value):
            raise ValueError(f"{key} filter items must be objects")
        return value

    @classmethod
    def _field_value(cls, data: dict[str, Any], field_name: str) -> Any:
        current: Any = data
        for part in field_name.split("."):
            if isinstance(current, dict):
                current = current.get(part)
                continue
            return None
        return current

    @classmethod
    def _contains(cls, value: Any, expected: Any, case_sensitive: bool) -> bool:
        if isinstance(expected, list):
            return any(cls._contains(value, item, case_sensitive) for item in expected)
        return cls._normalize(expected, case_sensitive) in cls._normalize(value, case_sensitive)

    @staticmethod
    def _normalize(value: Any, case_sensitive: bool) -> str:
        text = JobFilterSet._stringify(value)
        return text if case_sensitive else text.casefold()

    @staticmethod
    def _stringify(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return " ".join(JobFilterSet._stringify(item) for item in value)
        if isinstance(value, dict):
            return " ".join(f"{key} {JobFilterSet._stringify(item)}" for key, item in value.items())
        return str(value)
