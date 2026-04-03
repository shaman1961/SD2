from economy import Economy, ResourceType
from typing import List, Optional

class Country:
    def __init__(self, name: str, color: List[int], resources_list: List[str],
                 wheat: int = 0, metal: int = 0, wood: int = 0,
                 coal: int = 0, oil: int = 0, provinces: Optional[List[str]] = None,
                 capital: Optional[str] = None, gold: int = 100):
        self.country = name
        self.color = color
        self.resources_list = resources_list
        self.provinces = provinces if provinces else []
        self.capital = capital
        # === НОВАЯ ЭКОНОМИКА ===
        self.economy = Economy(country_name=name, starting_gold=gold)

        # Конвертация старых ресурсов в золото (для обратной совместимости)
        self._migrate_old_resources(wheat, metal, wood, coal, oil)

    def _migrate_old_resources(self, wheat: int, metal: int, wood: int,
                               coal: int, oil: int) -> None:
        """Конвертация старой системы ресурсов в новую"""
        total_old = wheat + metal + wood + coal + oil
        if total_old > 0:
            self.economy.gold += total_old * 10

        self.economy.wheat_income = wheat
        self.economy.metal_income = metal
        self.economy.wood_income = wood
        self.economy.coal_income = coal
        self.economy.oil_income = oil

    def end_turn(self, provinces_data: list) -> None:
        """Завершение хода: начисление ресурсов от провинций"""
        self.economy.add_resources_from_provinces(provinces_data)

    # === Методы для game.py ===
    def buy_army(self, count: int = 1) -> bool:
        return self.economy.buy_army(count)

    def can_buy_army(self, count: int = 1) -> bool:
        return self.economy.can_buy_army(count)

    def invest(self, resource_name: str) -> bool:
        mapping = {
            'Пшеница': ResourceType.WHEAT,
            'Металл': ResourceType.METAL,
            'Дерево': ResourceType.WOOD,
            'Уголь': ResourceType.COAL,
            'Нефть': ResourceType.OIL
        }
        res_type = mapping.get(resource_name)
        if res_type:
            return self.economy.invest(res_type)
        return False

    def can_invest(self, resource_name: str) -> bool:
        mapping = {
            'Пшеница': ResourceType.WHEAT,
            'Металл': ResourceType.METAL,
            'Дерево': ResourceType.WOOD,
            'Уголь': ResourceType.COAL,
            'Нефть': ResourceType.OIL
        }
        res_type = mapping.get(resource_name)
        if res_type:
            return self.economy.can_invest(res_type)
        return False

    def get_investment_bonus(self, resource_name: str) -> str:
        mapping = {
            'Пшеница': ResourceType.WHEAT,
            'Металл': ResourceType.METAL,
            'Дерево': ResourceType.WOOD,
            'Уголь': ResourceType.COAL,
            'Нефть': ResourceType.OIL
        }
        res_type = mapping.get(resource_name)
        if res_type:
            return self.economy.get_investment_bonus_text(res_type)
        return ""

    def level_up_province(self) -> bool:
        return self.economy.level_up_province()

    def can_level_up_province(self) -> bool:
        return self.economy.can_level_up_province()

    # === Геттеры для интерфейса ===
    def get_gold(self) -> int:
        return self.economy.gold

    def get_army_count(self) -> int:
        return self.economy.army_count

    def get_resource(self, name: str) -> int:
        return getattr(self.economy, name.lower(), 0)

    def get_income(self, resource_name: str) -> int:
        mapping = {
            'Пшеница': ResourceType.WHEAT,
            'Металл': ResourceType.METAL,
            'Дерево': ResourceType.WOOD,
            'Уголь': ResourceType.COAL,
            'Нефть': ResourceType.OIL
        }
        res_type = mapping.get(resource_name)
        if res_type:
            return self.economy.get_resource_income(res_type)
        return 0

    def get_invest_level(self, resource_name: str) -> int:
        # Маппинг русских названий на английские атрибуты
        mapping = {
            'Пшеница': 'wheat',
            'Металл': 'metal',
            'Дерево': 'wood',
            'Уголь': 'coal',
            'Нефть': 'oil'
        }
        eng_name = mapping.get(resource_name, resource_name.lower())
        return getattr(self.economy, f"{eng_name}_invest", 0)

    # === Сериализация ===
    def to_dict(self) -> dict:
        return {
            'country': self.country,
            'color': self.color,
            'capital': self.capital,
            'provinces': self.provinces,
            'economy': self.economy.to_dict()
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Country':
        economy_data = data.get('economy', {})
        country = cls(
            name=data.get('country', ''),
            color=data.get('color', [0, 0, 0]),
            resources_list=data.get('resources_list', []),
            wheat=economy_data.get('wheat', 0),
            metal=economy_data.get('metal', 0),
            wood=economy_data.get('wood', 0),
            coal=economy_data.get('coal', 0),
            oil=economy_data.get('oil', 0),
            provinces=data.get('provinces', []),
            capital=data.get('capital', ''),
            gold=economy_data.get('gold', 100)
        )
        country.economy = Economy.from_dict(economy_data)
        return country