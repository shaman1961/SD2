import arcade
from arcade.gui import UIManager, UIFlatButton, UIAnchorLayout, UIBoxLayout, UIImage, UILabel, UIInputText
import game
from network_client import NetworkClient
import time

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080

COUNTRIES_BY_YEAR = {
    1938: ["Германия", "СССР", "Британия", "Франция", "Италия", "Польша", "Чехословакия", "Испания", "Турция", "Швеция",
           "Румыния", "Венгрия", "Югославия", "Греция", "Бельгия", "Нидерланды", "Дания", "Норвегия", "Финляндия", "Португалия",
           "Швейцария", "Ирландия", "Болгария", "Австрия", "Литва", "Латвия", "Эстония"],
    1941: ["Германия", "СССР", "Британия", "Италия", "Словакия", "Франция Виши", "Свободная Франция", "Хорватия",
           "Венгрия", "Румыния", "Болгария", "Финляндия", "Швеция", "Швейцария", "Португалия", "Испания", "Турция", "Ирландия"]
}

BG = (242, 238, 228)
DARK = (40, 40, 40)
MID = (110, 110, 110)
GREEN = (100, 180, 100)
RED = (180, 100, 100)

# 🔧 Исправлены ключи стилей (убраны пробелы, иначе arcade.gui их игнорирует)
MAIN_BUTTON_STYLE = {
    "normal": {"font_name": ("Courier New",), "font_size": 26, "font_color": DARK, "bg": (0, 0, 0, 0), "border": 0},
    "hover": {"font_color": (0, 0, 0), "bg": (220, 215, 205, 160)},
    "press": {"font_color": (0, 0, 0), "bg": (210, 205, 195, 180)}
}

COUNTRY_BUTTON_STYLE = {
    "normal": {"font_name": ("Courier New",), "font_size": 18, "font_color": DARK, "bg": (0, 0, 0, 0), "border": 0},
    "hover": {"font_color": (0, 0, 0), "bg": (220, 215, 205, 160)},
    "press": {"font_color": (0, 0, 0), "bg": (210, 205, 195, 180)}
}

def get_max_players_for_year(year):
    return len(COUNTRIES_BY_YEAR.get(year, []))

class MultiplayerMenu(arcade.View):
    """Главное меню мультиплеера — список комнат с сервера"""
    def __init__(self):
        super().__init__()
        arcade.set_background_color(BG)
        self.client = NetworkClient(
            server_url="http://192.168.0.148:5443",
            secret_code="SteelDawn2024"
        )
        self.client.load_player_session()
        self.rooms = []
        self.last_refresh = 0
        self.refresh_interval = 3.0
        self.player_name = None
        self.pending_join_room = None  # 🔧 Для корректного возврата после регистрации

    def on_show_view(self):
        self._fetch_rooms()
        self.setup_gui()

    def on_update(self, delta_time):
        self.last_refresh += delta_time
        if self.last_refresh >= self.refresh_interval:
            self.last_refresh = 0
            self._fetch_rooms()
            self._update_room_list()  # 🔧 Обновляем только список комнат, а не весь UI

    def _fetch_rooms(self):
        try:
            self.rooms = self.client.get_games_list()
        except Exception as e:
            print(f"Ошибка получения комнат: {e}")
            self.rooms = []

    def setup_gui(self):
        if hasattr(self, 'manager'):
            self.manager.disable()

        self.manager = UIManager()
        self.manager.enable()

        title_label = UILabel(text="МУЛЬТИПЛЕЕР", font_size=48, text_color=DARK, font_name=("Courier New",))
        title_anchor = UIAnchorLayout()
        title_anchor.add(title_label, anchor_x="center", anchor_y="top", align_y=-100)
        self.manager.add(title_anchor)

        back_btn = UIFlatButton(text="< НАЗАД", width=250, height=75, style=MAIN_BUTTON_STYLE)
        back_btn.on_click = lambda e: self.window.show_view(GameModeMenu())
        back_anchor = UIAnchorLayout()
        back_anchor.add(back_btn, anchor_x="left", anchor_y="top", align_x=20, align_y=-20)
        self.manager.add(back_anchor)

        main_box = UIBoxLayout(vertical=True, space_between=25)
        main_box.with_padding(top=20, bottom=20, left=40, right=40)

        def on_create_click():
            if self.client.player_id:
                self.window.show_view(CreateRoomView(
                    self.client, self.client.player_id, player_name=self.player_name or "Игрок"
                ))
            else:
                self.window.show_view(PlayerRegistrationView(
                    self.client, callback=self._on_registration_done
                ))

        create_btn = UIFlatButton(text="СОЗДАТЬ КОМНАТУ", width=600, height=55, style=MAIN_BUTTON_STYLE)
        create_btn.on_click = lambda e: on_create_click()
        main_box.add(create_btn)

        divider = UILabel(text="─" * 60, font_size=16, text_color=MID)
        main_box.add(divider)

        rooms_title = UILabel(text="ДОСТУПНЫЕ КОМНАТЫ:", font_size=22, text_color=DARK, font_name=("Courier New",))
        main_box.add(rooms_title)

        self.rooms_box = UIBoxLayout(vertical=True, space_between=12)  # 🔧 Сохраняем ссылку
        self._update_room_list()
        main_box.add(self.rooms_box)

        refresh_label = UILabel(text="🔄 Автообновление...", font_size=14, text_color=MID, font_name=("Courier New",))
        main_box.add(refresh_label)

        root = UIAnchorLayout()
        root.add(main_box, anchor_x="center", anchor_y="center")
        self.manager.add(root)

    def _update_room_list(self):
        """🔧 Обновляет только контейнер комнат, не пересоздавая весь UI"""
        if not hasattr(self, 'rooms_box') or not self.rooms_box:
            return
        self.rooms_box.clear()

        if not self.rooms:
            self.rooms_box.add(UILabel(text="Нет доступных комнат. Создайте свою!", font_size=20, text_color=MID, font_name=("Courier New",)))
            return

        for room in self.rooms:
            max_players = get_max_players_for_year(room.get("year", 1938))
            players_count = room.get("players_count", 0)

            if room.get("locked", False):
                room_text = f"{room['name']} | {room['year']} | {players_count}/{max_players} (ИГРА НАЧИНАЕТСЯ)"
                room_btn = UIFlatButton(text=room_text, width=700, height=50, style=MAIN_BUTTON_STYLE)
                room_btn.style["normal"]["font_color"] = RED
                room_btn.on_click = lambda e: None
            else:
                room_text = f"{room['name']} | {room['year']} | {players_count}/{max_players} игроков"
                room_btn = UIFlatButton(text=room_text, width=700, height=50, style=MAIN_BUTTON_STYLE)

                def on_room_click(room_data):
                    if self.client.player_id:
                        self._join_room_direct(room_data)
                    else:
                        self.pending_join_room = room_data
                        self.window.show_view(PlayerRegistrationView(
                            self.client, callback=self._on_registration_done
                        ))

                room_btn.on_click = lambda e, r=room: on_room_click(r)

            self.rooms_box.add(room_btn)

    def _on_registration_done(self, player_id, player_name=None):
        if player_id:
            self.player_name = player_name or "Игрок"
            # 🔧 Если игрок пытался зайти в комнату до регистрации — возвращаем его туда
            if self.pending_join_room:
                room = self.pending_join_room
                self.pending_join_room = None
                self._join_room_direct(room)
            else:
                self.window.show_view(CreateRoomView(
                    self.client, player_id, player_name=self.player_name
                ))

    def _join_room_direct(self, room):
        game_id = room.get('id')
        if not game_id:
            print("❌ Ошибка: нет ID комнаты")
            return

        occupied = [p.get('country') for p in room.get('players', []) if p.get('country')]
        available = [c for c in COUNTRIES_BY_YEAR.get(room.get('year', 1938), [])
                     if c not in occupied]

        country = available[0] if available else None
        if not country:
            print("❌ Нет свободных стран")
            return

        success = self.client.join_game(game_id, country)
        if success:
            room_data = {
                "id": game_id, "name": room.get('name', 'Комната'),
                "year": room.get('year', 1938), "players": room.get('players', []), "is_host": False
            }
            self.window.show_view(MultiplayerLobbyView(self.client, self.client.player_id, room_data))
        else:
            print("❌ Не удалось присоединиться")

    def on_hide_view(self):
        if self.manager:
            self.manager.disable()
        # 🔧 Безопасная остановка фонового потока
        if hasattr(self, 'poll_thread') and self.poll_thread and self.poll_thread.is_alive():
            self.poll_thread.join(timeout=1.0)

    def on_draw(self):
        self.clear()
        self.manager.draw()


class PlayerRegistrationView(arcade.View):
    """Экран регистрации игрока перед мультиплеером"""
    def __init__(self, client, callback=None):
        super().__init__()
        arcade.set_background_color(BG)
        self.client = client
        self.callback = callback
        self.player_name = " "

    def on_show_view(self):
        self.setup_gui()

    def setup_gui(self):
        if hasattr(self, 'manager'):
            self.manager.disable()

        self.manager = UIManager()
        self.manager.enable()

        title_label = UILabel(text="РЕГИСТРАЦИЯ", font_size=48, text_color=DARK, font_name=("Courier New",))
        title_anchor = UIAnchorLayout()
        title_anchor.add(title_label, anchor_x="center", anchor_y="top", align_y=-100)
        self.manager.add(title_anchor)

        back_btn = UIFlatButton(text="< НАЗАД", width=250, height=75, style=MAIN_BUTTON_STYLE)
        back_btn.on_click = lambda e: self.window.show_view(MultiplayerMenu())
        back_anchor = UIAnchorLayout()
        back_anchor.add(back_btn, anchor_x="left", anchor_y="top", align_x=20, align_y=-20)
        self.manager.add(back_anchor)

        settings_box = UIBoxLayout(vertical=True, space_between=25)
        settings_box.with_padding(top=30, bottom=30, left=50, right=50)

        name_label = UILabel(text="Ваше имя:", font_size=22, text_color=DARK, font_name=("Courier New",))
        settings_box.add(name_label)

        self.name_input = UIInputText(
            text="Игрок", width=400, height=45, font_size=20, font_name=("Courier New",),
            text_color=(40, 40, 40), bg_color=(200, 200, 200, 255), caret_color=(40, 40, 40)
        )
        settings_box.add(self.name_input)

        register_btn = UIFlatButton(text="ЗАРЕГИСТРИРОВАТЬСЯ", width=350, height=55, style=MAIN_BUTTON_STYLE)
        register_btn.on_click = lambda e: self._register()
        settings_box.add(register_btn)

        self.error_label = UILabel(text=" ", font_size=16, text_color=RED, font_name=("Courier New",))
        settings_box.add(self.error_label)

        root = UIAnchorLayout()
        root.add(settings_box, anchor_x="center", anchor_y="center")
        self.manager.add(root)

    def on_key_press(self, key, modifiers):
        if hasattr(self, 'manager'):
            self.manager.on_key_press(key, modifiers)

    def _register(self):
        self.player_name = self.name_input.text.strip()
        if not self.player_name:
            self.error_label.text = "Введите имя!"
            return

        player_id = self.client.register(self.player_name)
        if player_id:
            print(f"Зарегистрирован: {player_id}")
            if self.callback:
                self.callback(player_id, self.player_name)
        else:
            self.error_label.text = "Ошибка регистрации. Проверьте сервер."

    def on_hide_view(self):
        if self.manager:
            self.manager.disable()

    def on_draw(self):
        self.clear()
        self.manager.draw()


class CreateRoomView(arcade.View):
    """Создание комнаты через API"""
    def __init__(self, client, player_id, player_name="Игрок"):
        super().__init__()
        arcade.set_background_color(BG)
        self.client = client
        self.player_id = player_id
        self.player_name = player_name
        self.room_name = " "
        self.scenario_year = 1938
        self.max_players = get_max_players_for_year(1938)

    def on_show_view(self):
        self.setup_gui()

    def setup_gui(self):
        if hasattr(self, 'manager'):
            self.manager.disable()

        self.manager = UIManager()
        self.manager.enable()

        title_label = UILabel(text="СОЗДАНИЕ КОМНАТЫ", font_size=48, text_color=DARK, font_name=("Courier New",))
        title_anchor = UIAnchorLayout()
        title_anchor.add(title_label, anchor_x="center", anchor_y="top", align_y=-100)
        self.manager.add(title_anchor)

        back_btn = UIFlatButton(text="< НАЗАД", width=250, height=75, style=MAIN_BUTTON_STYLE)
        back_btn.on_click = lambda e: self.window.show_view(MultiplayerMenu())
        back_anchor = UIAnchorLayout()
        back_anchor.add(back_btn, anchor_x="left", anchor_y="top", align_x=20, align_y=-20)
        self.manager.add(back_anchor)

        settings_box = UIBoxLayout(vertical=True, space_between=25)
        settings_box.with_padding(top=30, bottom=30, left=50, right=50)

        name_label = UILabel(text="Название комнаты:", font_size=22, text_color=DARK, font_name=("Courier New",))
        settings_box.add(name_label)

        self.name_input = UIInputText(
            text="Моя комната", width=500, height=45, font_size=20, font_name=("Courier New",),
            text_color=(40, 40, 40), bg_color=(200, 200, 200, 255), caret_color=(40, 40, 40)
        )
        settings_box.add(self.name_input)

        scenario_label = UILabel(text="Сценарий:", font_size=22, text_color=DARK, font_name=("Courier New",))
        settings_box.add(scenario_label)

        scenario_box = UIBoxLayout(vertical=False, space_between=25)
        btn_1938 = UIFlatButton(text="1938", width=180, height=45, style=MAIN_BUTTON_STYLE)
        btn_1938.on_click = lambda e: self._set_scenario(1938)
        scenario_box.add(btn_1938)

        btn_1941 = UIFlatButton(text="1941", width=180, height=45, style=MAIN_BUTTON_STYLE)
        btn_1941.on_click = lambda e: self._set_scenario(1941)
        scenario_box.add(btn_1941)
        settings_box.add(scenario_box)

        self.scenario_info = UILabel(text=f"Выбрано: {self.scenario_year} ({self.max_players} стран доступно)",
                                     font_size=18, text_color=MID, font_name=("Courier New",))
        settings_box.add(self.scenario_info)

        divider = UILabel(text="─" * 40, font_size=16, text_color=MID)
        settings_box.add(divider)

        create_btn = UIFlatButton(text="СОЗДАТЬ КОМНАТУ", width=400, height=55, style=MAIN_BUTTON_STYLE)
        create_btn.on_click = lambda e: self._create_room()
        settings_box.add(create_btn)

        root = UIAnchorLayout()
        root.add(settings_box, anchor_x="center", anchor_y="center")
        self.manager.add(root)

    def on_key_press(self, key, modifiers):
        if hasattr(self, 'manager'):
            self.manager.on_key_press(key, modifiers)

    def _set_scenario(self, year):
        self.scenario_year = year
        self.max_players = get_max_players_for_year(year)
        self.scenario_info.text = f"Выбрано: {self.scenario_year} ({self.max_players} стран доступно)"

    def _create_room(self):
        self.room_name = self.name_input.text.strip()
        if not self.room_name:
            print("Введите название комнаты!")
            return

        game_id = self.client.create_game(year=self.scenario_year, turn_time=180)
        if game_id:
            room_data = {
                "id": game_id, "name": self.room_name, "year": self.scenario_year,
                "players": [{"name": self.player_name, "country": None, "ready": False, "is_host": True, "player_id": self.player_id}],
                "is_host": True
            }
            self.window.show_view(MultiplayerLobbyView(self.client, self.player_id, room_data))
        else:
            print("Ошибка создания комнаты")

    def on_hide_view(self):
        if self.manager:
            self.manager.disable()

    def on_draw(self):
        self.clear()
        self.manager.draw()


class MultiplayerLobbyView(arcade.View):
    """Лобби комнаты — выбор стран, готовность, чат, таймер"""
    def __init__(self, client, player_id, room_data):
        super().__init__()
        arcade.set_background_color(BG)
        self.client = client
        self.player_id = player_id
        self.room = room_data
        self.game_id = room_data.get("id")
        self.year = room_data.get("year", 1938)
        self.countries = COUNTRIES_BY_YEAR.get(self.year, [])
        self.max_players = len(self.countries)
        self.players = room_data.get("players", [])
        self.my_country = None
        self.country_selected = False
        self.is_ready = False
        self.is_host = room_data.get("is_host", False)
        self.poll_thread = None
        self.time_left = None
        self.bot_mode_enabled = False
        self.pending_state = None  # 🔧 Очередь для безопасного обновления GUI

    def on_show_view(self):
        self.setup_gui()
        self.poll_thread = self.client.poll_updates(self._on_game_state_update, interval=1.0)

    def on_update(self, delta_time):
        # 🔧 Применяем сетевое состояние только в главном потоке
        if self.pending_state is not None:
            self._apply_state_update(self.pending_state)
            self.pending_state = None

    def _on_game_state_update(self, state):
        # 🔧 Только запоминаем данные, НЕ трогаем GUI
        self.pending_state = state

    def _apply_state_update(self, state):
        self.players = state.get("players", [])
        self.time_left = state.get("time_left")
        self.bot_mode_enabled = state.get("bot_mode_enabled", False)

        for player in self.players:
            if player.get("player_id") == self.player_id:
                if player.get("country"):
                    self.my_country = player.get("country")
                    self.country_selected = True
                break

        if state.get("state") == "playing":
            self._start_game()
            return

        self.setup_gui()

    def setup_gui(self):
        if hasattr(self, 'manager'):
            self.manager.disable()

        self.manager = UIManager()
        self.manager.enable()

        title_label = UILabel(text=f"ЛОББИ: {self.room.get('name', 'Комната')}", font_size=40, text_color=DARK, font_name=("Courier New",))
        title_anchor = UIAnchorLayout()
        title_anchor.add(title_label, anchor_x="center", anchor_y="top", align_y=-80)
        self.manager.add(title_anchor)

        back_btn = UIFlatButton(text="< НАЗАД", width=250, height=75, style=MAIN_BUTTON_STYLE)
        back_btn.on_click = lambda e: self._leave_and_back()
        back_anchor = UIAnchorLayout()
        back_anchor.add(back_btn, anchor_x="left", anchor_y="top", align_x=20, align_y=-20)
        self.manager.add(back_anchor)

        main_layout = UIBoxLayout(vertical=False, space_between=40)
        main_layout.with_padding(top=20, bottom=20, left=40, right=40)

        left_column = UIBoxLayout(vertical=True, space_between=20)
        left_column.with_padding(top=20, bottom=20, left=20, right=20)

        players_title = UILabel(text=f"ИГРОКИ ({len(self.players)}/{self.max_players}):", font_size=20, text_color=DARK, font_name=("Courier New",))
        left_column.add(players_title)

        players_box = UIBoxLayout(vertical=True, space_between=10)
        for player in self.players:
            player_row = UIBoxLayout(vertical=False, space_between=10)
            if player.get("country"):
                flag_path = f"images/flags/{player['country']}.png"
                try:
                    texture = arcade.load_texture(flag_path)
                    flag = UIImage(texture=texture, width=50, height=35)
                except:
                    flag = UILabel(text=player["country"][:3], width=50, height=35)
            else:
                flag = UILabel(text="---", width=50, height=35)

            player_row.add(flag)
            status = "[ГОТОВ]" if player.get("ready", False) else "[НЕ ГОТОВ]"
            host_mark = " (Х)" if player.get("is_host", False) else ""
            country_text = player.get("country") if player.get("country") else "—"
            player_info = UILabel(text=f"{player.get('name', 'Игрок')[:15]}{host_mark}\n{country_text} {status}",
                                  font_size=14, text_color=DARK, font_name=("Courier New",), width=180)
            player_row.add(player_info)
            players_box.add(player_row)
        left_column.add(players_box)

        if self.time_left is not None and self.time_left > 0:
            timer_label = UILabel(text=f"Игра начнётся через {int(self.time_left)} сек", font_size=24, text_color=RED, font_name=("Courier New",), bold=True)
            left_column.add(timer_label)

        ready_box = UIBoxLayout(vertical=True, space_between=15)
        self.ready_btn = UIFlatButton(text="ГОТОВ" if not self.is_ready else "НЕ ГОТОВ", width=220, height=45, style=MAIN_BUTTON_STYLE)
        self.ready_btn.on_click = lambda e: self._toggle_ready()
        ready_box.add(self.ready_btn)

        if self.is_host and not self.bot_mode_enabled:
            bots_btn = UIFlatButton(text="ИГРАТЬ С БОТАМИ", width=220, height=45, style=MAIN_BUTTON_STYLE)
            bots_btn.on_click = lambda e: self._enable_bots()
            ready_box.add(bots_btn)

        if self.is_host and len(self.players) >= 2 and not self.bot_mode_enabled:
            start_btn = UIFlatButton(text="НАЧАТЬ ИГРУ", width=220, height=45, style=MAIN_BUTTON_STYLE)
            start_btn.on_click = lambda e: self._start_game()  # 🔧 Исправлено: было _enable_bots()
            ready_box.add(start_btn)

        left_column.add(ready_box)
        main_layout.add(left_column)

        right_column = UIBoxLayout(vertical=True, space_between=15)
        right_column.with_padding(top=20, bottom=20, left=20, right=20)

        countries_title = UILabel(text="ВЫБЕРИТЕ СТРАНУ:", font_size=20, text_color=DARK, font_name=("Courier New",))
        right_column.add(countries_title)

        countries_grid = UIBoxLayout(vertical=False, space_between=6)
        columns = [UIBoxLayout(vertical=True, space_between=6) for _ in range(6)]
        occupied = [p.get("country") for p in self.players if p.get("country")]

        for i, country in enumerate(self.countries):
            is_occupied = country in occupied
            btn = UIFlatButton(text=f"  > {country.upper()}", width=160, height=35, style=COUNTRY_BUTTON_STYLE)

            if is_occupied:
                btn.style = {"normal": {"font_color": RED, "bg": (180, 100, 100, 80), "border": 0},
                             "hover": {"font_color": RED, "bg": (200, 120, 120, 100), "border": 0},
                             "press": {"font_color": RED, "bg": (180, 100, 100, 80), "border": 0}}
                btn.on_click = lambda e: None
            else:
                btn.style = {"normal": {"font_color": GREEN, "bg": (100, 180, 100, 80), "border": 0},
                             "hover": {"font_color": DARK, "bg": (220, 215, 205, 160), "border": 0},
                             "press": {"font_color": DARK, "bg": (210, 205, 195, 180), "border": 0}}
                if self.country_selected:
                    btn.on_click = lambda e: None
                else:
                    btn.on_click = lambda e, c=country: self._select_country(c)
            columns[i % 6].add(btn)

        for col in columns:
            countries_grid.add(col)
        right_column.add(countries_grid)
        main_layout.add(right_column)

        root = UIAnchorLayout()
        root.add(main_layout, anchor_x="center", anchor_y="center", align_y=-30)
        self.manager.add(root)

    def on_key_press(self, key, modifiers):
        if hasattr(self, 'manager'):
            self.manager.on_key_press(key, modifiers)

    def _leave_and_back(self):
        self.client.leave_game()
        self.window.show_view(MultiplayerMenu())

    def _select_country(self, country):
        if self.country_selected:
            print(f"⚠️ Страна уже выбрана: {self.my_country}")
            return
        occupied = [p.get("country") for p in self.players if p.get("country")]
        if country in occupied:
            print(f"⚠️ Страна {country} уже занята")
            return

        self.my_country = country
        self.country_selected = True
        print(f"Выбрано: {country}")
        success = self.client.join_game(self.game_id, country)
        if success:
            for player in self.players:
                if player.get("player_id") == self.player_id:
                    player["country"] = country
                    break
            self.setup_gui()
        else:
            self.country_selected = False

    def _toggle_ready(self):
        if not self.my_country:
            print("⚠️ Сначала выберите страну!")
            return
        self.is_ready = not self.is_ready
        self.ready_btn.text = "ГОТОВ" if not self.is_ready else "НЕ ГОТОВ"

    def _enable_bots(self):
        if self.client.enable_bots():
            self.bot_mode_enabled = True
            print("🤖 Режим с ботами включён, таймер запущен")

    def _start_game(self):
        print("Запуск игры...")
        self.client.leave_game()
        self.window.show_view(game.Game(
            self.year, self.my_country or "Германия", is_new_game=True,
            is_multiplayer=True, client=self.client
        ))

    def on_hide_view(self):
        if self.manager:
            self.manager.disable()
        if self.poll_thread and self.poll_thread.is_alive():
            self.poll_thread.join(timeout=1.0)
        if self.client:
            self.client.close()

    def on_draw(self):
        self.clear()
        self.manager.draw()

from menu import GameModeMenu
