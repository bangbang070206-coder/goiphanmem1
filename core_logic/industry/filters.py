from operator import ge, le, gt
from typing import Any, Dict

from .base import IndustryFilter, metric_check


class ThresholdIndustryFilter(IndustryFilter):
    rules = {}
    metric_groups = ()

    def evaluate(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        groups = {group: [] for group in self.metric_groups}
        reasons = []
        missing = []
        passed_count = 0
        available_count = 0
        for code, rule in self.rules.items():
            detail, reason, _ = metric_check(metrics, code, rule["label"], rule["operator"], rule["threshold"])
            groups.setdefault(rule["group"], []).append(detail)
            if detail["status"] == "N/A":
                missing.append(code)
            else:
                available_count += 1
                if detail["status"] == "PASS":
                    passed_count += 1
                elif reason:
                    reasons.append(reason)
        score = 100.0 * passed_count / available_count if available_count else None
        return self._result(groups, reasons, missing, score=score)


class GenericIndustryFilter(ThresholdIndustryFilter):
    code = "generic"
    display_name = "Ngành khác"
    metric_groups = ("profitability", "growth", "risk")
    rules = {
        "roe": {"label": "ROE", "operator": ge, "threshold": 0.15, "group": "profitability"},
        "rev_growth": {"label": "Tăng trưởng doanh thu", "operator": gt, "threshold": 0, "group": "growth"},
        "np_growth": {"label": "Tăng trưởng lợi nhuận", "operator": gt, "threshold": 0, "group": "growth"},
        "debt_to_equity": {"label": "Nợ/VCSH", "operator": le, "threshold": 1.5, "group": "risk"},
        "cfo": {"label": "CFO TTM", "operator": gt, "threshold": 0, "group": "risk"},
    }


class BankingFilter(ThresholdIndustryFilter):
    code = "banking"
    display_name = "Ngân hàng"
    metric_groups = ("profitability", "asset_quality", "growth")
    rules = {
        "roe": {"label": "ROE", "operator": ge, "threshold": 0.10, "group": "profitability"},
        "nim": {"label": "NIM", "operator": gt, "threshold": 0, "group": "profitability"},
        "np_growth": {"label": "Tăng trưởng lợi nhuận", "operator": gt, "threshold": 0, "group": "growth"},
        "npl": {"label": "NPL", "operator": le, "threshold": 0.03, "group": "asset_quality"},
        "loan_loss_coverage": {"label": "Bao phủ nợ xấu", "operator": ge, "threshold": 1.0, "group": "asset_quality"},
        "credit_growth": {"label": "Tăng trưởng tín dụng", "operator": gt, "threshold": 0, "group": "growth"},
    }


class SecuritiesFilter(ThresholdIndustryFilter):
    code = "securities"
    display_name = "Chứng khoán"
    metric_groups = ("profitability", "market_activity", "margin")
    rules = {
        "roe": {"label": "ROE", "operator": ge, "threshold": 0.10, "group": "profitability"},
        "rev_growth": {"label": "Tăng trưởng doanh thu", "operator": gt, "threshold": 0, "group": "profitability"},
        "np_growth": {"label": "Tăng trưởng lợi nhuận", "operator": gt, "threshold": 0, "group": "profitability"},
        "margin_loan_growth": {"label": "Tăng trưởng dư nợ margin", "operator": gt, "threshold": 0, "group": "margin"},
        "capital_adequacy": {"label": "An toàn tài chính", "operator": ge, "threshold": 1.10, "group": "market_activity"},
    }


class RealEstateFilter(ThresholdIndustryFilter):
    code = "real_estate"
    display_name = "Bất động sản"
    metric_groups = ("balance_sheet", "operating", "cash_flow")
    rules = {
        "rev_growth": {"label": "Tăng trưởng doanh thu", "operator": gt, "threshold": 0, "group": "operating"},
        "gross_margin": {"label": "Biên lợi nhuận gộp", "operator": gt, "threshold": 0, "group": "operating"},
        "debt_to_equity": {"label": "Nợ/VCSH", "operator": le, "threshold": 2.0, "group": "balance_sheet"},
        "cfo": {"label": "CFO TTM", "operator": gt, "threshold": 0, "group": "cash_flow"},
        "customer_advances": {"label": "Người mua trả tiền trước", "operator": gt, "threshold": 0, "group": "operating"},
    }


class SteelFilter(ThresholdIndustryFilter):
    code = "steel"
    display_name = "Thép"
    metric_groups = ("revenue_volume", "margin", "risk", "cash_flow")
    rules = {
        "rev_growth": {"label": "Tăng trưởng doanh thu", "operator": gt, "threshold": 0, "group": "revenue_volume"},
        "gross_margin": {"label": "Biên lợi nhuận gộp", "operator": gt, "threshold": 0, "group": "margin"},
        "debt_to_equity": {"label": "Nợ/VCSH", "operator": le, "threshold": 2.0, "group": "risk"},
        "cfo": {"label": "CFO TTM", "operator": gt, "threshold": 0, "group": "cash_flow"},
        "sales_volume": {"label": "Sản lượng tiêu thụ", "operator": gt, "threshold": 0, "group": "revenue_volume"},
    }


class OilGasFilter(ThresholdIndustryFilter):
    code = "oil_gas"
    display_name = "Dầu khí"
    metric_groups = ("profitability", "operations", "cash_flow")
    rules = {
        "rev_growth": {"label": "Tăng trưởng doanh thu", "operator": gt, "threshold": 0, "group": "profitability"},
        "np_growth": {"label": "Tăng trưởng lợi nhuận", "operator": gt, "threshold": 0, "group": "profitability"},
        "cfo": {"label": "CFO TTM", "operator": gt, "threshold": 0, "group": "cash_flow"},
        "production_volume": {"label": "Sản lượng", "operator": gt, "threshold": 0, "group": "operations"},
    }


class ElectricityFilter(ThresholdIndustryFilter):
    code = "electricity"
    display_name = "Điện"
    metric_groups = ("profitability", "operations", "risk")
    rules = {
        "rev_growth": {"label": "Tăng trưởng doanh thu", "operator": gt, "threshold": 0, "group": "profitability"},
        "np_growth": {"label": "Tăng trưởng lợi nhuận", "operator": gt, "threshold": 0, "group": "profitability"},
        "debt_to_equity": {"label": "Nợ/VCSH", "operator": le, "threshold": 2.5, "group": "risk"},
        "power_output": {"label": "Sản lượng điện", "operator": gt, "threshold": 0, "group": "operations"},
    }


class RetailFilter(ThresholdIndustryFilter):
    code = "retail"
    display_name = "Bán lẻ"
    metric_groups = ("profitability", "operations", "cash_flow")
    rules = {
        "rev_growth": {"label": "Tăng trưởng doanh thu", "operator": gt, "threshold": 0, "group": "profitability"},
        "np_growth": {"label": "Tăng trưởng lợi nhuận", "operator": gt, "threshold": 0, "group": "profitability"},
        "gross_margin": {"label": "Biên lợi nhuận", "operator": gt, "threshold": 0, "group": "profitability"},
        "store_growth": {"label": "Tăng trưởng số cửa hàng", "operator": gt, "threshold": 0, "group": "operations"},
        "cfo": {"label": "CFO TTM", "operator": gt, "threshold": 0, "group": "cash_flow"},
    }


class ChemicalFilter(SteelFilter):
    code = "chemical"
    display_name = "Hóa chất"


class TransportPortFilter(ThresholdIndustryFilter):
    code = "transport_port"
    display_name = "Vận tải / Cảng biển"
    metric_groups = ("profitability", "operations", "cash_flow")
    rules = {
        "rev_growth": {"label": "Tăng trưởng doanh thu", "operator": gt, "threshold": 0, "group": "profitability"},
        "np_growth": {"label": "Tăng trưởng lợi nhuận", "operator": gt, "threshold": 0, "group": "profitability"},
        "cargo_volume": {"label": "Sản lượng hàng hóa", "operator": gt, "threshold": 0, "group": "operations"},
        "utilization_rate": {"label": "Công suất sử dụng", "operator": gt, "threshold": 0, "group": "operations"},
        "cfo": {"label": "CFO TTM", "operator": gt, "threshold": 0, "group": "cash_flow"},
    }


# v2 industry rules: hard filters decide FAIL; scoring rules only contribute
# points and report WARNING when a present value misses its scoring threshold.
from .base import score_metric


def _hard(code, label, operator, threshold, group):
    return {"code": code, "label": label, "operator": operator, "threshold": threshold, "group": group}


def _score(code, label, weight, operator, threshold, group):
    return {"code": code, "label": label, "weight": weight, "operator": operator, "threshold": threshold, "group": group}


class ConfiguredIndustryFilter(IndustryFilter):
    hard_filters = ()
    scoring_rules = ()

    def evaluate(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        groups, reasons, missing_hard, missing_scoring = {}, [], [], []
        for rule in self.hard_filters:
            detail, reason, _ = metric_check(metrics, rule["code"], rule["label"], rule["operator"], rule["threshold"])
            groups.setdefault(rule["group"], []).append(detail)
            if detail["status"] == "N/A":
                missing_hard.append(rule["code"])
            elif reason:
                reasons.append(reason)

        points = 0.0
        weight_available = 0.0
        for rule in self.scoring_rules:
            detail = score_metric(metrics, rule)
            groups.setdefault(rule["group"], []).append(detail)
            if detail["status"] == "N/A":
                missing_scoring.append(rule["code"])
            else:
                points += detail["points"] * rule["weight"]
                weight_available += rule["weight"]

        missing = missing_hard + missing_scoring
        if missing_hard or missing_scoring:
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
            "score": points / weight_available if weight_available else None,
            "groups": groups,
            "reasons": reasons,
            "missing_metrics": missing,
            "missing_hard_filters": missing_hard,
            "missing_scoring_metrics": missing_scoring,
        }


def _rules(hard_filters, scoring_rules):
    return type("IndustryRules", (), {"hard_filters": hard_filters, "scoring_rules": scoring_rules})


def _industry_class(name, code, display_name, groups, hard_filters, scoring_rules):
    return type(name, (ConfiguredIndustryFilter,), {
        "code": code,
        "display_name": display_name,
        "metric_groups": groups,
        "hard_filters": hard_filters,
        "scoring_rules": scoring_rules,
    })


BankingFilter = _industry_class("BankingFilter", "banking", "Ngân hàng", ("profitability", "asset_quality", "growth"), (
    _hard("roe", "ROE", ge, .12, "profitability"), _hard("npl", "NPL", le, .03, "asset_quality"),
    _hard("car", "CAR", ge, .09, "asset_quality"), _hard("np_growth", "Tăng trưởng lợi nhuận", ge, 0, "growth")), (
    _score("roe", "ROE", .20, ge, .12, "profitability"), _score("nim", "NIM", .15, gt, 0, "profitability"),
    _score("np_growth", "Tăng trưởng lợi nhuận", .15, ge, 0, "growth"), _score("credit_growth", "Tăng trưởng tín dụng", .10, gt, 0, "growth"),
    _score("casa", "CASA", .10, gt, 0, "profitability"), _score("npl", "NPL", .10, le, .03, "asset_quality"),
    _score("loan_loss_coverage", "Bao phủ nợ xấu", .10, gt, 1, "asset_quality"), _score("cir", "CIR", .10, le, .60, "profitability")))

SecuritiesFilter = _industry_class("SecuritiesFilter", "securities", "Chứng khoán", ("profitability", "market_activity", "margin", "financial_strength"), (
    _hard("roe", "ROE", ge, .08, "profitability"), _hard("np_growth", "Tăng trưởng lợi nhuận", ge, 0, "profitability"),
    _hard("cfo", "CFO", ge, 0, "financial_strength"), _hard("capital_adequacy", "An toàn tài chính", ge, 1.10, "financial_strength")), (
    _score("roe", "ROE", .20, ge, .08, "profitability"), _score("np_growth", "Tăng trưởng lợi nhuận", .20, ge, 0, "profitability"),
    _score("brokerage_market_share", "Thị phần môi giới", .15, gt, 0, "market_activity"), _score("margin_loan_growth", "Tăng trưởng dư nợ margin", .15, gt, 0, "margin"),
    _score("brokerage_revenue", "Doanh thu môi giới", .10, gt, 0, "market_activity"), _score("trading_value", "Giá trị giao dịch", .10, gt, 0, "market_activity"),
    _score("rev_growth", "Tăng trưởng doanh thu", .10, gt, 0, "profitability")))

RealEstateFilter = _industry_class("RealEstateFilter", "real_estate", "Bất động sản", ("balance_sheet", "operating", "cash_flow"), (
    _hard("cfo", "CFO TTM", ge, 0, "cash_flow"), _hard("debt_to_equity", "Nợ/VCSH", le, 2.5, "balance_sheet"),
    _hard("interest_coverage", "Interest Coverage", gt, 1.5, "risk"), _hard("cash_short_term_debt", "Tiền/Nợ ngắn hạn", ge, 1, "balance_sheet")), (
    _score("cfo", "CFO TTM", .20, ge, 0, "cash_flow"), _score("debt_to_equity", "Nợ/VCSH", .15, le, 2.5, "balance_sheet"),
    _score("np_growth", "Tăng trưởng lợi nhuận", .15, gt, 0, "operating"), _score("gross_margin", "Biên lợi nhuận gộp", .10, gt, 0, "operating"),
    _score("rev_growth", "Tăng trưởng doanh thu", .10, gt, 0, "operating"), _score("customer_advances", "Người mua trả trước", .10, gt, 0, "operating"),
    _score("project_backlog", "Quỹ đất / dự án", .10, gt, 0, "operating"), _score("roe", "ROE", .10, ge, .08, "profitability")))

SteelFilter = _industry_class("SteelFilter", "steel", "Thép", ("revenue_volume", "margin", "risk", "cash_flow"), (
    _hard("cfo", "CFO TTM", ge, 0, "cash_flow"), _hard("debt_to_equity", "Nợ/VCSH", le, 2, "risk"), _hard("interest_coverage", "Interest Coverage", ge, 1.5, "risk")), (
    _score("np_growth", "Tăng trưởng lợi nhuận", .20, gt, 0, "profitability"), _score("gross_margin", "Biên lợi nhuận gộp", .15, gt, 0, "margin"),
    _score("rev_growth", "Tăng trưởng doanh thu", .10, gt, 0, "revenue_volume"), _score("roe", "ROE", .10, gt, 0, "profitability"),
    _score("cfo", "CFO TTM", .10, ge, 0, "cash_flow"), _score("debt_to_equity", "Nợ/VCSH", .10, le, 2, "risk"),
    _score("sales_volume", "Sản lượng tiêu thụ", .10, gt, 0, "revenue_volume"), _score("capacity_utilization", "Công suất sử dụng", .05, gt, 0, "revenue_volume"),
    _score("steel_price", "Giá thép", .05, gt, 0, "margin"), _score("input_cost", "Chi phí đầu vào", .05, le, 0, "margin")))


def _common_industry(name, code, label, hard_filters, scoring_rules):
    return _industry_class(name, code, label, ("profitability", "operations", "risk", "cash_flow"), hard_filters, scoring_rules)


OilGasFilter = _common_industry("OilGasFilter", "oil_gas", "Dầu khí", (
    _hard("cfo", "CFO TTM", gt, 0, "cash_flow"), _hard("debt_to_equity", "Nợ/VCSH", le, 2, "risk"), _hard("profit", "Lợi nhuận", ge, 0, "profitability")), (
    _score("np_growth", "Tăng trưởng lợi nhuận", .20, gt, 0, "profitability"), _score("roe", "ROE", .15, gt, 0, "profitability"), _score("cfo", "CFO TTM", .15, gt, 0, "cash_flow"), _score("rev_growth", "Tăng trưởng doanh thu", .10, gt, 0, "profitability"), _score("gross_margin", "Biên lợi nhuận", .10, gt, 0, "profitability"), _score("oil_price_exposure", "Mức hưởng lợi giá dầu", .10, gt, 0, "operations"), _score("backlog", "Backlog", .10, gt, 0, "operations"), _score("debt_to_equity", "Nợ/VCSH", .05, le, 2, "risk"), _score("dividend", "Cổ tức", .05, gt, 0, "profitability")))

ElectricityFilter = _common_industry("ElectricityFilter", "electricity", "Điện", (
    _hard("cfo", "CFO TTM", ge, 0, "cash_flow"), _hard("debt_to_equity", "Nợ/VCSH", le, 3, "risk"), _hard("interest_coverage", "Interest Coverage", ge, 1.5, "risk")), (
    _score("cfo", "CFO TTM", .20, ge, 0, "cash_flow"), _score("roe", "ROE", .15, gt, 0, "profitability"), _score("np_growth", "Tăng trưởng lợi nhuận", .15, gt, 0, "profitability"), _score("rev_growth", "Tăng trưởng doanh thu", .10, gt, 0, "profitability"), _score("debt_to_equity", "Nợ/VCSH", .10, le, 3, "risk"), _score("capacity_utilization", "Công suất sử dụng", .10, gt, 0, "operations"), _score("power_output", "Sản lượng điện", .05, gt, 0, "operations"), _score("gross_margin", "Biên lợi nhuận", .05, gt, 0, "profitability"), _score("dividend", "Cổ tức", .05, gt, 0, "profitability")))

RetailFilter = _common_industry("RetailFilter", "retail", "Bán lẻ", (
    _hard("cfo", "CFO TTM", gt, 0, "cash_flow"), _hard("np_growth", "Tăng trưởng lợi nhuận", ge, 0, "profitability"), _hard("debt_to_equity", "Nợ/VCSH", le, 2, "risk")), (
    _score("rev_growth", "Tăng trưởng doanh thu", .20, gt, 0, "profitability"), _score("np_growth", "Tăng trưởng lợi nhuận", .20, ge, 0, "profitability"), _score("roe", "ROE", .15, gt, 0, "profitability"), _score("gross_margin", "Biên lợi nhuận", .10, gt, 0, "profitability"), _score("cfo", "CFO TTM", .10, gt, 0, "cash_flow"), _score("same_store_sales", "Same-store Sales", .10, gt, 0, "operations"), _score("store_growth", "Tăng trưởng cửa hàng", .05, gt, 0, "operations"), _score("inventory_turnover", "Vòng quay tồn kho", .05, gt, 0, "operations"), _score("debt_to_equity", "Nợ/VCSH", .05, le, 2, "risk")))

ChemicalFilter = _common_industry("ChemicalFilter", "chemical", "Hóa chất", (_hard("cfo", "CFO TTM", gt, 0, "cash_flow"), _hard("debt_to_equity", "Nợ/VCSH", le, 2, "risk")), ())
TransportPortFilter = _common_industry("TransportPortFilter", "transport_port", "Vận tải / Cảng biển", (_hard("cfo", "CFO TTM", gt, 0, "cash_flow"), _hard("debt_to_equity", "Nợ/VCSH", le, 2, "risk"), _hard("profit", "Lợi nhuận", ge, 0, "profitability")), ())
SeafoodFilter = _common_industry("SeafoodFilter", "seafood", "Thủy sản", (_hard("cfo", "CFO TTM", gt, 0, "cash_flow"), _hard("debt_to_equity", "Nợ/VCSH", le, 2, "risk"), _hard("profit", "Lợi nhuận", ge, 0, "profitability")), ())
TextileFilter = _common_industry("TextileFilter", "textile", "Dệt may", (_hard("cfo", "CFO TTM", gt, 0, "cash_flow"), _hard("debt_to_equity", "Nợ/VCSH", le, 2, "risk")), ())
FoodBeverageFilter = _common_industry("FoodBeverageFilter", "food_beverage", "Thực phẩm / Đồ uống", (_hard("cfo", "CFO TTM", gt, 0, "cash_flow"), _hard("profit", "Lợi nhuận", ge, 0, "profitability"), _hard("debt_to_equity", "Nợ/VCSH", le, 2, "risk")), ())
PharmaceuticalFilter = _common_industry("PharmaceuticalFilter", "pharmaceuticals", "Dược phẩm", (_hard("roe", "ROE", ge, .10, "profitability"), _hard("cfo", "CFO TTM", gt, 0, "cash_flow"), _hard("debt_to_equity", "Nợ/VCSH", le, 1.5, "risk")), ())
ConstructionFilter = _common_industry("ConstructionFilter", "construction", "Xây dựng", (_hard("cfo", "CFO TTM", ge, 0, "cash_flow"), _hard("debt_to_equity", "Nợ/VCSH", le, 2.5, "risk"), _hard("interest_coverage", "Interest Coverage", ge, 1.5, "risk")), ())
IndustrialParkFilter = _common_industry("IndustrialParkFilter", "industrial_parks", "Khu công nghiệp", (_hard("cfo", "CFO TTM", ge, 0, "cash_flow"), _hard("debt_to_equity", "Nợ/VCSH", le, 2.5, "risk")), ())
InsuranceFilter = _common_industry("InsuranceFilter", "insurance", "Bảo hiểm", (_hard("profit", "Lợi nhuận", ge, 0, "profitability"), _hard("roe", "ROE", ge, .08, "profitability"), _hard("solvency_ratio", "Tỷ lệ khả năng thanh toán", ge, 1, "insurance_quality")), ())
SoftwareFilter = _common_industry("SoftwareFilter", "software", "Phần mềm / Công nghệ", (_hard("roe", "ROE", ge, .15, "profitability"), _hard("cfo", "CFO TTM", gt, 0, "cash_flow"), _hard("debt_to_equity", "Nợ/VCSH", le, 1.5, "risk"), _hard("np_growth", "Tăng trưởng lợi nhuận", ge, 0, "growth")), (
    _score("roe", "ROE", .20, ge, .15, "profitability"), _score("np_growth", "Tăng trưởng lợi nhuận", .20, ge, 0, "growth"), _score("rev_growth", "Tăng trưởng doanh thu", .15, gt, 0, "growth"), _score("eps_growth", "Tăng trưởng EPS", .10, gt, 0, "growth"), _score("gross_margin", "Biên lợi nhuận gộp", .10, gt, 0, "profitability"), _score("cfo_quality", "Chất lượng CFO", .10, gt, 0, "cash_flow"), _score("debt_to_equity", "Nợ/VCSH", .05, le, 1.5, "risk"), _score("roa", "ROA", .05, gt, 0, "profitability"), _score("rd_quality", "R&D / Chất lượng kinh doanh", .05, gt, 0, "quality")))

# Scoring-only rules for the remaining sectors. Missing optional metrics stay
# N/A/INSUFFICIENT_DATA and are never replaced with zero.
ChemicalFilter.scoring_rules = (
    _score("roe", "ROE", .15, gt, 0, "profitability"), _score("np_growth", "Tăng trưởng lợi nhuận", .15, gt, 0, "profitability"), _score("rev_growth", "Tăng trưởng doanh thu", .10, gt, 0, "profitability"), _score("gross_margin", "Biên lợi nhuận gộp", .15, gt, 0, "profitability"), _score("cfo", "CFO TTM", .15, gt, 0, "cash_flow"), _score("debt_to_equity", "Nợ/VCSH", .10, le, 2, "risk"), _score("selling_price", "Giá bán", .05, gt, 0, "operations"), _score("input_cost", "Chi phí đầu vào", .05, le, 0, "operations"), _score("capacity_utilization", "Công suất sử dụng", .10, gt, 0, "operations"))
TransportPortFilter.scoring_rules = (
    _score("rev_growth", "Tăng trưởng doanh thu", .15, gt, 0, "profitability"), _score("np_growth", "Tăng trưởng lợi nhuận", .20, gt, 0, "profitability"), _score("roe", "ROE", .15, gt, 0, "profitability"), _score("cfo", "CFO TTM", .15, gt, 0, "cash_flow"), _score("cargo_volume", "Sản lượng", .10, gt, 0, "operations"), _score("capacity_utilization", "Công suất sử dụng", .10, gt, 0, "operations"), _score("freight_rate", "Giá cước", .05, gt, 0, "operations"), _score("debt_to_equity", "Nợ/VCSH", .05, le, 2, "risk"), _score("dividend", "Cổ tức", .05, gt, 0, "profitability"))
SeafoodFilter.scoring_rules = (
    _score("rev_growth", "Tăng trưởng doanh thu", .15, gt, 0, "profitability"), _score("np_growth", "Tăng trưởng lợi nhuận", .20, gt, 0, "profitability"), _score("roe", "ROE", .15, gt, 0, "profitability"), _score("gross_margin", "Biên lợi nhuận gộp", .15, gt, 0, "profitability"), _score("cfo", "CFO TTM", .10, gt, 0, "cash_flow"), _score("export_growth", "Tăng trưởng xuất khẩu", .10, gt, 0, "operations"), _score("selling_price", "Giá bán", .05, gt, 0, "operations"), _score("debt_to_equity", "Nợ/VCSH", .05, le, 2, "risk"), _score("inventory", "Tồn kho", .05, le, 0, "operations"))
TextileFilter.scoring_rules = (
    _score("rev_growth", "Tăng trưởng doanh thu", .15, gt, 0, "profitability"), _score("np_growth", "Tăng trưởng lợi nhuận", .20, gt, 0, "profitability"), _score("roe", "ROE", .15, gt, 0, "profitability"), _score("gross_margin", "Biên lợi nhuận gộp", .15, gt, 0, "profitability"), _score("cfo", "CFO TTM", .10, gt, 0, "cash_flow"), _score("backlog", "Đơn hàng / Backlog", .10, gt, 0, "operations"), _score("capacity_utilization", "Công suất sử dụng", .05, gt, 0, "operations"), _score("debt_to_equity", "Nợ/VCSH", .05, le, 2, "risk"))
FoodBeverageFilter.scoring_rules = (
    _score("rev_growth", "Tăng trưởng doanh thu", .20, gt, 0, "profitability"), _score("np_growth", "Tăng trưởng lợi nhuận", .20, gt, 0, "profitability"), _score("roe", "ROE", .15, gt, 0, "profitability"), _score("gross_margin", "Biên lợi nhuận gộp", .15, gt, 0, "profitability"), _score("cfo", "CFO TTM", .10, gt, 0, "cash_flow"), _score("market_share", "Thị phần", .05, gt, 0, "operations"), _score("volume_growth", "Tăng trưởng sản lượng", .05, gt, 0, "operations"), _score("debt_to_equity", "Nợ/VCSH", .05, le, 2, "risk"), _score("inventory", "Tồn kho", .05, le, 0, "operations"))
PharmaceuticalFilter.scoring_rules = (
    _score("rev_growth", "Tăng trưởng doanh thu", .15, gt, 0, "profitability"), _score("np_growth", "Tăng trưởng lợi nhuận", .20, gt, 0, "profitability"), _score("roe", "ROE", .15, ge, .10, "profitability"), _score("gross_margin", "Biên lợi nhuận gộp", .15, gt, 0, "profitability"), _score("cfo", "CFO TTM", .10, gt, 0, "cash_flow"), _score("eps_growth", "Tăng trưởng EPS", .10, gt, 0, "profitability"), _score("rd_quality", "R&D", .05, gt, 0, "operations"), _score("debt_to_equity", "Nợ/VCSH", .05, le, 1.5, "risk"))
ConstructionFilter.scoring_rules = (
    _score("backlog", "Backlog", .20, gt, 0, "operations"), _score("rev_growth", "Tăng trưởng doanh thu", .15, gt, 0, "profitability"), _score("np_growth", "Tăng trưởng lợi nhuận", .15, gt, 0, "profitability"), _score("roe", "ROE", .10, gt, 0, "profitability"), _score("cfo", "CFO TTM", .15, ge, 0, "cash_flow"), _score("gross_margin", "Biên lợi nhuận gộp", .10, gt, 0, "profitability"), _score("debt_to_equity", "Nợ/VCSH", .05, le, 2.5, "risk"), _score("book_to_bill", "Book-to-bill", .05, gt, 0, "operations"))
IndustrialParkFilter.scoring_rules = (
    _score("occupancy_rate", "Tỷ lệ lấp đầy", .20, gt, 0, "operations"), _score("leased_area_growth", "Tăng trưởng diện tích thuê", .15, gt, 0, "operations"), _score("rev_growth", "Tăng trưởng doanh thu", .15, gt, 0, "profitability"), _score("np_growth", "Tăng trưởng lợi nhuận", .15, gt, 0, "profitability"), _score("roe", "ROE", .10, gt, 0, "profitability"), _score("cfo", "CFO TTM", .10, ge, 0, "cash_flow"), _score("rental_price_growth", "Tăng trưởng giá thuê", .05, gt, 0, "operations"), _score("debt_to_equity", "Nợ/VCSH", .05, le, 2.5, "risk"), _score("backlog", "Backlog", .05, gt, 0, "operations"))
InsuranceFilter.scoring_rules = (
    _score("premium_growth", "Tăng trưởng phí", .15, gt, 0, "profitability"), _score("np_growth", "Tăng trưởng lợi nhuận", .20, gt, 0, "profitability"), _score("roe", "ROE", .15, ge, .08, "profitability"), _score("combined_ratio", "Combined Ratio", .15, le, 1, "insurance_quality"), _score("investment_yield", "Lợi suất đầu tư", .10, gt, 0, "insurance_quality"), _score("cfo", "CFO TTM", .10, gt, 0, "cash_flow"), _score("solvency_ratio", "Solvency", .10, ge, 1, "insurance_quality"), _score("dividend", "Cổ tức", .05, gt, 0, "profitability"))
