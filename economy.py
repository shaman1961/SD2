from enum import Enum
from typing import List, Dict

class ResourceType(Enum):
    """Типы ресурсов"""
    WHEAT = "Пшеница"
    METAL = "Металл"
    WOOD = "Дерево"
    COAL = "Уголь"
    OIL = "Нефть"

class Economy:
    """
    Экономическая система страны.
    Армия покупается за золото, ресурсы конвертируются в доход.
    """
    # === БАЛАНС (можно менять) ===
    ARMY_COST = 50  # Золота за 1 армию
    INVESTMENT_COST = 100  # Золота за 1 уровень инвестиции
    LEVEL_UP_GOLD_COST = 50  # Золота за прокачку провинции
    MAX_INVESTMENT_LEVEL = 3  # Макс уровень инвестиции
    INVESTMENT_BONUS_PER_LEVEL = 0.5  # +50% дохода за уровень
    # ================================

    def __init__(self, country_name: str = "", starting_gold: int = 100):
        self.country_name = country_name
        self.gold = starting_gold

        # Ресурсы (накопленные)
        self.wheat = 0
        self.metal = 0
        self.wood = 0
        self.coal = 0
        self.oil = 0

        # Доход за ход (базовый, от провинций)
        self.wheat_income = 0
        self.metal_income = 0
        self.wood_income = 0
        self.coal_income = 0
        self.oil_income = 0

        # Уровни инвестиций (0-3)
        self.wheat_invest = 0
        self.metal_invest = 0
        self.wood_invest = 0
        self.coal_invest = 0
        self.oil_invest = 0

        # Армии
        self.army_count = 0

    def get_resource_income(self, resource_type: ResourceType) -> int:
        """Рассчитать доход ресурса с учётом инвестиций"""
        # Маппинг русских названий на английские атрибуты
        resource_mapping = {
            ResourceType.WHEAT: 'wheat',
            ResourceType.METAL: 'metal',
            ResourceType.WOOD: 'wood',
            ResourceType.COAL: 'coal',
            ResourceType.OIL: 'oil'
        }

        resource_name = resource_mapping.get(resource_type)
        if not resource_name:
            return 0

        base_income = getattr(self, f"{resource_name}_income", 0)
        invest_level = getattr(self, f"{resource_name}_invest", 0)
        multiplier = 1 + (invest_level * self.INVESTMENT_BONUS_PER_LEVEL)
        return int(base_income * multiplier)

    def calculate_gold_income(self, province_level_sum: int) -> int:
        """Рассчитать доход золота от провинций"""
        return province_level_sum * 2

    def add_resources_from_provinces(self, provinces_data: List[Dict]) -> None:
        """Начислить ресурсы от провинций (вызывать каждый ход)"""
        # Сбрасываем базовый доход
        self.wheat_income = 0
        self.metal_income = 0
        self.wood_income = 0
        self.coal_income = 0
        self.oil_income = 0

        province_level_sum = 0

        for prov in provinces_data:
            level = prov.get('level', 1)
            resource = prov.get('resource', '-')

            province_level_sum += level

            if resource == "Пшеница":
                self.wheat_income += level
            elif resource == "Металл":
                self.metal_income += level
            elif resource == "Дерево":
                self.wood_income += level
            elif resource == "Уголь":
                self.coal_income += level
            elif resource == "Нефть":
                self.oil_income += level

        # Начисляем золото
        gold_income = self.calculate_gold_income(province_level_sum)
        self.gold += gold_income

        # Начисляем ресурсы с учётом инвестиций
        resource_mapping = {
            ResourceType.WHEAT: 'wheat',
            ResourceType.METAL: 'metal',
            ResourceType.WOOD: 'wood',
            ResourceType.COAL: 'coal',
            ResourceType.OIL: 'oil'
        }

        for res_type in ResourceType:
            income = self.get_resource_income(res_type)
            resource_name = resource_mapping.get(res_type)
            if resource_name:
                current = getattr(self, resource_name, 0)
                setattr(self, resource_name, current + income)

    def can_buy_army(self, count: int = 1) -> bool:
        return self.gold >= (count * self.ARMY_COST)

    def buy_army(self, count: int = 1) -> bool:
        total_cost = count * self.ARMY_COST
        if self.can_buy_army(count):
            self.gold -= total_cost
            self.army_count += count
            return True
        return False

    # === ДОБАВИТЬ в класс Economy (после buy_army) ===
    def spend_gold(self, amount: int) -> bool:
        """Потратить золото (для перемещения армии)"""
        if self.gold >= amount:
            self.gold -= amount
            return True
        return False

    def can_invest(self, resource_type: ResourceType) -> bool:
        # Маппинг русских названий на английские атрибуты
        resource_mapping = {
            ResourceType.WHEAT: 'wheat',
            ResourceType.METAL: 'metal',
            ResourceType.WOOD: 'wood',
            ResourceType.COAL: 'coal',
            ResourceType.OIL: 'oil'
        }

        resource_name = resource_mapping.get(resource_type)
        if not resource_name:
            return False

        current_invest = getattr(self, f"{resource_name}_invest", 0)
        return (self.gold >= self.INVESTMENT_COST and
                current_invest < self.MAX_INVESTMENT_LEVEL)

    def invest(self, resource_type: ResourceType) -> bool:
        if not self.can_invest(resource_type):
            return False

        # Маппинг русских названий на английские атрибуты
        resource_mapping = {
            ResourceType.WHEAT: 'wheat',
            ResourceType.METAL: 'metal',
            ResourceType.WOOD: 'wood',
            ResourceType.COAL: 'coal',
            ResourceType.OIL: 'oil'
        }

        resource_name = resource_mapping.get(resource_type)
        if not resource_name:
            return False

        self.gold -= self.INVESTMENT_COST
        current = getattr(self, f"{resource_name}_invest", 0)
        setattr(self, f"{resource_name}_invest", current + 1)
        return True

    def can_level_up_province(self) -> bool:
        return self.gold >= self.LEVEL_UP_GOLD_COST

    def level_up_province(self) -> bool:
        if self.can_level_up_province():
            self.gold -= self.LEVEL_UP_GOLD_COST
            return True
        return False

    def get_investment_bonus_text(self, resource_type: ResourceType) -> str:
        # Маппинг русских названий на английские атрибуты
        resource_mapping = {
            ResourceType.WHEAT: 'wheat',
            ResourceType.METAL: 'metal',
            ResourceType.WOOD: 'wood',
            ResourceType.COAL: 'coal',
            ResourceType.OIL: 'oil'
        }

        resource_name = resource_mapping.get(resource_type)
        if not resource_name:
            return ""

        level = getattr(self, f"{resource_name}_invest", 0)
        next_bonus = int((level + 1) * self.INVESTMENT_BONUS_PER_LEVEL * 100)
        return f"+{next_bonus}% к добыче"

    # === Сериализация ===
    def to_dict(self) -> dict:
        return {
            'country_name': self.country_name,
            'gold': self.gold,
            'wheat': self.wheat,
            'metal': self.metal,
            'wood': self.wood,
            'coal': self.coal,
            'oil': self.oil,
            'wheat_income': self.wheat_income,
            'metal_income': self.metal_income,
            'wood_income': self.wood_income,
            'coal_income': self.coal_income,
            'oil_income': self.oil_income,
            'wheat_invest': self.wheat_invest,
            'metal_invest': self.metal_invest,
            'wood_invest': self.wood_invest,
            'coal_invest': self.coal_invest,
            'oil_invest': self.oil_invest,
            'army_count': self.army_count
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Economy':
        econ = cls()
        econ.country_name = data.get('country_name', '')
        econ.gold = data.get('gold', 100)
        econ.wheat = data.get('wheat', 0)
        econ.metal = data.get('metal', 0)
        econ.wood = data.get('wood', 0)
        econ.coal = data.get('coal', 0)
        econ.oil = data.get('oil', 0)
        econ.wheat_income = data.get('wheat_income', 0)
        econ.metal_income = data.get('metal_income', 0)
        econ.wood_income = data.get('wood_income', 0)
        econ.coal_income = data.get('coal_income', 0)
        econ.oil_income = data.get('oil_income', 0)
        econ.wheat_invest = data.get('wheat_invest', 0)
        econ.metal_invest = data.get('metal_invest', 0)
        econ.wood_invest = data.get('wood_invest', 0)
        econ.coal_invest = data.get('coal_invest', 0)
        econ.oil_invest = data.get('oil_invest', 0)
        econ.army_count = data.get('army_count', 0)
        return econ