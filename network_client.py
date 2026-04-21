import requests, time, threading, os, json
from typing import Optional, Callable, Dict, List

SECRET, URL = "SteelDawn2024", "http://192.168.0.148:5443"

class NetworkClient:
    def __init__(self, server_url: str = URL, secret_code: str = SECRET):
        self.server_url = server_url.rstrip('/')
        self.secret_code = secret_code
        self.player_id: Optional[str] = None
        self.game_id: Optional[str] = None
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json', 'User-Agent': 'SteelDawn/1.0'})
        self._poll_thread: Optional[threading.Thread] = None
        self._poll_stop = threading.Event()
        self.load_player_session()

    def _req(self, method: str, endpoint: str, **kw) -> Optional[requests.Response]:
        url = f"{self.server_url}{endpoint}"
        if 'json' in kw and kw['json']: kw['json']['secret_code'] = self.secret_code
        kw.setdefault('timeout', 10)
        try:
            r = self.session.request(method, url, **kw); r.raise_for_status(); return r
        except Exception as e: print(f"❌ {'Connection' if 'Connection' in str(type(e)) else 'Network'} Error: {e}"); return None

    def register(self, name: str) -> Optional[str]:
        if not name or not name.strip(): return None
        r = self._req('POST', '/api/player/register', json={"name": name.strip()})
        if not r: return None
        d = r.json(); self.player_id = d.get('player_id')
        if self.player_id: print(f"✅ Игрок зарегистрирован: {self.player_id}"); self.save_player_session(); return self.player_id
        print(f"❌ Ошибка: {d.get('error', 'Unknown')}"); return None

    def create_game(self, year: int = 1938, turn_time: int = 180) -> Optional[str]:
        if not self.player_id: return None
        r = self._req('POST', '/api/game/create', json={"year": year, "host_player_id": self.player_id, "turn_time": turn_time})
        if not r: return None
        d = r.json(); self.game_id = d.get('game_id')
        if self.game_id: print(f"✅ Игра создана: {self.game_id}"); return self.game_id
        return None

    def join_game(self, game_id: str, country: str) -> bool:
        if not self.player_id: return False
        r = self._req('POST', f'/api/game/{game_id}/join', json={"player_id": self.player_id, "country": country})
        if not r: return False
        self.game_id = game_id; print(f"✅ Присоединился: {game_id}"); return True

    def enable_bots(self) -> bool:
        if not self.game_id or not self.player_id: return False
        r = self._req('POST', f'/api/game/{self.game_id}/enable_bots', json={"player_id": self.player_id})
        if not r: return False
        if r.json().get('success'): print("✅ Боты включены"); return True
        return False

    def leave_game(self) -> bool:
        if not self.game_id or not self.player_id: return True
        self._req('POST', f'/api/game/{self.game_id}/leave', json={"player_id": self.player_id})
        self.game_id = None; print("✅ Вышли из игры"); return True

    def finish_game(self) -> bool:
        if not self.game_id or not self.player_id: return False
        self._req('POST', f'/api/game/{self.game_id}/finish', json={"player_id": self.player_id})
        self.game_id = None; print("✅ Игра завершена"); return True

    def get_game_state(self) -> Dict:
        if not self.game_id: return {}
        r = self._req('GET', f'/api/game/{self.game_id}/state')
        return r.json() if r else {}

    def get_games_list(self) -> List:
        r = self._req('GET', '/api/games/list')
        return r.json().get('games', []) if r else []

    def send_action(self, action_type: str, **kw) -> Dict:
        if not self.game_id or not self.player_id: return {"error": "Not connected"}
        r = self._req('POST', f'/api/game/{self.game_id}/action', json={"player_id": self.player_id, "action_type": action_type, **kw})
        return r.json() if r else {"error": "Request failed"}

    def end_turn(self) -> Dict: return self.send_action('end_turn')

    def poll_updates(self, callback: Callable, interval: float = 2.0) -> Optional[threading.Thread]:
        if not self.game_id: return None
        self._poll_stop.clear()
        def loop():
            while not self._poll_stop.is_set() and self.game_id:
                try:
                    s = self.get_game_state()
                    if s and callback: callback(s)
                except Exception as e: print(f"⚠️ Poll error: {e}")
                self._poll_stop.wait(interval)
        self._poll_thread = threading.Thread(target=loop, daemon=True); self._poll_thread.start(); return self._poll_thread

    def close(self):
        self.game_id = None; self._poll_stop.set()
        if self._poll_thread and self._poll_thread.is_alive(): self._poll_thread.join(timeout=2.0)
        self.session.close(); print("🔌 Connection closed")

    def save_player_session(self, filename: str = "player_config.json") -> bool:
        if not self.player_id: return False
        try:
            with open(os.path.join(os.getcwd(), filename), 'w', encoding='utf-8') as f: json.dump({'player_id': self.player_id}, f, ensure_ascii=False)
            return True
        except Exception as e: print(f"⚠️ Save error: {e}"); return False

    def load_player_session(self, filename: str = "player_config.json") -> bool:
        try:
            path = os.path.join(os.getcwd(), filename)
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f: self.player_id = json.load(f).get('player_id')
                if self.player_id: print(f"✅ Сессия загружена: {self.player_id}"); return True
        except Exception as e: print(f"⚠️ Load error: {e}")
        return False

    def __enter__(self): return self
    def __exit__(self, *args): self.close(); return False
