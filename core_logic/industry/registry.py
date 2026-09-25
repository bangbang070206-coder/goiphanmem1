from typing import Dict, Optional

from .base import IndustryFilter
from .filters import (
    BankingFilter, ChemicalFilter, ConstructionFilter, ElectricityFilter,
    FoodBeverageFilter, GenericIndustryFilter, IndustrialParkFilter,
    InsuranceFilter, OilGasFilter, PharmaceuticalFilter, RealEstateFilter,
    RetailFilter, SeafoodFilter, SecuritiesFilter, SoftwareFilter, SteelFilter,
    TextileFilter, TransportPortFilter,
)

INDUSTRY_FILTERS: Dict[str, IndustryFilter] = {
    "banking": BankingFilter(),
    "securities": SecuritiesFilter(),
    "real_estate": RealEstateFilter(),
    "steel": SteelFilter(),
    "oil_gas": OilGasFilter(),
    "electricity": ElectricityFilter(),
    "retail": RetailFilter(),
    "chemical": ChemicalFilter(),
    "transport_port": TransportPortFilter(),
    "seafood": SeafoodFilter(),
    "textile": TextileFilter(),
    "food_beverage": FoodBeverageFilter(),
    "pharmaceuticals": PharmaceuticalFilter(),
    "construction": ConstructionFilter(),
    "industrial_parks": IndustrialParkFilter(),
    "insurance": InsuranceFilter(),
    "software": SoftwareFilter(),
    "generic": GenericIndustryFilter(),
}

INDUSTRY_LABELS = {
    "banking": "Ngân hàng",
    "securities": "Chứng khoán",
    "real_estate": "Bất động sản",
    "steel": "Thép",
    "oil_gas": "Dầu khí",
    "electricity": "Điện",
    "retail": "Bán lẻ",
    "chemical": "Hóa chất",
    "transport_port": "Vận tải / Cảng biển",
    "seafood": "Thủy sản",
    "textile": "Dệt may",
    "food_beverage": "Thực phẩm / Đồ uống",
    "pharmaceuticals": "Dược phẩm",
    "construction": "Xây dựng",
    "industrial_parks": "Khu công nghiệp",
    "insurance": "Bảo hiểm",
    "software": "Phần mềm / Công nghệ",
    "generic": "Ngành khác",
}


def get_industry_filter(code: str) -> Optional[IndustryFilter]:
    return INDUSTRY_FILTERS.get(code)


def list_industries():
    return [{"code": code, "name": name} for code, name in INDUSTRY_LABELS.items()]


def evaluate_industry(code: str, metrics: dict) -> dict:
    if not code:
        return {
            "industry_code": None,
            "industry_name": "Chưa xác định",
            "is_passed": False,
            "status": "INDUSTRY_UNKNOWN",
            "score": None,
            "groups": {},
            "reasons": ["Chưa có phân loại ngành từ nguồn dữ liệu"],
            "missing_metrics": [],
        }
    industry_filter = get_industry_filter(code)
    if industry_filter is None:
        return {
            "industry_code": code,
            "industry_name": "Không hỗ trợ",
            "is_passed": False,
            "status": "INDUSTRY_UNKNOWN",
            "score": None,
            "groups": {},
            "reasons": [f"Mã ngành không được hỗ trợ: {code}"],
            "missing_metrics": [],
        }
    return industry_filter.evaluate(metrics or {})
