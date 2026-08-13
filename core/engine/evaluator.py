from typing import Any, Dict
from jsonpath_ng.ext import parse
from core.common.schemas import VariableRule
from core.common.exceptions import EvaluatorError
from core.common.logger import log


class VariableEvaluator:
    """Evaluates variables against context data according to simple rules:
    - No jsonpath: Treats `value` as a static literal constant.
    - Has jsonpath: Evaluates JsonPath expression against root context; uses `value` as fallback if null/missing.
    """

    @staticmethod
    def evaluate(rule: VariableRule, context: Dict[str, Any]) -> Any:
        """Evaluates a single VariableRule against context."""
        try:
            # Case 1: Static Value Constant
            if not rule.jsonpath:
                return rule.value

            # Case 2: Dynamic JsonPath Extraction
            jsonpath_expr = parse(rule.jsonpath)
            matches = jsonpath_expr.find(context)

            if matches:
                extracted_val = matches[0].value
                if extracted_val is not None and extracted_val != "":
                    return extracted_val

            # Fallback to static default value
            return rule.value

        except Exception as e:
            raise EvaluatorError(f"Failed to evaluate variable with JsonPath [{rule.jsonpath}]: {str(e)}")

    @classmethod
    def evaluate_all(cls, rules: Dict[str, VariableRule], context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluates all variable rules declared for a step."""
        resolved_vars = {}
        if not rules:
            return resolved_vars

        for var_name, rule in rules.items():
            resolved_vars[var_name] = cls.evaluate(rule, context)

        return resolved_vars