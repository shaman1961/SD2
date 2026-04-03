import os
from datetime import datetime

STATS_FILE = "game_stats.txt"


def load_stats():
    if not os.path.exists(STATS_FILE):
        return {"turns": 0, "reinforcements": 0, "conquered": 0, "last_update": ""}

    stats = {"turns": 0, "reinforcements": 0, "conquered": 0, "last_update": ""}
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("Общее количество ходов:"):
                stats["turns"] = int(line.split(":")[1].strip())
            elif line.startswith("Заказано подкреплений:"):
                stats["reinforcements"] = int(line.split(":")[1].strip())
            elif line.startswith("Захвачено провинций:"):
                stats["conquered"] = int(line.split(":")[1].strip())
            elif line.startswith("Последнее обновление:"):
                stats["last_update"] = line.split(": ", 1)[1].strip()

    return stats


def save_stats(stats):
    stats["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content = f"""=== STEEL DAWN — ПЕРСОНАЛЬНАЯ СТАТИСТИКА ===
Общее количество ходов: {stats['turns']}
Заказано подкреплений: {stats['reinforcements']}
Захвачено провинций: {stats['conquered']}
Последнее обновление: {stats['last_update']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Статистика накапливается между всеми сессиями игры.
"""
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        f.write(content)


def increment_turns(n=1):
    stats = load_stats()
    stats["turns"] += n
    save_stats(stats)


def increment_reinforcements(n=1):
    stats = load_stats()
    stats["reinforcements"] += n
    save_stats(stats)


def increment_conquered(n=1):
    stats = load_stats()
    stats["conquered"] += n
    save_stats(stats)


def get_stats():
    return load_stats()