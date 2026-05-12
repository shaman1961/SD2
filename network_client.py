import requests
import time
import threading
import os
import json
from typing import Optional, Callable, Dict, List

SECRET = "SteelDawn2024"
URL = "http://192.168.0.148:5443"


class NetworkClient:
    """Клиент для взаимодействия с сервером игры по REST API."""

    def __init__(self, server_url: str = URL, secret_code: str = SECRET):
        self.server_url = server_url.rstrip('/')
        self.secret_code = secret_code
        self.player_id: Optional[str] = None
        self.game_id: Optional[str] = None

        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'SteelDawn/1.0'
        })

        self._poll_thread: Optional[threading.Thread] = None
        self._poll_stop = threading.Event()

        self.load_player_session()

    def _req(self, method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
        """Выполнить HTTP-запрос к серверу."""
        url = f"{self.server_url}{endpoint}"

        if 'json' in kwargs and kwargs['json']:
            kwargs['json']['secret_code'] = self.secret_code

        kwargs.setdefault('timeout', 10)

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except Exception:
            return None

    def register(self, name: str) -> Optional[str]:
        """Зарегистрировать игрока на сервере."""
        if not name or not name.strip():
            return None

        name = name.strip()
        response = self._req('POST', '/api/player/register', json={"name": name})

        if not response:
            return None

        data = response.json()
        self.player_id = data.get('player_id')

        if self.player_id:
            self.save_player_session()
            return self.player_id

        return None

    def create_game(self, year: int = 1938, turn_time: int = 180) -> Optional[str]:
        """Создать новую игру на сервере."""
        if not self.player_id:
            return None

        response = self._req('POST', '/api/game/create', json={
            "year": year,
            "host_player_id": self.player_id,
            "turn_time": turn_time
        })

        if not response:
            return None

        data = response.json()
        self.game_id = data.get('game_id')

        if self.game_id:
            return self.game_id

        return None

    def join_game(self, game_id: str, country: str) -> bool:
        """Присоединиться к существующей игре."""
        if not self.player_id:
            return False

        response = self._req('POST', f'/api/game/{game_id}/join', json={
            "player_id": self.player_id,
            "country": country
        })

        if not response:
            return False

        self.game_id = game_id
        return True

    def enable_bots(self) -> bool:
        """Включить ботов в игре."""
        if not self.game_id or not self.player_id:
            return False

        response = self._req('POST', f'/api/game/{self.game_id}/enable_bots', json={
            "player_id": self.player_id
        })

        if not response:
            return False

        result = response.json()
        return result.get('success', False)

    def leave_game(self) -> bool:
        """Выйти из игры."""
        if not self.game_id or not self.player_id:
            return True

        self._req('POST', f'/api/game/{self.game_id}/leave', json={
            "player_id": self.player_id
        })

        self.game_id = None
        return True

    def finish_game(self) -> bool:
        """Завершить игру (только для хоста)."""
        if not self.game_id or not self.player_id:
            return False

        self._req('POST', f'/api/game/{self.game_id}/finish', json={
            "player_id": self.player_id
        })

        self.game_id = None
        return True

    def get_game_state(self) -> Dict:
        """Получить текущее состояние игры с сервера."""
        if not self.game_id:
            return {}

        response = self._req('GET', f'/api/game/{self.game_id}/state')

        if response:
            return response.json()

        return {}

    def get_games_list(self) -> List:
        """Получить список доступных игр."""
        response = self._req('GET', '/api/games/list')

        if response:
            return response.json().get('games', [])

        return []

    def send_action(self, action_type: str, **kwargs) -> Dict:
        """Отправить игровое действие на сервер."""
        if not self.game_id or not self.player_id:
            return {"error": "Not connected"}

        payload = {
            "player_id": self.player_id,
            "action_type": action_type,
            **kwargs
        }

        response = self._req('POST', f'/api/game/{self.game_id}/action', json=payload)

        if response:
            return response.json()

        return {"error": "Request failed"}

    def end_turn(self) -> Dict:
        """Завершить текущий ход."""
        if not self.game_id or not self.player_id:
            return {"error": "Not connected"}

        response = self._req('POST', f'/api/game/{self.game_id}/end_turn', json={
            "player_id": self.player_id
        })

        if response:
            return response.json()

        return {"error": "Request failed"}

    def poll_updates(self, callback: Callable, interval: float = 2.0) -> Optional[threading.Thread]:
        """Запустить фоновый опрос сервера."""
        if not self.game_id:
            return None

        self._poll_stop.clear()

        def loop():
            while not self._poll_stop.is_set() and self.game_id:
                state = self.get_game_state()
                if state and callback:
                    callback(state)
                self._poll_stop.wait(interval)

        self._poll_thread = threading.Thread(target=loop, daemon=True)
        self._poll_thread.start()

        return self._poll_thread

    def close(self):
        """Закрыть соединение с сервером."""
        self.game_id = None
        self._poll_stop.set()

        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=2.0)

        self.session.close()

    def save_player_session(self, filename: str = "player_config.json") -> bool:
        """Сохранить ID игрока в файл."""
        if not self.player_id:
            return False

        try:
            filepath = os.path.join(os.getcwd(), filename)
            with open(filepath, 'w', encoding='utf-8') as file:
                json.dump({'player_id': self.player_id}, file, ensure_ascii=False)
            return True
        except Exception:
            return False

    def load_player_session(self, filename: str = "player_config.json") -> bool:
        """Загрузить ID игрока из файла."""
        filepath = os.path.join(os.getcwd(), filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as file:
                data = json.load(file)
                self.player_id = data.get('player_id')
                return self.player_id is not None
        return False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False