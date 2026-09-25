import math
from abc import ABC, abstractmethod
from typing import Any, Dict


class IndustryFilter(ABC):
    code = "generic"
    display_name = "Ngành khác"
    metric_groups = ()

    @abstractmethod
    def evaluate(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Return status, groups, reasons and missing_metrics without inventing values."""
        raise NotImplementedError

    def _result(self, groups, reasons, missing_metrics, score=None):
        if missing_metrics:
            status = "INSUFFICIENT_DATA"
        elif reasons:
            status = "FAIL"
        else:
            status = "PASS"
        return {
            "industry_code": self.code,
            "industry_name": self.display_name,
            "is_passed": status == "PASS",
            "status": status,
            "score": score,
            "groups": groups,
            "reasons": reasons,
            "missing_metrics": missing_metrics,
        }


def metric_check(metrics, code, label, operator, threshold):
    value = metrics.get(code)
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return {"code": code, "label": label, "value": None, "status": "N/A"}, None, None
    passed = operator(value, threshold)
    detail = {
        "code": code,
        "label": label,
        "value": value,
        "threshold": threshold,
        "status": "PASS" if passed else "FAIL",
    }
    return detail, None if passed else f"{label} không đạt ngưỡng ({value} {operator.__name__} {threshold})", None


def score_metric(metrics, rule):
    value = metrics.get(rule["code"])
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return {
            "code": rule["code"], "label": rule["label"], "value": None,
            "status": "N/A", "weight": rule["weight"], "points": None,
        }
    passed = rule["operator"](value, rule["threshold"])
    return {
        "code": rule["code"], "label": rule["label"], "value": value,
        "threshold": rule["threshold"], "status": "PASS" if passed else "WARNING",
        "weight": rule["weight"], "points": 100.0 if passed else 0.0,
    }
