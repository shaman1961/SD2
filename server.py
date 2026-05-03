from flask import Flask, request, jsonify
from flask_cors import CORS
import time, random, json, os
from datetime import datetime
from threading import Thread, Lock, Timer

app = Flask(__name__)
CORS(app)

SECRET = "SteelDawn2024"
PORT = 5443
TURN_TIME = 180
MAX_P = 8
MIN_P = 2
COUNTDOWN = 10
PLAYERS_FILE = "players.json"
ARMY_COST = 50
LEVEL_UP_COST = 50
MOVE_COST = 25


def load_map_data():
    map_data = {}
    for year in [1938, 1941]:
        try:
            with open(f"provinces{year}.json", "r", encoding="utf-8") as f:
                provinces = json.load(f)
            with open(f"countries{year}.json", "r", encoding="utf-8") as f:
                countries = json.load(f)
            neighbors = {}
            try:
                with open("neighbors.py", "r", encoding="utf-8") as f:
                    exec(f.read(), globals())
                    neighbors = globals().get('province_neighbors', {})
            except:
                pass
            map_data[year] = {'provinces': provinces, 'countries': countries, 'neighbors': neighbors}
        except Exception as e:
            print(f"⚠️ Map {year}: {e}")
    return map_data


MAP_DATA = load_map_data()
games, players, lock = {}, {}, Lock()


def save_players():
    try:
        data = {pid: {'id': p['id'], 'name': p['name'], 'created_at': p['created_at']} for pid, p in players.items()}
        with open(PLAYERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass


def load_players():
    try:
        if os.path.exists(PLAYERS_FILE):
            with open(PLAYERS_FILE, 'r', encoding='utf-8') as f:
                for pid, pdata in json.load(f).items():
                    players[pid] = {'id': pid, 'name': pdata['name'], 'created_at': pdata.get('created_at', ''),
                                    'current_game': None}
    except:
        pass


def gen_id(): return f"{int(time.time())}_{random.randint(1000, 9999)}"


def ts(): return datetime.now().isoformat()


def check_auth(): return (request.get_json(silent=True) or {}).get('secret_code') == SECRET


def init_game_state(year, players_list):
    map_info = MAP_DATA.get(year, {})
    countries_data = map_info.get('countries', {})
    province_owners = {prov: country for country, data in countries_data.items() for prov in data.get('provinces', [])}
    economies = {pid: {'gold': 100, 'wheat': 0, 'metal': 0, 'wood': 0, 'coal': 0, 'oil': 0, 'army_count': 0} for pid in
                 players_list}
    return {'province_owners': province_owners, 'economies': economies, 'armies': {}, 'province_levels': {}}


def get_army_info(armies_dict, position):
    """Получить информацию об армии в провинции: (owner, count)"""
    info = armies_dict.get(position)
    if not info:
        return None, 0
    if isinstance(info, dict):
        return info.get("owner"), info.get("count", 1)
    else:
        return info, 1


def set_army_info(armies_dict, position, owner, count):
    """Установить информацию об армии"""
    if count > 0:
        armies_dict[position] = {"owner": owner, "count": count}
    elif position in armies_dict:
        del armies_dict[position]


def handle_buy_army(game, pid, position):
    state = game['map_state']
    econ = state['economies'].get(pid, {})

    if econ.get('gold', 0) < ARMY_COST:
        return {'success': False, 'error': 'Недостаточно золота'}

    if state['province_owners'].get(position) != game['countries'].get(pid):
        return {'success': False, 'error': 'Провинция не ваша'}

    # Получаем текущую информацию об армии
    owner, count = get_army_info(state['armies'], position)

    if owner is not None and owner != pid:
        return {'success': False, 'error': 'В провинции чужая армия'}

    # Увеличиваем количество дивизий
    set_army_info(state['armies'], position, pid, count + 1)

    econ['gold'] -= ARMY_COST
    econ['army_count'] = econ.get('army_count', 0) + 1
    return {'success': True}


def handle_move_army(game, pid, from_pos, to_pos):
    state = game['map_state']
    econ = state['economies'].get(pid, {})

    if econ.get('gold', 0) < MOVE_COST:
        return {'success': False, 'error': 'Недостаточно золота'}

    # Проверяем исходную армию
    from_owner, from_count = get_army_info(state['armies'], from_pos)
    if from_owner != pid or from_count == 0:
        return {'success': False, 'error': 'Нет вашей армии в исходной провинции'}

    # Проверяем целевую армию
    to_owner, to_count = get_army_info(state['armies'], to_pos)

    player_country = game['countries'].get(pid)
    econ['gold'] -= MOVE_COST

    # Если целевая провинция наша
    if to_owner == pid:
        set_army_info(state['armies'], to_pos, pid, to_count + from_count)
        if from_pos in state['armies']:
            del state['armies'][from_pos]
        return {'success': True, 'conquered': False}

    # Если целевая провинция пустая
    if to_owner is None:
        set_army_info(state['armies'], to_pos, pid, from_count)
        if from_pos in state['armies']:
            del state['armies'][from_pos]
        # Проверяем захват
        if state['province_owners'].get(to_pos) != player_country:
            state['province_owners'][to_pos] = player_country
            return {'success': True, 'conquered': True}
        return {'success': True, 'conquered': False}

    # Сражение с чужой армией
    if from_count > to_count:
        # Победа
        losses = max(0, int(to_count * 0.7))  # Базовые потери 70% от врага
        survivors = max(1, from_count - losses)
        set_army_info(state['armies'], to_pos, pid, survivors)
        if from_pos in state['armies']:
            del state['armies'][from_pos]

        # Захват провинции
        conquered = state['province_owners'].get(to_pos) != player_country
        if conquered:
            state['province_owners'][to_pos] = player_country
        return {'success': True, 'conquered': conquered}

    elif from_count == to_count:
        # Ничья — обе армии уничтожены
        if from_pos in state['armies']:
            del state['armies'][from_pos]
        if to_pos in state['armies']:
            del state['armies'][to_pos]
        return {'success': True, 'conquered': False}

    else:
        # Поражение — атакующий уничтожен
        if from_pos in state['armies']:
            del state['armies'][from_pos]
        return {'success': True, 'conquered': False}


def handle_level_up(game, pid, province_name):
    state = game['map_state']
    econ = state['economies'].get(pid, {})
    if econ.get('gold', 0) < LEVEL_UP_COST: return {'success': False, 'error': 'Недостаточно золота'}
    if state['province_owners'].get(province_name) != game['countries'].get(pid): return {'success': False,
                                                                                          'error': 'Провинция не ваша'}
    if state['province_levels'].get(province_name, 1) >= 4: return {'success': False, 'error': 'Максимальный уровень'}
    econ['gold'] -= LEVEL_UP_COST
    state['province_levels'][province_name] = state['province_levels'].get(province_name, 1) + 1
    return {'success': True}


def process_end_turn(game):
    state = game['map_state']
    for pid, econ in state['economies'].items():
        country = game['countries'].get(pid)
        if not country: continue
        total_level = sum(
            state['province_levels'].get(p, 1) for p, o in state['province_owners'].items() if o == country)
        econ['gold'] = econ.get('gold', 0) + total_level * 2


def sanitize_game_state(game, time_left=None):
    return {
        'id': game['id'], 'year': game['year'],
        'players': [
            {'player_id': pid, 'name': players.get(pid, {}).get('name', pid), 'country': game['countries'].get(pid),
             'is_host': pid == game['host']} for pid in game['players'] if not pid.startswith('bot_')],
        'turn': game['turn'], 'current_player': game['current_player'], 'state': game['state'],
        'map_state': game.get('map_state', {}), 'bot_mode_enabled': game.get('bot_mode_enabled', False),
        'time_left': time_left, 'server_time': ts()
    }


def next_player(game):
    if not game['players']: return
    try:
        idx = game['players'].index(game['current_player'])
    except:
        idx = -1
    game['current_player'] = game['players'][(idx + 1) % len(game['players'])]
    game['turn'] += 1
    game['turn_started_at'] = time.time()
    if game['current_player'].startswith('bot_'):
        Timer(0.5, process_bot_turn, args=[game['id']]).start()


def process_bot_turn(gid):
    with lock:
        game = games.get(gid)
        if not game or game['state'] != 'playing': return
        bot_id = game['current_player']
        if not bot_id.startswith('bot_'): return
        bot_country = game['countries'].get(bot_id)
        state = game['map_state']
        try:
            from ai_controller import AIController
            ai = AIController(
                country_name=bot_country,
                country_data={'gold': state['economies'].get(bot_id, {}).get('gold', 100),
                              'provinces': [n for n, o in state['province_owners'].items() if o == bot_country],
                              'color': [100, 100, 100]},
                provinces_data=MAP_DATA.get(game['year'], {}).get('provinces', {}),
                player_country_name=game['countries'].get(game['host'], ''),
                all_armies=state['armies']
            )
            ai.make_move()
            state['armies'] = ai.all_armies
            state['economies'][bot_id]['gold'] = ai.gold
            for prov_name in ai.provinces:
                state['province_owners'][prov_name] = bot_country
        except Exception as e:
            print(f"⚠️ Bot error: {e}")
        Timer(0.5, next_player, args=[gid]).start()


def start_countdown(gid):
    if gid in games: games[gid].update({'locked': True, 'countdown_started_at': time.time(), 'state': 'counting_down'})


def start_game(gid):
    game = games.get(gid)
    if not game: return
    if game.get('bot_mode_enabled'): add_bots(gid)
    map_info = MAP_DATA.get(game['year'], {})
    all_countries = list(map_info.get('countries', {}).keys())
    occupied = [c for c in game['countries'].values() if c]
    available = [c for c in all_countries if c not in occupied]
    for pid in game['players']:
        if game['countries'].get(pid) is None and available: game['countries'][pid] = available.pop(0)
    if not game.get('map_state'): game['map_state'] = init_game_state(game['year'], game['players'])
    game.update(
        {'state': 'playing', 'locked': False, 'countdown_started_at': None, 'turn_started_at': time.time(), 'turn': 0})


def add_bots(gid):
    game = games.get(gid)
    if not game: return
    all_countries = list(MAP_DATA.get(game['year'], {}).get('countries', {}).keys())
    occupied = [c for c in game['countries'].values() if c]
    for country in all_countries:
        if country not in occupied:
            bot_id = f"bot_{country}"
            game['players'].append(bot_id)
            game['countries'][bot_id] = country
            game['map_state']['economies'][bot_id] = {'gold': 100, 'wheat': 0, 'metal': 0, 'wood': 0, 'coal': 0,
                                                      'oil': 0, 'army_count': 0}
            occupied.append(country)


# API
@app.route('/api/health')
def health(): return jsonify({"status": "ok"})


@app.route('/api/player/register', methods=['POST'])
def register():
    if not check_auth(): return jsonify({"error": "Invalid secret"}), 403
    name = (request.get_json(silent=True) or {}).get('name', '').strip()
    if not name: return jsonify({"error": "Name required"}), 400
    with lock:
        for pid, pdata in players.items():
            if pdata['name'] == name: return jsonify({"player_id": pid}), 200
        pid = gen_id()
        players[pid] = {'id': pid, 'name': name, 'created_at': ts(), 'current_game': None}
        save_players()
    return jsonify({"player_id": pid}), 201


@app.route('/api/game/create', methods=['POST'])
def create():
    if not check_auth(): return jsonify({"error": "Invalid secret"}), 403
    data = request.get_json(silent=True) or {}
    host_id = data.get('host_player_id')
    if not host_id or host_id not in players: return jsonify({"error": "Invalid player"}), 404
    gid = gen_id()
    with lock:
        games[gid] = {'id': gid, 'year': data.get('year', 1938), 'host': host_id, 'players': [host_id],
                      'countries': {host_id: None}, 'turn': 0, 'current_player': host_id,
                      'turn_started_at': time.time(), 'turn_time_limit': data.get('turn_time', TURN_TIME),
                      'state': 'waiting', 'map_state': init_game_state(data.get('year', 1938), [host_id]),
                      'chat': [], 'created_at': ts(), 'bot_mode_enabled': False,
                      'countdown_started_at': None, 'locked': False}
        players[host_id]['current_game'] = gid
    return jsonify({"game_id": gid}), 201


@app.route('/api/game/<gid>/join', methods=['POST'])
def join(gid):
    if not check_auth(): return jsonify({"error": "Invalid secret"}), 403
    data = request.get_json(silent=True) or {}
    pid, country = data.get('player_id'), data.get('country')
    with lock:
        game = games.get(gid)
        if not game: return jsonify({"error": "Game not found"}), 404
        if game['state'] not in ['waiting', 'counting_down'] or game.get('locked'):
            return jsonify({"error": "Cannot join now"}), 400
        if pid not in players: return jsonify({"error": "Invalid player"}), 400
        if country in game['countries'].values(): return jsonify({"error": "Country taken"}), 400
        if pid in game['players']:
            game['countries'][pid] = country
            return jsonify({"message": "Country updated", "game_state": sanitize_game_state(game)}), 200
        if len(game['players']) >= MAX_P: return jsonify({"error": "Game full"}), 400
        game['players'].append(pid)
        game['countries'][pid] = country
        players[pid]['current_game'] = gid
        game['map_state']['economies'][pid] = {'gold': 100, 'wheat': 0, 'metal': 0, 'wood': 0, 'coal': 0, 'oil': 0,
                                               'army_count': 0}
    return jsonify({"message": "Joined", "game_state": sanitize_game_state(game)}), 200


@app.route('/api/game/<gid>/action', methods=['POST'])
def action(gid):
    if not check_auth(): return jsonify({"error": "Invalid secret"}), 403
    data = request.get_json(silent=True) or {}
    pid, action_type = data.get('player_id'), data.get('action_type')
    with lock:
        game = games.get(gid)
        if not game: return jsonify({"error": "Game not found"}), 404
        if game['state'] != 'playing': return jsonify({"error": "Game not started"}), 400
        if game['current_player'] != pid: return jsonify({"error": "Not your turn"}), 403
        handlers = {
            'buy_army': lambda: handle_buy_army(game, pid, data.get('position')),
            'move_army': lambda: handle_move_army(game, pid, data.get('from_position'), data.get('to_position')),
            'level_up_province': lambda: handle_level_up(game, pid, data.get('province'))
        }
        result = handlers.get(action_type, lambda: {'success': False, 'error': 'Unknown action'})()
    return jsonify(result), 200


@app.route('/api/game/<gid>/end_turn', methods=['POST'])
def end_turn(gid):
    if not check_auth(): return jsonify({"error": "Invalid secret"}), 403
    pid = (request.get_json(silent=True) or {}).get('player_id')
    with lock:
        game = games.get(gid)
        if not game or game['state'] != 'playing': return jsonify({"error": "Invalid game state"}), 400
        if game['current_player'] != pid: return jsonify({"error": "Not your turn"}), 403
        process_end_turn(game)
        next_player(game)
    return jsonify({"success": True, "new_state": sanitize_game_state(game)}), 200


@app.route('/api/game/<gid>/state')
def get_state(gid):
    with lock:
        game = games.get(gid)
        if not game: return jsonify({"error": "Not found"}), 404
        time_left = None
        if game.get('locked') and game.get('countdown_started_at'):
            time_left = max(0, COUNTDOWN - (time.time() - game['countdown_started_at']))
            if time_left <= 0: start_game(gid); time_left = 0
        return jsonify(sanitize_game_state(game, time_left))


@app.route('/api/games/list')
def list_games():
    with lock:
        return jsonify({"games": [{'id': g['id'], 'name': f"Room {g['id'][-6:]}",
                                   'year': g['year'], 'players_count': len(g['players']),
                                   'max_players': MAX_P, 'host': g['host'],
                                   'locked': g.get('locked', False),
                                   'bot_mode': g.get('bot_mode_enabled', False)}
                                  for g in games.values() if g['state'] in ['waiting', 'counting_down']]})


@app.route('/api/game/<gid>/enable_bots', methods=['POST'])
def enable_bots(gid):
    if not check_auth(): return jsonify({"error": "Invalid secret"}), 403
    pid = (request.get_json(silent=True) or {}).get('player_id')
    with lock:
        game = games.get(gid)
        if not game or game['host'] != pid: return jsonify({"error": "Denied"}), 403
        if game['state'] in ['playing', 'counting_down']: return jsonify({"error": "Game already starting"}), 400
        game['bot_mode_enabled'] = True
    return jsonify({"message": "Bots enabled"}), 200


@app.route('/api/game/<gid>/leave', methods=['POST'])
def leave(gid):
    if not check_auth(): return jsonify({"error": "Invalid secret"}), 403
    pid = (request.get_json(silent=True) or {}).get('player_id')
    with lock:
        game = games.get(gid)
        if not game: return jsonify({"error": "Not found"}), 404
        if pid in players: players[pid]['current_game'] = None
        if pid in game['players']: game['players'].remove(pid)
        game['countries'].pop(pid, None)
        game['map_state']['economies'].pop(pid, None)
        game['map_state']['armies'] = {p: o for p, o in game['map_state']['armies'].items()
                                       if (o.get("owner") if isinstance(o, dict) else o) != pid}
        if pid == game['host']:
            if game['players']:
                game['host'] = game['current_player'] = game['players'][0]
            else:
                del games[gid]
                return jsonify({"message": "Game deleted"}), 200
    return jsonify({"message": "Left"}), 200


@app.route('/api/game/<gid>/start', methods=['POST'])
def start_game_manual(gid):
    if not check_auth(): return jsonify({"error": "Invalid secret"}), 403
    pid = (request.get_json(silent=True) or {}).get('player_id')
    with lock:
        game = games.get(gid)
        if not game or game['host'] != pid: return jsonify({"error": "Denied"}), 403
        if game['state'] != 'waiting': return jsonify({"error": "Game already starting"}), 400
        if not game.get('bot_mode_enabled') and not all(
                game['countries'].get(p) for p in game['players'] if not p.startswith('bot_')):
            return jsonify({"error": "Не все игроки выбрали страны"}), 400
        start_countdown(gid)
    return jsonify({"message": "Game starting", "time_left": COUNTDOWN}), 200


def turn_timer():
    while True:
        time.sleep(5)
        with lock:
            for gid, game in list(games.items()):
                if game['state'] == 'playing' and time.time() - game['turn_started_at'] >= game['turn_time_limit']:
                    next_player(game)


Thread(target=turn_timer, daemon=True).start()
load_players()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
