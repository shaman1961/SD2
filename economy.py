from enum import Enum
from typing import List, Dict

# === КОНСТАНТЫ ТЕХНОЛОГИЙ ===
TECH_BASE_COSTS = {
    "economy": {"wheat": 10, "wood": 5},
    "army": {"metal": 12, "coal": 6},
    "logistics": {"wood": 10, "oil": 6}
}
TECH_BASE_TURNS = 4
TECH_TURNS_REDUCTION_PER_PACK = 1  # 1 доп. пакет ресурсов = -1 ход
TECH_MAX_LEVEL = 8
# ============================

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

        self.wheat_progress = 0.0
        self.metal_progress = 0.0
        self.wood_progress = 0.0
        self.coal_progress = 0.0
        self.oil_progress = 0.0

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
        """
        Расчет добычи ресурсов с накоплением (таймерами).
        1 ур = 1 ед. за 3 хода (0.33/ход)
        2 ур = 1 ед. за 2 хода (0.5/ход)
        3 ур = 1 ед. за 1 ход (1.0/ход)
        4 ур = 2 ед. за 1 ход (2.0/ход)
        """
        # Маппинг ресурсов (с запасом на пробелы из JSON)
        res_map = {
            "Пшеница": 'wheat', "Пшеница ": 'wheat',
            "Металл": 'metal', "Металл ": 'metal',
            "Дерево": 'wood', "Дерево ": 'wood',
            "Уголь": 'coal', "Уголь ": 'coal',
            "Нефть": 'oil', "Нефть ": 'oil'
        }

        # 1. Группируем провинции по ресурсам и уровням: {'wheat': {1: 5, 2: 3}, ...}
        dist = {}
        for prov in provinces_data:
            res_raw = prov.get('resource', '-')
            level = prov.get('level', 1)
            res_key = res_map.get(res_raw)  # Ищем в маппинге

            if res_key:
                if res_key not in dist:
                    dist[res_key] = {}
                dist[res_key][level] = dist[res_key].get(level, 0) + 1

        # 2. Рассчитываем добычу и обновляем прогресс
        production_rates = {
            1: 0.3333,  # 1 ед за 3 хода
            2: 0.5,  # 1 ед за 2 хода
            3: 1.0,  # 1 ед за 1 ход
            4: 2.0  # 2 ед за 1 ход (и выше)
        }

        for res_key, levels in dist.items():
            prod_per_turn = 0.0
            for lvl, count in levels.items():
                rate = production_rates.get(lvl, 2.0)
                prod_per_turn += (rate * count)

            # Добавляем к текущему прогрессу
            current_progress = getattr(self, f"{res_key}_progress", 0.0)
            new_progress = current_progress + prod_per_turn

            # Если накопили целое число ресурсов — выдаем их
            amount_produced = int(new_progress)
            if amount_produced > 0:
                setattr(self, res_key, getattr(self, res_key, 0) + amount_produced)
                setattr(self, f"{res_key}_progress", new_progress - amount_produced)  # Оставляем остаток
            else:
                setattr(self, f"{res_key}_progress", new_progress)

        # Начисляем золото (как раньше)
        province_level_sum = sum(prov.get('level', 1) for prov in provinces_data)
        self.gold += self.calculate_gold_income(province_level_sum)

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

    def can_pay_tech(self, branch: str, next_level: int, packs: int = 1) -> bool:
        """Проверка, хватает ли ресурсов на пакет исследования"""
        if branch not in TECH_BASE_COSTS:
            return False
        base = TECH_BASE_COSTS[branch]
        # Стоимость растёт линейно с уровнем
        multiplier = next_level
        for res, amount in base.items():
            needed = amount * multiplier * packs
            if getattr(self, res, 0) < needed:
                return False
        return True

    def pay_tech(self, branch: str, next_level: int, packs: int = 1) -> bool:
        """Списание ресурсов за исследование"""
        if not self.can_pay_tech(branch, next_level, packs):
            return False
        base = TECH_BASE_COSTS[branch]
        multiplier = next_level
        for res, amount in base.items():
            setattr(self, res, getattr(self, res, 0) - (amount * multiplier * packs))
        return True

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
            'army_count': self.army_count,
            'wheat_progress': self.wheat_progress,
            'metal_progress': self.metal_progress,
            'wood_progress': self.wood_progress,
            'coal_progress': self.coal_progress,
            'oil_progress': self.oil_progress
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