import json
import os
from datetime import datetime

SAVE_FILE = "savegame.json"
SAVE_VERSION = "2.0"

def save_game(game):
    """Сохранение игры - ТОЛЬКО в savegame.json (оригиналы JSON не трогаем!)"""
    # Собираем владельцев провинций
    province_owners = {}
    for prov in game.all_provinces:
        province_owners[prov.name] = [prov.color[0], prov.color[1], prov.color[2]]

    # Сохраняем позиции армий
    army_positions_str = {str(pos): moved for pos, moved in game.army_positions.items()}

    # === НОВАЯ ЭКОНОМИКА ===
    economy_data = None

    if hasattr(game, 'player_country') and hasattr(game.player_country, 'economy'):
        economy_data = game.player_country.economy.to_dict()
    # =====================

    # === УРОВНИ ПРОВИНЦИЙ ===
    province_levels = {}
    for prov in game.all_provinces:
        province_levels[prov.name] = prov.level
    # ========================

    save_data = {
        "version": SAVE_VERSION,
        "year": game.year,
        "country": game.country,
        "turn": game.turn,
        "army_positions": army_positions_str,
        "province_owners": province_owners,
        "province_levels": province_levels,
        "player_economy": economy_data,
        "saved_at": datetime.now().isoformat()
    }

    # ← Сохраняем ТОЛЬКО в savegame.json
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)

    print(f"💾 Игра сохранена (версия {SAVE_VERSION})")

def load_game():
    """Загрузка игры"""
    if not os.path.exists(SAVE_FILE):
        return None
    with open(SAVE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def has_save():
    """Проверка наличия сохранения"""
    return os.path.exists(SAVE_FILE)

def delete_save():
    """Удалить сохранение игры"""
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)
        print("🗑️ Сохранение удалено")
        return True
    return False

def apply_save_to_game(game, save_data):
    """Применение сохранения к игре - из savegame.json в память (НЕ в JSON файлы!)"""
    game.turn = save_data.get("turn", 0)

    # Загрузка позиций армий
    game.army_positions = {}
    for pos_str, moved in save_data.get("army_positions", {}).items():
        try:
            # pos_str имеет формат "(100.5, 200.3)" — убираем скобки ()
            clean = pos_str.strip("()")
            parts = clean.split(",")
            if len(parts) == 2:
                x = float(parts[0].strip())
                y = float(parts[1].strip())
                game.army_positions[(x, y)] = moved
        except (ValueError, AttributeError, KeyError):
            # Если не удалось распарсить — пропускаем (без падения)
            pass

    # Восстановление владельцев провинций (в памяти, НЕ в JSON!)
    for prov in game.all_provinces:
        if prov.name in save_data.get("province_owners", {}):
            r, g, b = save_data["province_owners"][prov.name]
            prov.color = (int(r), int(g), int(b))

    # === ВОССТАНОВЛЕНИЕ УРОВНЕЙ ПРОВИНЦИЙ ===
    for prov in game.all_provinces:
        if prov.name in save_data.get("province_levels", {}):
            prov.level = save_data["province_levels"][prov.name]
    # =========================================

    # === НОВАЯ ЭКОНОМИКА ===
    # Загрузка экономики игрока
    if save_data.get("player_economy") and hasattr(game, 'player_country'):
        from economy import Economy
        game.player_country.economy = Economy.from_dict(save_data["player_economy"])
        print(f"✅ Экономика загружена: {game.player_country.get_gold()} золота")
    # =====================

    print(f"✅ Сохранение загружено (ход {game.turn})")