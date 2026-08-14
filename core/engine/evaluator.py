from typing import Any, Dict, Union
from jsonpath_ng.ext import parse
from core.common.schemas import VariableConfig, VariableRule
from core.common.exceptions import EvaluatorError
from core.common.logger import log


class VariableEvaluator:
    """Evaluates dynamic variable substitution maps using JSONPath syntax or static fallbacks."""

    @staticmethod
    def evaluate(rule: Union[VariableConfig, VariableRule], context_data: Dict[str, Any]) -> Any:
        """Resolves a single variable rule against context data with default fallback."""
        if not rule:
            return None

        # 1. Attempt JSONPath extraction first if defined
        if rule.jsonpath:
            try:
                jsonpath_expr = parse(rule.jsonpath)
                matches = jsonpath_expr.find(context_data)
                if matches and matches[0].value is not None:
                    return matches[0].value
                else:
                    log.debug(f"JSONPath '{rule.jsonpath}' found no matches in context. Falling back to default.")
            except Exception as e:
                raise EvaluatorError(f"Failed to evaluate JSONPath [{rule.jsonpath}]: {str(e)}")

        # 2. Fall back to static default value
        return rule.default

    @classmethod
    def evaluate_all(
        cls, 
        var_map: Dict[str, Union[VariableConfig, VariableRule]], 
        context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluates a dictionary of variable rules against context data."""
        resolved: Dict[str, Any] = {}

        if not var_map:
            return resolved

        for var_name, rule in var_map.items():
            resolved[var_name] = cls.evaluate(rule, context_data)

        return resolved