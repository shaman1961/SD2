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
        self.rooms = []
        self.last_refresh = 0
        self.refresh_interval = 3.0
        self.player_name = None
        self.pending_join_room = None

    def on_show_view(self):
        self._fetch_rooms()
        self.setup_gui()

    def on_update(self, delta_time):
        self.last_refresh += delta_time
        if self.last_refresh >= self.refresh_interval:
            self.last_refresh = 0
            self._fetch_rooms()
            self._update_room_list()

    def _fetch_rooms(self):
        try:
            self.rooms = self.client.get_games_list()
        except Exception as e:
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

        self.rooms_box = UIBoxLayout(vertical=True, space_between=12)
        self._update_room_list()
        main_box.add(self.rooms_box)

        refresh_label = UILabel(text="Автообновление...", font_size=14, text_color=MID, font_name=("Courier New",))
        main_box.add(refresh_label)

        root = UIAnchorLayout()
        root.add(main_box, anchor_x="center", anchor_y="center")
        self.manager.add(root)

    def _update_room_list(self):
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
            return

        state = self.client._req('GET', f'/api/game/{game_id}/state')
        if not state:
            return

        game_state = state.json()

        room_data = {
            "id": game_id, "name": room.get('name', 'Комната'),
            "year": game_state.get('year', 1938),
            "players": game_state.get('players', []),
            "is_host": False
        }
        self.window.show_view(MultiplayerLobbyView(self.client, self.client.player_id, room_data))

    def on_hide_view(self):
        if self.manager:
            self.manager.disable()

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

        register_btn = UIFlatButton(text="ЗАРЕГИСТРИРОВАТЬСЯ", width=400, height=55, style=MAIN_BUTTON_STYLE)
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
            return

        game_id = self.client.create_game(year=self.scenario_year, turn_time=180)

        if not game_id:
            self.client.player_id = None
            self.window.show_view(PlayerRegistrationView(
                self.client,
                callback=lambda pid, name: self._retry_create_room(pid, name)
            ))
            return

        room_data = {
            "id": game_id, "name": self.room_name, "year": self.scenario_year,
            "players": [{"name": self.player_name, "country": None, "ready": False, "is_host": True,
                         "player_id": self.player_id}],
            "is_host": True
        }
        self.window.show_view(MultiplayerLobbyView(self.client, self.player_id, room_data))

    def _retry_create_room(self, player_id, player_name):
        self.player_id = player_id
        self.player_name = player_name

        game_id = self.client.create_game(year=self.scenario_year, turn_time=180)
        if game_id:
            room_data = {
                "id": game_id, "name": self.room_name, "year": self.scenario_year,
                "players": [{"name": self.player_name, "country": None, "ready": False, "is_host": True,
                             "player_id": self.player_id}],
                "is_host": True
            }
            self.window.show_view(MultiplayerLobbyView(self.client, self.player_id, room_data))
        else:
            pass

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
        self.time_left = None
        self.bot_mode_enabled = False
        self.poll_timer = 0
        self.poll_interval = 1.0
        self._game_started = False

    def on_show_view(self):
        self.setup_gui()

    def on_update(self, delta_time):
        self.poll_timer += delta_time
        if self.poll_timer >= self.poll_interval:
            self.poll_timer = 0
            state = self.client.get_game_state()
            if state:
                self._apply_state_update(state)

    def _apply_state_update(self, state):
        if not state:
            return

        if state.get("state") == "playing":
            if not self._game_started:
                self._game_started = True
                self._start_game()
            return

        self.players = state.get("players", [])
        self.time_left = state.get("time_left")
        self.bot_mode_enabled = state.get("bot_mode_enabled", False)

        for player in self.players:
            if player.get("player_id") == self.player_id:
                if player.get("country"):
                    self.my_country = player.get("country")
                    self.country_selected = True
                break

        self.setup_gui()

    def setup_gui(self):
        if hasattr(self, 'manager'):
            self.manager.disable()

        self.manager = UIManager()
        self.manager.enable()

        title_label = UILabel(
            text=f"ЛОББИ: {self.room.get('name', 'Комната')}",
            font_size=36,
            text_color=DARK,
            font_name=("Courier New",),
            bold=True
        )
        title_anchor = UIAnchorLayout()
        title_anchor.add(title_label, anchor_x="center", anchor_y="top", align_y=-60)
        self.manager.add(title_anchor)

        year_label = UILabel(
            text=f"Сценарий: {self.year}",
            font_size=20,
            text_color=MID,
            font_name=("Courier New",)
        )
        year_anchor = UIAnchorLayout()
        year_anchor.add(year_label, anchor_x="center", anchor_y="top", align_y=-110)
        self.manager.add(year_anchor)

        back_btn = UIFlatButton(text="< НАЗАД", width=200, height=60, style=MAIN_BUTTON_STYLE)
        back_btn.on_click = lambda e: self._leave_and_back()
        back_anchor = UIAnchorLayout()
        back_anchor.add(back_btn, anchor_x="left", anchor_y="top", align_x=20, align_y=-20)
        self.manager.add(back_anchor)

        if self.time_left is not None and self.time_left > 0:
            timer_label = UILabel(
                text=f"Игра начнется через {int(self.time_left)} сек",
                font_size=24,
                text_color=RED,
                font_name=("Courier New",),
                bold=True
            )
            timer_anchor = UIAnchorLayout()
            timer_anchor.add(timer_label, anchor_x="center", anchor_y="top", align_y=-160)
            self.manager.add(timer_anchor)

        main_layout = UIBoxLayout(vertical=False, space_between=30)
        main_layout.with_padding(top=10, bottom=10, left=30, right=30)

        left_panel = UIBoxLayout(vertical=True, space_between=12)
        left_panel.with_padding(top=15, bottom=15, left=15, right=15)
        left_panel.with_background(color=(28, 30, 34, 200))
        left_panel.width = 380
        left_panel.height = 600

        players_title = UILabel(
            text=f"ИГРОКИ ({len(self.players)}/{self.max_players})",
            font_size=18,
            text_color=(255, 255, 255),
            font_name=("Courier New",),
            bold=True,
            width=350
        )
        left_panel.add(players_title)
        left_panel.add(UILabel(text="─" * 30, font_size=12, text_color=MID, width=350))

        for player in self.players:
            player_box = UIBoxLayout(vertical=False, space_between=10)
            player_box.with_padding(top=5, bottom=5, left=5, right=5)

            host_mark = "[HOST]" if player.get("is_host", False) else ""
            ready_mark = "1" if player.get("ready", False) else "0"
            name = player.get('name', 'Игрок')[:12]
            country_name = player.get("country") or "---"

            player_info = UILabel(
                text=f"{host_mark} {ready_mark} {name}\n    {country_name}",
                font_size=14,
                text_color=(220, 220, 220),
                font_name=("Courier New",),
                width=250,
                align="left"
            )
            player_box.add(player_info)
            left_panel.add(player_box)

        button_box = UIBoxLayout(vertical=True, space_between=8)
        button_box.with_padding(top=10, bottom=0, left=0, right=0)

        if not self.is_ready:
            ready_btn = UIFlatButton(text="[ГОТОВ]", width=350, height=45, style=MAIN_BUTTON_STYLE)
            ready_btn.on_click = lambda e: self._toggle_ready()
            button_box.add(ready_btn)

        if self.is_host:
            if not self.bot_mode_enabled:
                bots_btn = UIFlatButton(text="ИГРАТЬ С БОТАМИ", width=350, height=45, style=MAIN_BUTTON_STYLE)
                bots_btn.on_click = lambda e: self._enable_bots()
                button_box.add(bots_btn)

            all_chose = all(p.get("country") is not None for p in self.players)
            all_ready = all(p.get("ready", False) for p in self.players)

            if (all_chose and all_ready) or self.bot_mode_enabled:
                start_btn = UIFlatButton(text="НАЧАТЬ ИГРУ", width=350, height=50, style=MAIN_BUTTON_STYLE)
                start_btn.on_click = lambda e: self._start_countdown()
                button_box.add(start_btn)

        left_panel.add(button_box)
        main_layout.add(left_panel)

        right_panel = UIBoxLayout(vertical=True, space_between=8, align="top")
        right_panel.with_padding(top=15, bottom=15, left=15, right=15)
        right_panel.with_background(color=(28, 30, 34, 200))
        right_panel.width = 850
        right_panel.height = 600

        countries_title = UILabel(
            text="ВЫБОР СТРАНЫ",
            font_size=18,
            text_color=(255, 255, 255),
            font_name=("Courier New",),
            bold=True,
            width=820
        )
        right_panel.add(countries_title)
        right_panel.add(UILabel(text="─" * 65, font_size=12, text_color=MID, width=820))

        if self.my_country:
            selected_label = UILabel(
                text=f"Выбрано: {self.my_country}",
                font_size=16,
                text_color=GREEN,
                font_name=("Courier New",),
                bold=True,
                width=820
            )
            right_panel.add(selected_label)

        num_cols = 5
        countries_grid = UIBoxLayout(vertical=False, space_between=8, align="top")
        columns = [UIBoxLayout(vertical=True, space_between=4, align="top") for _ in range(num_cols)]
        occupied = [p.get("country") for p in self.players if p.get("country")]

        for i, country in enumerate(self.countries):
            is_occupied = country in occupied
            is_my_country = country == self.my_country
            btn_width = 160
            btn_height = 38

            if is_my_country:
                btn_text = f"* {country}"
                btn = UIFlatButton(text=btn_text, width=btn_width, height=btn_height, style=COUNTRY_BUTTON_STYLE)
                btn.enabled = False
            elif is_occupied:
                btn_text = f"  {country}"
                btn = UIFlatButton(text=btn_text, width=btn_width, height=btn_height, style=COUNTRY_BUTTON_STYLE)
                btn.enabled = False
            elif self.country_selected:
                btn_text = f"  {country}"
                btn = UIFlatButton(text=btn_text, width=btn_width, height=btn_height, style=COUNTRY_BUTTON_STYLE)
                btn.enabled = False
            else:
                btn_text = f"  {country}"
                btn = UIFlatButton(text=btn_text, width=btn_width, height=btn_height, style=COUNTRY_BUTTON_STYLE)
                btn.on_click = lambda e, c=country: self._select_country(c)

            columns[i % num_cols].add(btn)

        for col in columns:
            countries_grid.add(col)

        right_panel.add(countries_grid)
        main_layout.add(right_panel)

        root = UIAnchorLayout()
        root.add(main_layout, anchor_x="center", anchor_y="center")
        self.manager.add(root)

    def on_key_press(self, key, modifiers):
        if hasattr(self, 'manager'):
            self.manager.on_key_press(key, modifiers)

    def _leave_and_back(self):
        self.client.leave_game()
        self.window.show_view(MultiplayerMenu())

    def _select_country(self, country):
        if self.country_selected:
            return

        occupied = [p.get("country") for p in self.players if p.get("country")]
        if country in occupied:
            return

        self.my_country = country
        self.country_selected = True

        success = self.client.join_game(self.game_id, country)
        if success:
            for player in self.players:
                if player.get("player_id") == self.player_id:
                    player["country"] = country
                    break
            self.setup_gui()
        else:
            self.country_selected = False
            self.my_country = None

    def _toggle_ready(self):
        if not self.my_country:
            return
        self.is_ready = True
        self.client._req('POST', f'/api/game/{self.game_id}/ready',
                         json={"player_id": self.player_id})
        for player in self.players:
            if player.get("player_id") == self.player_id:
                player["ready"] = True
                break
        self.setup_gui()

    def _enable_bots(self):
        if self.client.enable_bots():
            self.bot_mode_enabled = True

    def _start_countdown(self):
        """Запуск обратного отсчёта"""
        if self.is_host:
            self.client._req('POST', f'/api/game/{self.game_id}/start',
                             json={"player_id": self.player_id})

    def _start_game(self):
        self.client.game_id = self.game_id
        game_view = game.Game(
            self.year,
            self.my_country or "Германия",
            is_new_game=True,
            is_multiplayer=True,
            client=self.client
        )
        if self.window:
            self.window.show_view(game_view)

    def on_hide_view(self):
        if self.manager:
            self.manager.disable()

    def on_draw(self):
        self.clear()
        self.manager.draw()

from menu import GameModeMenu
