from flask import Flask, request, jsonify
from flask_cors import CORS
import time, random, json, os
from datetime import datetime
from threading import Thread, Lock, Timer
from sqlalchemy import create_engine, Column, String
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool
from flask import render_template

app = Flask(__name__)
CORS(app)

SECRET = "SteelDawn2024"
PORT = 5443
TURN_TIME = 180
MAX_P = 8
MIN_P = 2
COUNTDOWN = 10
DB_FILE = "players.db"
ARMY_COST = 50
LEVEL_UP_COST = 50
MOVE_COST = 25

Base = declarative_base()

class Player(Base):
    __tablename__ = 'players'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    created_at = Column(String, nullable=False)

engine = create_engine(
    f'sqlite:///{DB_FILE}',
    connect_args={'check_same_thread': False},
    poolclass=StaticPool,
    echo=False
)
Base.metadata.create_all(engine)
session_factory = sessionmaker(bind=engine)
DBSession = scoped_session(session_factory)

def load_players():
    """Загружает всех игроков из БД в словарь players"""
    global players
    session = DBSession()
    try:
        for player in session.query(Player).all():
            players[player.id] = {
                'id': player.id,
                'name': player.name,
                'created_at': player.created_at,
                'current_game': None
            }
    finally:
        session.close()

def load_map_data():
    map_data = {}
    for year in [1938, 1941]:
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
    return map_data

MAP_DATA = load_map_data()
games, players, lock = {}, {}, Lock()

def gen_id(): return f"{int(time.time())}_{random.randint(1000,9999)}"
def ts(): return datetime.now().isoformat()
def check_auth(): return (request.get_json(silent=True) or {}).get('secret_code') == SECRET

def init_game_state(year, players_list):
    map_info = MAP_DATA.get(year, {})
    countries_data = map_info.get('countries', {})
    province_owners = {prov: country for country, data in countries_data.items() for prov in data.get('provinces', [])}
    economies = {pid: {'gold': 100, 'wheat': 0, 'metal': 0, 'wood': 0, 'coal': 0, 'oil': 0, 'army_count': 0} for pid in players_list}
    return {'province_owners': province_owners, 'economies': economies, 'armies': {}, 'province_levels': {}}

def get_army_info(armies_dict, position):
    info = armies_dict.get(position)
    if not info: return None, 0
    if isinstance(info, dict): return info.get("owner"), info.get("count", 1)
    else: return info, 1

def set_army_info(armies_dict, position, owner, count):
    if count > 0: armies_dict[position] = {"owner": owner, "count": count}
    elif position in armies_dict: del armies_dict[position]

def handle_buy_army(game, pid, position):
    state = game['map_state']
    econ = state['economies'].get(pid, {})
    if econ.get('gold', 0) < ARMY_COST: return {'success': False, 'error': 'Недостаточно золота'}
    if state['province_owners'].get(position) != game['countries'].get(pid): return {'success': False, 'error': 'Провинция не ваша'}
    owner, count = get_army_info(state['armies'], position)
    if owner is not None and owner != pid: return {'success': False, 'error': 'В провинции чужая армия'}
    set_army_info(state['armies'], position, pid, count + 1)
    econ['gold'] -= ARMY_COST
    econ['army_count'] = econ.get('army_count', 0) + 1
    return {'success': True}

def handle_move_army(game, pid, from_pos, to_pos):
    state = game['map_state']
    econ = state['economies'].get(pid, {})
    if econ.get('gold', 0) < MOVE_COST: return {'success': False, 'error': 'Недостаточно золота'}
    from_owner, from_count = get_army_info(state['armies'], from_pos)
    if from_owner != pid or from_count == 0: return {'success': False, 'error': 'Нет вашей армии в исходной провинции'}
    to_owner, to_count = get_army_info(state['armies'], to_pos)
    player_country = game['countries'].get(pid)
    econ['gold'] -= MOVE_COST
    if to_owner == pid:
        set_army_info(state['armies'], to_pos, pid, to_count + from_count)
        if from_pos in state['armies']: del state['armies'][from_pos]
        return {'success': True, 'conquered': False}
    if to_owner is None:
        set_army_info(state['armies'], to_pos, pid, from_count)
        if from_pos in state['armies']: del state['armies'][from_pos]
        if state['province_owners'].get(to_pos) != player_country:
            state['province_owners'][to_pos] = player_country
            return {'success': True, 'conquered': True}
        return {'success': True, 'conquered': False}
    if from_count > to_count:
        losses = max(0, int(to_count * 0.7))
        survivors = max(1, from_count - losses)
        set_army_info(state['armies'], to_pos, pid, survivors)
        if from_pos in state['armies']: del state['armies'][from_pos]
        conquered = state['province_owners'].get(to_pos) != player_country
        if conquered: state['province_owners'][to_pos] = player_country
        return {'success': True, 'conquered': conquered}
    elif from_count == to_count:
        if from_pos in state['armies']: del state['armies'][from_pos]
        if to_pos in state['armies']: del state['armies'][to_pos]
        return {'success': True, 'conquered': False}
    else:
        if from_pos in state['armies']: del state['armies'][from_pos]
        return {'success': True, 'conquered': False}

def handle_level_up(game, pid, province_name):
    state = game['map_state']
    econ = state['economies'].get(pid, {})
    if econ.get('gold', 0) < LEVEL_UP_COST: return {'success': False, 'error': 'Недостаточно золота'}
    if state['province_owners'].get(province_name) != game['countries'].get(pid): return {'success': False, 'error': 'Провинция не ваша'}
    if state['province_levels'].get(province_name, 1) >= 4: return {'success': False, 'error': 'Максимальный уровень'}
    econ['gold'] -= LEVEL_UP_COST
    state['province_levels'][province_name] = state['province_levels'].get(province_name, 1) + 1
    return {'success': True}

def process_end_turn(game):
    state = game['map_state']
    for pid, econ in state['economies'].items():
        country = game['countries'].get(pid)
        if not country: continue
        total_level = sum(state['province_levels'].get(p, 1) for p, o in state['province_owners'].items() if o == country)
        econ['gold'] = econ.get('gold', 0) + total_level * 2

def sanitize_game_state(game, time_left=None):
    return {
        'id': game['id'], 'year': game['year'],
        'name': game.get('name', ''),
        'players': [{'player_id': pid, 'name': players.get(pid, {}).get('name', pid), 'country': game['countries'].get(pid), 'is_host': pid == game['host'], 'ready': game.get('ready_status', {}).get(pid, False)} for pid in game['players'] if not pid.startswith('bot_')],
        'turn': game['turn'], 'current_player': game['current_player'], 'state': game['state'],
        'map_state': game.get('map_state', {}), 'bot_mode_enabled': game.get('bot_mode_enabled', False),
        'time_left': time_left, 'server_time': ts()
    }

def next_player(game):
    if isinstance(game, str):
        game = games.get(game)
        if not game:
            return

    if not game['players']: return
    try:
        idx = game['players'].index(game['current_player'])
    except:
        idx = -1

    game['current_player'] = game['players'][(idx + 1) % len(game['players'])]
    game['turn'] += 1
    game['turn_started_at'] = time.time()

    if game['current_player'].startswith('bot_'):
        process_all_bots(game)

def process_all_bots(game):
    max_iterations = len(game['players'])
    iterations = 0

    while game['current_player'].startswith('bot_') and iterations < max_iterations:
        bot_id = game['current_player']
        bot_country = game['countries'].get(bot_id)
        state = game['map_state']

        from ai_controller import AIController
        ai = AIController(
            country_name=bot_country,
            country_data={
                'gold': state['economies'].get(bot_id, {}).get('gold', 100),
                'provinces': [n for n, o in state['province_owners'].items() if o == bot_country],
                'color': [100, 100, 100]
            },
            provinces_data=MAP_DATA.get(game['year'], {}).get('provinces', {}),
            player_country_name=game['countries'].get(game['host'], ''),
            all_armies=state['armies'].copy()
        )
        ai.make_move()
        state['armies'] = dict(ai.all_armies)
        state['economies'][bot_id]['gold'] = ai.gold
        for prov_name in ai.provinces:
            if prov_name:
                state['province_owners'][prov_name] = bot_country

        try:
            idx = game['players'].index(game['current_player'])
        except:
            idx = -1
        game['current_player'] = game['players'][(idx + 1) % len(game['players'])]
        game['turn_started_at'] = time.time()
        iterations += 1

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
    game.update({'state': 'playing', 'locked': False, 'countdown_started_at': None, 'turn_started_at': time.time(), 'turn': 0})

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
            game['map_state']['economies'][bot_id] = {'gold': 100, 'wheat': 0, 'metal': 0, 'wood': 0, 'coal': 0, 'oil': 0, 'army_count': 0}
            occupied.append(country)

@app.route('/api/health')
def health(): return jsonify({"status": "ok"})

@app.route('/api/player/register', methods=['POST'])
def register():
    if not check_auth(): return jsonify({"error": "Invalid secret"}), 403
    name = (request.get_json(silent=True) or {}).get('name', '').strip()
    if not name: return jsonify({"error": "Name required"}), 400
    with lock:
        session = DBSession()
        try:
            existing = session.query(Player).filter_by(name=name).first()
            if existing: return jsonify({"player_id": existing.id}), 200
            pid = gen_id()
            player = Player(id=pid, name=name, created_at=ts())
            session.add(player)
            session.commit()
            players[pid] = {'id': pid, 'name': name, 'created_at': player.created_at, 'current_game': None}
        finally:
            session.close()
    return jsonify({"player_id": pid}), 201

@app.route('/api/game/create', methods=['POST'])
def create():
    if not check_auth(): return jsonify({"error": "Invalid secret"}), 403
    data = request.get_json(silent=True) or {}
    host_id = data.get('host_player_id')
    if not host_id or host_id not in players: return jsonify({"error": "Invalid player"}), 404
    gid = gen_id()
    room_name = f"Комната {players[host_id]['name']}"
    with lock:
        games[gid] = {'id': gid, 'year': data.get('year', 1938), 'host': host_id, 'players': [host_id], 'countries': {host_id: None}, 'turn': 0, 'current_player': host_id, 'turn_started_at': time.time(), 'turn_time_limit': data.get('turn_time', TURN_TIME), 'state': 'waiting', 'map_state': init_game_state(data.get('year', 1938), [host_id]), 'chat': [], 'created_at': ts(), 'bot_mode_enabled': False, 'countdown_started_at': None, 'locked': False, 'name': room_name}
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
        if game['state'] not in ['waiting', 'counting_down'] or game.get('locked'): return jsonify({"error": "Cannot join now"}), 400
        if pid not in players: return jsonify({"error": "Invalid player"}), 400
        if country and country in game['countries'].values(): return jsonify({"error": "Country taken"}), 400
        if pid in game['players']:
            if country: game['countries'][pid] = country
            return jsonify({"message": "Country updated", "game_state": sanitize_game_state(game)}), 200
        if len(game['players']) >= MAX_P: return jsonify({"error": "Game full"}), 400
        game['players'].append(pid); game['countries'][pid] = country; players[pid]['current_game'] = gid
        game['map_state']['economies'][pid] = {'gold': 100, 'wheat': 0, 'metal': 0, 'wood': 0, 'coal': 0, 'oil': 0, 'army_count': 0}
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
    if not check_auth():
        return jsonify({"error": "Invalid secret"}), 403
    pid = (request.get_json(silent=True) or {}).get('player_id')
    with lock:
        game = games.get(gid)
        if not game or game['state'] != 'playing':
            return jsonify({"error": "Invalid game state"}), 400
        if game['current_player'] != pid:
            return jsonify({"error": "Not your turn"}), 403
        process_end_turn(game); next_player(game)
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
        return jsonify({"games": [{'id': g['id'], 'name': g.get('name', f"Room {g['id'][-6:]}"), 'year': g['year'], 'players_count': len(g['players']), 'max_players': MAX_P, 'host': g['host'], 'locked': g.get('locked', False), 'bot_mode': g.get('bot_mode_enabled', False)} for g in games.values() if g['state'] in ['waiting', 'counting_down']]})

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
        game['countries'].pop(pid, None); game['map_state']['economies'].pop(pid, None)
        game['map_state']['armies'] = {p: o for p, o in game['map_state']['armies'].items() if (o.get("owner") if isinstance(o, dict) else o) != pid}
        if pid == game['host']:
            if game['players']: game['host'] = game['current_player'] = game['players'][0]
            else: del games[gid]; return jsonify({"message": "Game deleted"}), 200
    return jsonify({"message": "Left"}), 200

@app.route('/api/game/<gid>/start', methods=['POST'])
def start_game_manual(gid):
    if not check_auth(): return jsonify({"error": "Invalid secret"}), 403
    pid = (request.get_json(silent=True) or {}).get('player_id')
    with lock:
        game = games.get(gid)
        if not game or game['host'] != pid: return jsonify({"error": "Denied"}), 403
        if game['state'] != 'waiting': return jsonify({"error": "Game already starting"}), 400
        if not game.get('bot_mode_enabled') and not all(game['countries'].get(p) for p in game['players'] if not p.startswith('bot_')):
            return jsonify({"error": "Не все игроки выбрали страны"}), 400
        start_countdown(gid)
    return jsonify({"message": "Game starting", "time_left": COUNTDOWN}), 200

@app.route('/api/game/<gid>/ready', methods=['POST'])
def toggle_ready(gid):
    if not check_auth(): return jsonify({"error": "Invalid secret"}), 403
    pid = (request.get_json(silent=True) or {}).get('player_id')
    with lock:
        game = games.get(gid)
        if not game: return jsonify({"error": "Game not found"}), 404
        if pid not in game['players']: return jsonify({"error": "Invalid player"}), 400
        current = game.get('ready_status', {}).get(pid, False)
        if 'ready_status' not in game:
            game['ready_status'] = {}
        game['ready_status'][pid] = not current
    return jsonify({"ready": game['ready_status'][pid]}), 200

@app.route('/')
def index():
    return render_template('index.html')

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
