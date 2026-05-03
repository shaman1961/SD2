"""
Контроллер ИИ (работает с именами провинций)
Поддерживает множественные дивизии в провинции
"""
import random
from neighbors import province_neighbors

class AIController:
    """Контроллер для одной страны-бота"""
    def __init__(self, country_name: str, country_data: dict, provinces_data: dict,
                 player_country_name: str, all_armies: dict):
        self.country_name = country_name
        self.country_data = country_data
        self.provinces_data = provinces_data
        self.player_country_name = player_country_name
        self.all_armies = all_armies

        self.gold = country_data.get('gold', 100)
        self.provinces = country_data.get('provinces', [])
        self.color = country_data.get('color', [0, 0, 0])

        self.armies = []
        self.army_counts = {}

        for name, info in all_armies.items():
            if isinstance(info, dict):
                owner = info.get("owner")
                count = info.get("count", 1)
            else:
                owner = info
                count = 1

            if owner == country_name:
                self.armies.append(name)
                self.army_counts[name] = count

    def make_move(self, game=None) -> dict:
        """
        Сделать ход бота.
        Приоритеты:
        1. Купить армию в своей провинции (50 золота)
        2. Атаковать соседа если есть преимущество
        3. Инвестировать в ресурс (100 золота)
        """
        result = {
            'bought_army': False,
            'moved_army': False,
            'conquered': None,
            'invested': None,
            'gold_spent': 0
        }

        if self.gold >= 50 and self.provinces:
            for prov_name in self.provinces:
                info = self.all_armies.get(prov_name, {"owner": None, "count": 0})

                if isinstance(info, dict):
                    owner = info.get("owner")
                    count = info.get("count", 0)
                else:
                    owner = info
                    count = 1 if info else 0

                if owner == self.country_name:
                    if isinstance(info, dict):
                        info["count"] = count + 1
                    else:
                        self.all_armies[prov_name] = {"owner": self.country_name, "count": count + 1}

                    self.army_counts[prov_name] = self.army_counts.get(prov_name, 0) + 1
                    if prov_name not in self.armies:
                        self.armies.append(prov_name)

                elif owner is None or owner != self.country_name:
                    self.all_armies[prov_name] = {"owner": self.country_name, "count": 1}
                    self.armies.append(prov_name)
                    self.army_counts[prov_name] = 1

                self.gold -= 50
                result['bought_army'] = True
                result['gold_spent'] += 50
                break

        if self.armies:
            attack_order = sorted(self.armies, key=lambda p: self.army_counts.get(p, 0), reverse=True)
            for army_prov in attack_order:
                my_count = self.army_counts.get(army_prov, 1)
                neighbors = province_neighbors.get(army_prov, [])
                random.shuffle(neighbors)

                for neighbor_name in neighbors:
                    neighbor_info = self.all_armies.get(neighbor_name, {"owner": None, "count": 0})

                    if isinstance(neighbor_info, dict):
                        neighbor_owner = neighbor_info.get("owner")
                        neighbor_count = neighbor_info.get("count", 0)
                    else:
                        neighbor_owner = neighbor_info
                        neighbor_count = 1 if neighbor_info else 0

                    if neighbor_owner and neighbor_owner != self.country_name:
                        if my_count > neighbor_count:
                            losses = max(0, int(neighbor_count * 0.7))
                            survivors = max(1, my_count - losses)

                            self.all_armies[neighbor_name] = {
                                "owner": self.country_name,
                                "count": survivors
                            }
                            self.army_counts[neighbor_name] = survivors

                            if army_prov in self.all_armies:
                                del self.all_armies[army_prov]
                            self.armies.remove(army_prov)
                            if army_prov in self.army_counts:
                                del self.army_counts[army_prov]

                            if neighbor_owner == self.player_country_name:
                                result['conquered'] = neighbor_name

                            if neighbor_name not in self.provinces:
                                self.provinces.append(neighbor_name)

                            result['moved_army'] = True
                            break

                        elif my_count == neighbor_count:
                            if army_prov in self.all_armies:
                                del self.all_armies[army_prov]
                            self.armies.remove(army_prov)
                            if army_prov in self.army_counts:
                                del self.army_counts[army_prov]

                            if neighbor_name in self.all_armies:
                                del self.all_armies[neighbor_name]

                            result['moved_army'] = True
                            break


        if self.gold >= 100 and not result['bought_army'] and not result['moved_army']:
            resources = ['wheat', 'metal', 'wood', 'coal', 'oil']
            chosen_resource = random.choice(resources)
            self.gold -= 100
            result['invested'] = chosen_resource
            result['gold_spent'] += 100

        self.country_data['gold'] = self.gold

        return result


def get_bot_countries(year: int, player_country: str) -> list:
    """Получить список стран-ботов для сценария"""
    import json
    with open(f"countries{year}.json", "r", encoding="utf-8") as f:
        countries_data = json.load(f)

    bot_countries = [
        name for name in countries_data.keys()
        if name != player_country
    ]
    bot_countries.sort()
    return bot_countries
