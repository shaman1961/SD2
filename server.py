from flask import Flask, request, jsonify
from flask_cors import CORS
import time, random, json
from datetime import datetime
from threading import Thread, Lock

app = Flask(__name__)
CORS(app)
SECRET, PORT = "SteelDawn2024", 5443
TURN_TIME, MAX_P, MIN_P, COUNTDOWN = 180, 8, 2, 10
COUNTRIES = {
    1938: ["Германия","СССР","Британия","Франция","Италия","Польша","Чехословакия","Испания","Турция","Швеция","Румыния","Венгрия","Югославия","Греция","Бельгия","Нидерланды","Дания","Норвегия","Финляндия","Португалия","Швейцария","Ирландия","Болгария","Австрия","Литва","Латвия","Эстония"],
    1941: ["Германия","СССР","Британия","Италия","Словакия","Франция Виши","Свободная Франция","Хорватия","Венгрия","Румыния","Болгария","Финляндия","Швеция","Швейцария","Португалия","Испания","Турция","Ирландия"]
}
games, players, lock = {}, {}, Lock()

def gen_id(): return f"{int(time.time())}_{random.randint(1000,9999)}"
def ts(): return datetime.now().isoformat()
def check(): return (request.get_json(silent=True) or {}).get('secret_code') == SECRET

@app.route('/api/health')
def health(): return jsonify({"status":"ok","timestamp":ts()})

@app.route('/api/player/register', methods=['POST'])
def register():
    if not check(): return jsonify({"error":"Invalid secret"}), 403
    data = request.get_json(silent=True) or {}
    if not data.get('name'): return jsonify({"error":"Name required"}), 400
    pid = gen_id()
    with lock: players[pid] = {'id':pid, 'name':data['name'].strip(), 'created_at':ts(), 'current_game':None}
    return jsonify({"player_id":pid}), 201

@app.route('/api/game/create', methods=['POST'])
def create():
    if not check(): return jsonify({"error":"Invalid secret"}), 403
    data = request.get_json(silent=True) or {}
    if not data.get('year') or not data.get('host_player_id'): return jsonify({"error":"Missing params"}), 400
    hid = data['host_player_id']
    with lock:
        if hid not in players: return jsonify({"error":"Invalid player"}), 404
        gid = gen_id()
        games[gid] = {'id':gid, 'year':data['year'], 'host':hid, 'players':[hid], 'countries':{}, 'turn':0,
            'current_player':hid, 'turn_started_at':time.time(), 'turn_time_limit':data.get('turn_time',TURN_TIME),
            'state':'waiting', 'map_state':{}, 'armies':{}, 'economies':{hid:{'gold':100,'wheat':0,'metal':0,'wood':0,'coal':0,'oil':0,'army_count':0}},
            'chat':[], 'created_at':ts(), 'bot_mode_enabled':False, 'countdown_started_at':None, 'locked':False}
        players[hid]['current_game'] = gid
    return jsonify({"game_id":gid}), 201

@app.route('/api/game/<gid>/join', methods=['POST'])
def join(gid):
    if not check(): return jsonify({"error":"Invalid secret"}), 403
    data = request.get_json(silent=True) or {}
    if not data.get('player_id') or not data.get('country'): return jsonify({"error":"Missing params"}), 400
    with lock:
        g = games.get(gid)
        if not g or g['state'] not in ['waiting','counting_down'] or g.get('locked'): return jsonify({"error":"Cannot join"}), 400
        if data['player_id'] not in players or data['country'] in g['countries'].values() or len(g['players'])>=MAX_P:
            return jsonify({"error":"Invalid"}), 400
        g['players'].append(data['player_id']); g['countries'][data['player_id']] = data['country']
        players[data['player_id']]['current_game'] = gid
        g['economies'][data['player_id']] = {'gold':100,'wheat':0,'metal':0,'wood':0,'coal':0,'oil':0,'army_count':0}
        if len(g['players'])>=MIN_P and g['state']=='waiting': _countdown(gid)
    return jsonify({"message":"Joined","game_state":g}), 200

@app.route('/api/game/<gid>/enable_bots', methods=['POST'])
def bots(gid):
    if not check(): return jsonify({"error":"Invalid secret"}), 403
    data = request.get_json(silent=True) or {}
    with lock:
        g = games.get(gid)
        if not g or g['host']!=data.get('player_id') or g['state'] in ['playing','counting_down']: return jsonify({"error":"Denied"}), 403
        g['bot_mode_enabled'] = True; _countdown(gid)
    return jsonify({"message":"Bots enabled","game_state":g}), 200

@app.route('/api/game/<gid>/state')
def state(gid):
    with lock:
        g = games.get(gid)
        if not g: return jsonify({"error":"Not found"}), 404
        tl = None
        if g.get('locked') and g.get('countdown_started_at') and g['state']=='counting_down':
            tl = max(0, COUNTDOWN - (time.time()-g['countdown_started_at']))
            if tl<=0: _start(gid); tl=0
        return jsonify({**{k:v for k,v in g.items()}, 'time_left':tl, 'server_time':ts()})

@app.route('/api/game/<gid>/leave', methods=['POST'])
def leave(gid):
    if not check(): return jsonify({"error":"Invalid secret"}), 403
    data = request.get_json(silent=True) or {}
    with lock:
        g = games.get(gid)
        if not g: return jsonify({"error":"Not found"}), 404
        if data['player_id'] in players: players[data['player_id']]['current_game'] = None
        for k in ['players','countries','economies']:
            if data['player_id'] in g[k]:
                if k!='players': del g[k][data['player_id']]
                else: g[k].remove(data['player_id'])
        if data['player_id']==g['host']:
            if g['players']: g['host']=g['current_player']=g['players'][0]; g.update({'state':'waiting','locked':False,'countdown_started_at':None})
            else: del games[gid]; return jsonify({"message":"Deleted"})
    return jsonify({"message":"Left","game_state":g}), 200

@app.route('/api/game/<gid>/action', methods=['POST'])
def action(gid):
    if not check(): return jsonify({"error":"Invalid secret"}), 403
    data = request.get_json(silent=True) or {}
    with lock:
        g = games.get(gid)
        if not g or g['state']!='playing' or g['current_player']!=data.get('player_id'): return jsonify({"error":"Denied"}), 403
        print(f"📥 [{data.get('action_type')}] from {data.get('player_id')}")
    return jsonify({"success":True}), 200

@app.route('/api/game/<gid>/end_turn', methods=['POST'])
def end_turn(gid):
    if not check(): return jsonify({"error":"Invalid secret"}), 403
    data = request.get_json(silent=True) or {}
    with lock:
        g = games.get(gid)
        if not g or g['state']!='playing' or g['current_player']!=data.get('player_id'): return jsonify({"error":"Denied"}), 403
        _next(gid)
    return jsonify({"success":True,"new_state":g}), 200

@app.route('/api/game/<gid>/finish', methods=['POST'])
def finish(gid):
    if not check(): return jsonify({"error":"Invalid secret"}), 403
    data = request.get_json(silent=True) or {}
    with lock:
        g = games.get(gid)
        if not g or g['host']!=data.get('player_id'): return jsonify({"error":"Denied"}), 403
        for p in g['players']:
            if p in players: players[p]['current_game'] = None
        del games[gid]
    return jsonify({"message":"Finished"}), 200

@app.route('/api/games/list')
def list_games():
    with lock:
        return jsonify({"games":[{'id':g['id'],'name':g.get('name',f"Room {g['id']}"),'year':g['year'],
            'players_count':len(g['players']),'max_players':MAX_P,'host':g['host'],'locked':g.get('locked'),
            'bot_mode':g.get('bot_mode_enabled')} for g in games.values() if g['state'] in ['waiting','counting_down']]})

def _countdown(gid):
    games[gid].update({'locked':True,'countdown_started_at':time.time(),'state':'counting_down'})
    print(f"⏱ {gid}")

def _start(gid):
    g = games[gid]
    g.update({'state':'playing','locked':False,'countdown_started_at':None,'turn_started_at':time.time()})
    print(f"🎮 {gid}")
    if g.get('bot_mode_enabled'): _add_bots(gid)

def _add_bots(gid):
    g = games[gid]; occ = set(g['countries'].values())
    for c in COUNTRIES.get(g['year'],[]):
        if c not in occ:
            bid = f"bot_{c}"; g['players'].append(bid); g['countries'][bid] = c
            g['economies'][bid] = {'gold':100,'wheat':0,'metal':0,'wood':0,'coal':0,'oil':0,'army_count':0}

def _next(gid):
    g = games[gid]
    if not g['players']: return
    try: idx = g['players'].index(g['current_player'])
    except: idx = -1
    g['current_player'] = g['players'][(idx+1)%len(g['players'])]; g['turn']+=1; g['turn_started_at'] = time.time()

def _timer():
    while True:
        time.sleep(5)
        with lock:
            for gid,g in list(games.items()):
                if g['state']=='playing' and time.time()-g['turn_started_at']>=g['turn_time_limit']: _next(gid)

Thread(target=_timer, daemon=True).start()

if __name__=='__main__':
    print(f"🌐 Server on :{PORT} | 🔐 {SECRET}")
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
