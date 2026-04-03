import arcade
from arcade.gui import (
    UIManager,
    UILabel,
    UIBoxLayout,
    UIMessageBox,
    UIFlatButton,
    UIAnchorLayout
)
from arcade.gui.experimental import UIScrollArea
from arcade.particles import FadeParticle, Emitter, EmitBurst
import json
from collections import Counter
import random
import time
import province
import menu
import stats_manager
from economy import Economy, ResourceType
from country import Country


class Game(arcade.View):
    def __init__(self, year: int, country: str, is_new_game: bool = True,
                 is_multiplayer: bool = False, client=None):
        super().__init__()
        self.moving = False
        self.prov_center = ""
        self.moving_army = False
        self.prov_name = ""
        self.prov_resource = ""
        self.last_prov_name = ""
        self.last_prov_centre = ""

        self.year = year
        self.country = country
        self.is_multiplayer = is_multiplayer
        self.client = client
        self.player_id = None
        self.game_id = None

        self.army_positions = {}
        self.province_owners = {}
        self.bot_armies = {}
        self.bot_countries = []
        self.current_bot_index = 0
        self.bot_turn_timer = 60
        self.bot_turn_active = False

        self.bot_gold = {}
        self.bot_provinces = {}

        self.army_sprite_cache = {}
        self.army_sprite_list = arcade.SpriteList()

        self.all_provinces = arcade.SpriteList()
        self.background = arcade.SpriteList()

        bg = arcade.Sprite("images/backgrounds/map.png")
        bg.center_x = bg.width // 2
        bg.center_y = bg.height // 2
        self.background.append(bg)
        bg_sprite = self.background[0]
        self.map_width = bg_sprite.width
        self.map_height = bg_sprite.height
        self.map_center_x = bg_sprite.center_x
        self.map_center_y = bg_sprite.center_y

        self.manager = None

        self.province_panel_opened = False
        self.country_panel_opened = False
        self.economics_panel_opened = False

        self.province_panel = None
        self.country_panel = None
        self.economics_panel = None
        self.moving_anchor = None

        self.message_anchor = None

        self.dragging = False
        self.turn = 0

        self.turn_time_limit = 180
        self.turn_timer = self.turn_time_limit
        self.turn_active = False
        self.turn_blocked = False

        self.last_mouse_x = 0
        self.last_mouse_y = 0

        self.min_zoom = 0.3
        self.max_zoom = 3.0

        self.pan_speed = 20.0
        self.keys = {
            key: False for key in (
                arcade.key.W,
                arcade.key.S,
                arcade.key.A,
                arcade.key.D
            )
        }

        self.world_camera = arcade.camera.Camera2D()
        self.gui_camera = arcade.camera.Camera2D()

        with open(f"provinces{self.year}.json", "r", encoding="utf-8") as provinces_file, \
                open(f"countries{self.year}.json", "r", encoding="utf-8") as countries_file:

            provinces_data = json.load(provinces_file)
            countries_data = json.load(countries_file)

            for name, data in countries_data.items():
                if name != self.country:
                    self.bot_gold[name] = data.get('gold', 100)
                    self.bot_provinces[name] = data.get('provinces', [])

            for country_name, country_data in countries_data.items():
                for prov_name in country_data.get('provinces', []):
                    self.province_owners[prov_name] = country_name

            country_data = countries_data[self.country]
            self.player_country = Country(
                name=self.country,
                color=country_data['color'],
                resources_list=country_data.get('resources', []),
                wheat=country_data.get('wheat', 0),
                metal=country_data.get('metal', 0),
                wood=country_data.get('wood', 0),
                coal=country_data.get('coal', 0),
                oil=country_data.get('oil', 0),
                provinces=country_data.get('provinces', []),
                capital=country_data.get('capital', ''),
                gold=country_data.get('gold', 100)
            )

            self.bot_countries = [name for name in countries_data.keys() if name != self.country]
            self.bot_countries.sort()

            capital = countries_data[self.country]["capital"]
            cap_key = capital.lower()
            if cap_key in provinces_data:
                self.world_camera.position = (
                    provinces_data[cap_key]["center_x"],
                    provinces_data[cap_key]["center_y"]
                )

        self.particle_emitters = []
        self._init_particle_textures()
        if is_new_game:
            self.overview()

        self._pending_save_data = None

        self.network = None
        if is_multiplayer and client:
            self._connect_to_server()

    def _connect_to_server(self):
        try:
            if self.client:
                self.network = self.client
                self.player_id = self.client.player_id
                self.game_id = self.client.game_id
                print(f"✅ Подключено к серверу: {self.player_id}")
        except Exception as e:
            print(f"⚠️ Не удалось подключиться к серверу: {e}")
            self.is_multiplayer = False

    def overview(self):
        with open(f"provinces{self.year}.json", "r", encoding="utf-8") as f, \
                open(f"countries{self.year}.json", "r", encoding="utf-8") as c:
            province_data = json.load(f)
            countries_data = json.load(c)

        print(f"✅ Игра инициализирована (сценарий {self.year})")

    def _init_particle_textures(self):
        self.victory_spark_textures = [
            arcade.make_soft_circle_texture(10, arcade.color.GOLD),
            arcade.make_soft_circle_texture(10, arcade.color.ORANGE_RED),
            arcade.make_soft_circle_texture(10, arcade.color.DARK_ORANGE),
            arcade.make_soft_circle_texture(10, arcade.color.SUNRAY),
        ]
        self.smoke_texture = arcade.make_soft_circle_texture(25, arcade.color.LIGHT_GRAY, 255, 80)
        self.flash_texture = arcade.make_soft_circle_texture(15, arcade.color.WHITE, 255, 120)

    def create_conquest_particles(self, x: float, y: float, conquering_color: tuple):
        explosion = Emitter(
            center_xy=(x, y),
            emit_controller=EmitBurst(70),
            particle_factory=lambda e: FadeParticle(
                filename_or_texture=random.choice(self.victory_spark_textures),
                change_xy=arcade.math.rand_in_circle((0.0, 0.0), 8.0),
                lifetime=random.uniform(0.7, 1.3),
                start_alpha=255,
                end_alpha=0,
                scale=random.uniform(0.4, 0.8),
                mutation_callback=lambda p: (
                    setattr(p, 'change_y', p.change_y - 0.08),
                    setattr(p, 'change_x', p.change_x * 0.94),
                    setattr(p, 'change_y', p.change_y * 0.94)
                ),
            ),
        )

        flash = Emitter(
            center_xy=(x, y),
            emit_controller=EmitBurst(15),
            particle_factory=lambda e: FadeParticle(
                filename_or_texture=self.flash_texture,
                change_xy=(0, 0),
                lifetime=0.3,
                start_alpha=220,
                end_alpha=0,
                scale=random.uniform(1.2, 2.0),
            ),
        )

        smoke = Emitter(
            center_xy=(x, y),
            emit_controller=EmitBurst(25),
            particle_factory=lambda e: FadeParticle(
                filename_or_texture=self.smoke_texture,
                change_xy=(random.uniform(-0.8, 0.8), random.uniform(1.0, 2.5)),
                lifetime=random.uniform(2.0, 3.0),
                start_alpha=180,
                end_alpha=0,
                scale=random.uniform(0.6, 1.0),
                mutation_callback=lambda p: (
                    setattr(p, 'scale', p.scale),
                    setattr(p, 'alpha', max(0, p.alpha - 2.0))
                ),
            ),
        )

        color_sparks = Emitter(
            center_xy=(x, y),
            emit_controller=EmitBurst(40),
            particle_factory=lambda e: FadeParticle(
                filename_or_texture=arcade.make_soft_circle_texture(
                    8,
                    (conquering_color[0], conquering_color[1], conquering_color[2])
                ),
                change_xy=arcade.math.rand_in_circle((0.0, 0.0), 6.0),
                lifetime=random.uniform(0.9, 1.6),
                start_alpha=240,
                end_alpha=30,
                scale=random.uniform(0.3, 0.6),
                mutation_callback=lambda p: (
                    setattr(p, 'change_y', p.change_y - 0.04),
                    setattr(p, 'scale', p.scale)
                ),
            ),
        )

        self.particle_emitters.extend([explosion, flash, smoke, color_sparks])

    def on_show_view(self):
        arcade.set_background_color((42, 44, 44))

        with open(f"countries{self.year}.json", "r", encoding="utf-8") as c_file:
            countries_data = json.load(c_file)

        with open(f"provinces{self.year}.json", "r", encoding="utf-8") as file:
            data = json.load(file)
            for name in data:
                prov = province.Province(
                    f"images/provinces/{name}.png",
                    data[name]["center_x"],
                    data[name]["center_y"],
                    data[name]["color"],
                    name,
                    data[name]["resource"]
                )
                self.all_provinces.append(prov)

                for country_name, country_data in countries_data.items():
                    if name in country_data.get('provinces', []):
                        self.province_owners[name] = country_name
                        prov.color = tuple(country_data['color'])
                        break

        self.manager = UIManager()
        self.manager.enable()

        for prov in self.all_provinces:
            with open(f"countries{self.year}.json", "r", encoding="utf-8") as f:
                countries_data = json.load(f)

            for country_name, country_data in countries_data.items():
                if prov.name in country_data.get('provinces', []):
                    self.province_owners[prov.name] = country_name
                    prov.color = tuple(country_data['color'])
                    break

        self.country_button = UIFlatButton(text="Статистика", width=130, height=50)
        self.country_button.on_click = lambda e: self.country_statistic_panel()

        self.country_button_container = UIAnchorLayout()
        self.country_button_container.add(
            self.country_button,
            anchor_x="left",
            anchor_y="top",
            align_x=10,
            align_y=-10
        )
        self.manager.add(self.country_button_container)

        self.economics_button = UIFlatButton(text="Экономика", width=130, height=50)
        self.economics_button.on_click = lambda e: self.economic_panel()

        self.economics_button_container = UIAnchorLayout()
        self.economics_button_container.add(
            self.economics_button,
            anchor_x="left",
            anchor_y="top",
            align_x=150,
            align_y=-10
        )
        self.manager.add(self.economics_button_container)

        self.tech_button = UIFlatButton(text="Технологии", width=130, height=50)
        self.tech_button.on_click = lambda e: self.new_turn()

        self.tech_button_container = UIAnchorLayout()
        self.tech_button_container.add(
            self.tech_button,
            anchor_x="left",
            anchor_y="top",
            align_x=290,
            align_y=-10
        )
        self.manager.add(self.tech_button_container)

        self.new_turn_button = UIFlatButton(text="Новый ход", width=150, height=75)
        self.new_turn_button.on_click = lambda e: self.new_turn()

        self.new_turn_button_container = UIAnchorLayout()
        self.new_turn_button_container.add(
            self.new_turn_button,
            anchor_x="right",
            anchor_y="bottom",
            align_x=-25,
            align_y=25
        )
        self.manager.add(self.new_turn_button_container)

        self.exit_button = UIFlatButton(text="Выход", width=150, height=50)
        self.exit_button.on_click = lambda e: self.exit()

        self.exit_button_container = UIAnchorLayout()
        self.exit_button_container.add(
            self.exit_button,
            anchor_x="right",
            anchor_y="top",
            align_x=-10,
            align_y=-10
        )
        self.manager.add(self.exit_button_container)

        if self._pending_save_data is not None:
            from save_manager import apply_save_to_game
            apply_save_to_game(self, self._pending_save_data)
            self._pending_save_data = None

        self.turn_label = UILabel(
            text=f"Ход: {self.turn}",
            font_size=18,
            text_color=(220, 220, 220),
            bold=True
        )
        turn_label_container = UIAnchorLayout()
        turn_label_container.add(
            self.turn_label,
            anchor_x="right",
            anchor_y="top",
            align_x=-20,
            align_y=-75
        )
        self.manager.add(turn_label_container)

        self.turn_active = True
        self.turn_timer = self.turn_time_limit

        self._show_turn_overlay()

        # Запустить опрос сервера в мультиплеере
        if self.is_multiplayer and self.network:
            self.network.poll_updates(self._on_server_update, interval=2.0)

    def _on_server_update(self, state):
        """Обработчик обновлений от сервера"""
        if not self.is_multiplayer:
            return

        current_player = state.get('current_player')
        if current_player == self.player_id:
            self.turn_blocked = False
            self.turn_active = True
        else:
            self.turn_blocked = True
            self.turn_active = False

        self._sync_with_server()

    def _sync_with_server(self):
        """Получить актуальное состояние игры с сервера"""
        if not self.is_multiplayer or not self.network:
            return

        state = self.network.get_game_state()
        if not state:
            return

        economy = state.get('economies', {}).get(self.player_id, {})
        if economy:
            self.player_country.gold = economy.get('gold', 100)

        armies = state.get('armies', {})
        self.army_positions = {}
        for pos, owner_id in armies.items():
            if owner_id == self.player_id:
                self.army_positions[pos] = self.country

    def _show_turn_overlay(self):
        self.turn_blocked = True

        overlay = UILabel(
            text="⏱ ВАШ ХОД",
            font_size=72,
            text_color=(255, 255, 255),
            bold=True
        )

        panel = UIBoxLayout(vertical=True)
        panel.with_background(color=(0, 0, 0, 180))
        panel.add(overlay)

        anchor = UIAnchorLayout()
        anchor.add(panel, anchor_x="center", anchor_y="center")
        self.manager.add(anchor)

        self.turn_overlay_anchor = anchor

        def remove_overlay(dt):
            if hasattr(self, 'turn_overlay_anchor') and self.manager:
                self.manager.remove(self.turn_overlay_anchor)
            self.turn_blocked = False

        arcade.schedule(remove_overlay, 2.0)

    def show_province_panel(self, has_army: bool):
        if self.turn_blocked:
            return

        self.province_panel_opened = True

        self.panel = UIBoxLayout(vertical=True, space_between=12)
        self.panel.with_padding(top=15, bottom=15, left=15, right=15)
        self.panel.with_background(color=(32, 35, 40, 220))

        title = UILabel(text=self.prov_name.upper(), width=280, align="left")
        divider1 = UILabel(text="─" * 30)
        resource_label = UILabel(text=f"Ресурс: {self.prov_resource}", width=280, align="left")

        army_status = "присутствует" if has_army else "отсутствует"
        army_label = UILabel(text=f"Армия: {army_status}", width=280, align="left")
        divider2 = UILabel(text="─" * 30)

        level = 1
        for prov in self.all_provinces:
            if prov.name == self.prov_name:
                level = prov.level
                break

        row = UIBoxLayout(vertical=False, space_between=10)
        level_label = UILabel(text=f"Уровень провинции: {level}", width=280, align="left")
        level_button = UIFlatButton(text="+", width=35, height=35)
        level_button.on_click = lambda e: self.level_up()

        row.add(level_label)
        row.add(level_button)
        divider3 = UILabel(text="─" * 30)

        if has_army:
            button_text = "Переместить армию"
            on_click_action = self.move_army
        else:
            button_text = "Тренировать войска"
            on_click_action = self.buy_army

        action_button = UIFlatButton(text=button_text, width=260, height=40)
        action_button.on_click = lambda e: on_click_action()

        close_button = UIFlatButton(text="Закрыть", width=260, height=36)
        close_button.on_click = lambda e: self.close_province_message()

        for widget in [
            title, divider1, resource_label, army_label,
            divider2, row, divider3, action_button, close_button
        ]:
            self.panel.add(widget)

        anchor = UIAnchorLayout()
        anchor.add(
            self.panel,
            anchor_x="left",
            anchor_y="bottom",
            align_x=15,
            align_y=15
        )

        self.province_panel = anchor
        self.manager.add(anchor)

    def country_statistic_panel(self):
        if self.turn_blocked:
            return

        self.country_panel_opened = True
        self.manager.remove(self.country_button_container)
        self.manager.remove(self.economics_button_container)
        self.manager.remove(self.tech_button_container)

        with open(f"countries{self.year}.json", mode="r", encoding="UTF-8") as file:
            data = json.load(file)
            provinces = data[self.country]["provinces"]
            resources = dict(Counter(data[self.country]["resources"]))

        if "-" in resources:
            del resources["-"]

        # Адаптивные размеры
        panel_w = 1200
        panel_h = 650

        content_panel = UIBoxLayout(vertical=True, space_between=8)
        content_panel.with_padding(top=15, bottom=15, left=20, right=20)
        content_panel.with_background(color=(28, 30, 34, 240))
        content_panel.size_hint = (None, None)
        content_panel.width = panel_w
        content_panel.height = panel_h

        # Заголовок
        content_panel.add(UILabel(text=self.country.upper(), font_size=24, align="center", width=panel_w - 40))
        content_panel.add(UILabel("─" * 80, align="center", width=panel_w - 40))

        # Ресурсы
        content_panel.add(UILabel(text="📦 РЕСУРСЫ:", font_size=18, align="left", width=panel_w - 40))

        # Ресурсы в одну строку
        res_line = " • " + ", ".join([f"{name}: {count}" for name, count in resources.items()])

        # Добавляем одним виджетом
        content_panel.add(UILabel(text=res_line, font_size=15, align="left", width=panel_w - 40))

        content_panel.add(UILabel("─" * 80, align="center", width=panel_w - 40))

        # Провинции
        content_panel.add(
            UILabel(text=f"🗺 ПРОВИНЦИИ ({len(provinces)}):", font_size=18, align="left", width=panel_w - 40))

        # СТРОКИ ПО 13 НАЗВАНИЙ
        chunk_size = 13
        for i in range(0, len(provinces), chunk_size):
            chunk = provinces[i:i + chunk_size]
            line_text = " • " + ", ".join(chunk)

            content_panel.add(UILabel(text=line_text, font_size=12, align="left", width=panel_w - 40))

        content_panel.add(UILabel("─" * 80, align="center", width=panel_w - 40))

        # Кнопка закрытия
        close_button = UIFlatButton(text="ЗАКРЫТЬ", width=200, height=40, font_size=16)
        close_button.on_click = lambda e: self.close_top_message(self.country_panel, "country_panel_opened")
        content_panel.add(close_button)

        # Центрирование панели на экране
        anchor = UIAnchorLayout()
        anchor.add(content_panel, anchor_x="center", anchor_y="center")
        self.country_panel = anchor
        self.manager.add(anchor)

    def economic_panel(self):
        if self.turn_blocked:
            return

        self.economics_panel_opened = True
        self.manager.remove(self.country_button_container)
        self.manager.remove(self.economics_button_container)
        self.manager.remove(self.tech_button_container)

        content_panel = UIBoxLayout(vertical=True, space_between=10)
        content_panel.with_padding(top=14, bottom=14, left=16, right=16)
        content_panel.with_background(color=(28, 30, 34, 230))

        scroll_area = UIScrollArea(
            size=(350, 750),
            size_hint=(None, None)
        )

        gold_label = UILabel(text=f"💰 Золото: {self.player_country.get_gold()}",
                             width=280, align="left", font_size=20)
        content_panel.add(gold_label)

        close_button = UIFlatButton(text="Закрыть", width=280, height=36)
        close_button.on_click = lambda e: self.close_top_message(
            self.economics_panel, "economics_panel_opened"
        )
        content_panel.add(close_button)

        scroll_area.add(content_panel)

        anchor = UIAnchorLayout()
        anchor.add(
            scroll_area,
            anchor_x="left",
            anchor_y="top",
            align_x=15,
            align_y=-15
        )

        self.economics_panel = anchor
        self.manager.add(anchor)

    def show_victory_window(self):
        self.manager.clear()

        with open(f"countries{self.year}.json", encoding="utf-8") as f:
            data = json.load(f)[self.country]

        panel = UIBoxLayout(vertical=True, space_between=12)
        panel.with_padding(top=20, bottom=20, left=25, right=25)
        panel.with_background(color=(25, 28, 32, 240))

        title = UILabel(
            text="ПОБЕДА",
            font_size=28,
            align="center",
            text_color=(220, 220, 220)
        )
        panel.add(title)

        country_label = UILabel(text=f"Страна: {self.country}", align="left")
        turn_label = UILabel(text=f"Ходов сыграно: {self.turn}", align="left")
        divider = UILabel("─" * 36)
        res_label = UILabel("Ресурсы:  ", align="left")

        resources = [
            f"Пшеница: {data['wheat']}",
            f"Металл: {data['metal']}",
            f"Дерево: {data['wood']}",
            f"Уголь: {data['coal']}",
            f"Нефть: {data['oil']}"
        ]

        panel.add(res_label)
        for r in resources:
            panel.add(UILabel(text=r, align="left"))

        panel.add(divider)

        exit_button = UIFlatButton(text="Выйти в меню", width=240, height=45)
        exit_button.on_click = lambda e: self.exit()

        panel.add(country_label)
        panel.add(turn_label)
        panel.add(divider)
        panel.add(exit_button)

        anchor = UIAnchorLayout()
        anchor.add(panel, anchor_x="center", anchor_y="center")
        self.manager.add(anchor)

    def show_loser_window(self):
        self.manager.clear()

        with open(f"countries{self.year}.json", encoding="utf-8") as f:
            data = json.load(f)[self.country]

        panel = UIBoxLayout(vertical=True, space_between=12)
        panel.with_padding(top=20, bottom=20, left=25, right=25)
        panel.with_background(color=(25, 28, 32, 240))

        title = UILabel(
            text="ПОРАЖЕНИЕ",
            font_size=28,
            align="center",
            text_color=(220, 220, 220)
        )
        panel.add(title)

        country_label = UILabel(text=f"Страна: {self.country}", align="left")
        turn_label = UILabel(
            text=f"Вы потратили слишком много времени: {self.turn}",
            align="left"
        )
        divider = UILabel("─" * 36)

        panel.add(divider)

        exit_button = UIFlatButton(text="Выйти в меню", width=240, height=45)
        exit_button.on_click = lambda e: self.exit()

        panel.add(country_label)
        panel.add(turn_label)
        panel.add(divider)
        panel.add(exit_button)

        anchor = UIAnchorLayout()
        anchor.add(panel, anchor_x="center", anchor_y="center")
        self.manager.add(anchor)

    def exit(self):
        from save_manager import save_game
        save_game(self)
        self.window.show_view(menu.Menu())

    def level_up(self):
        if self.turn_blocked:
            return

        if self.is_multiplayer and self.network:
            result = self.network.send_action(
                'level_up_province',
                province=self.prov_name
            )
            if result.get('success'):
                for prov in self.all_provinces:
                    if prov.name == self.prov_name:
                        if prov.level < 5:
                            prov.level += 1
                            break
                self._update_province_panel()
                self._show_message(f"Провинция улучшена! (-{Economy.LEVEL_UP_GOLD_COST} золота)", (0, 255, 255))
            else:
                self._show_message(result.get('error', "Ошибка"), (255, 0, 0))
            return

        if (self.player_country.can_level_up_province() and
                self.player_country.level_up_province()):
            for prov in self.all_provinces:
                if prov.name == self.prov_name:
                    if prov.level < 5:
                        prov.level += 1
                        break
            self._update_province_panel()
            self._show_message(f"Провинция улучшена! (-{Economy.LEVEL_UP_GOLD_COST} золота)", (0, 255, 255))
        else:
            self._show_message("Недостаточно золота!", (255, 0, 0))

    def go_to_province(self, name):
        self.close_province_message()
        self.prov_name = name
        with open(f"provinces{self.year}.json", mode="r", encoding="utf-8") as file:
            data = json.load(file)
            self.prov_center = (data[name]["center_x"], data[name]["center_y"])
            self.prov_resource = data[name]["resource"]
            self.world_camera.position = self.prov_center
            has_army = self.prov_center in self.army_positions.keys()
            self.show_province_panel(has_army)

    def new_turn(self, auto_end: bool = False):
        if self.turn_blocked:
            return

        if self.is_multiplayer and self.network:
            result = self.network.end_turn()
            if result.get('success'):
                self._sync_with_server()
                self.turn += 1
                if hasattr(self, 'turn_label'):
                    self.turn_label.text = f"Ход: {self.turn}"
                self._show_turn_overlay()
            return

        self.last_prov_centre = ""
        self.last_prov_name = ""

        stats_manager.increment_turns(1)

        player_provinces = []
        with open(f"provinces{self.year}.json", mode="r", encoding="utf-8") as f:
            provinces_data = json.load(f)

        for prov_name in self.player_country.provinces:
            if prov_name in provinces_data:
                player_provinces.append(provinces_data[prov_name])

        self.player_country.end_turn(player_provinces)
        self._update_economic_panel()

        for pos in self.army_positions:
            self.army_positions[pos] = 0

        self.turn += 1

        if not self.is_multiplayer and hasattr(self, 'bot_countries'):
            self._run_bot_turns()

        if hasattr(self, 'turn_label') and self.turn_label:
            self.turn_label.text = f"Ход: {self.turn}"

        self.close_help()

        if not auto_end:
            self.turn_active = True
            self.turn_timer = self.turn_time_limit

        self._show_turn_overlay()

    def buy_army(self):
        if self.turn_blocked:
            return

        if self.is_multiplayer and self.network:
            result = self.network.send_action(
                'buy_army',
                position=str(self.prov_center)
            )
            if result.get('success'):
                self.army_positions[self.prov_center] = self.country
                self._update_economic_panel()
                self._show_message(f"Армия нанята! (-{Economy.ARMY_COST} золота)", (0, 255, 0))
            else:
                self._show_message(result.get('error', "Ошибка"), (255, 0, 0))
            return

        if self.prov_center not in self.army_positions:
            if self.player_country.can_buy_army():
                if self.player_country.buy_army():
                    stats_manager.increment_reinforcements(1)
                    self.army_positions[self.prov_center] = 0
                    self._update_economic_panel()
                    self._show_message(f"Армия нанята! (-{Economy.ARMY_COST} золота)", (0, 255, 0))
                else:
                    self._show_message("Недостаточно золота!", (255, 0, 0))
            else:
                self._show_message(f"Нужно {Economy.ARMY_COST} золота", (255, 200, 0))

    def _run_bot_turns(self):
        if self.is_multiplayer:
            return

        from ai_controller import AIController

        with open(f"provinces{self.year}.json", "r", encoding="utf-8") as f:
            provinces_data = json.load(f)

        for bot_name in self.bot_countries:
            try:
                if bot_name not in self.bot_gold:
                    self.bot_gold[bot_name] = 100
                if bot_name not in self.bot_provinces:
                    self.bot_provinces[bot_name] = []

                bot_data = {
                    'gold': self.bot_gold[bot_name],
                    'provinces': self.bot_provinces[bot_name]
                }

                bot_controller = AIController(
                    country_name=bot_name,
                    country_data=bot_data,
                    provinces_data=provinces_data,
                    player_country_name=self.country,
                    all_armies=self.army_positions.copy()
                )

                result = bot_controller.make_move(self)

                for pos, owner in bot_controller.all_armies.items():
                    if owner == bot_name:
                        self.army_positions[pos] = owner

                self.bot_gold[bot_name] = bot_controller.gold

                conquered = result.get('conquered')
                if conquered:
                    if conquered not in self.bot_provinces[bot_name]:
                        self.bot_provinces[bot_name].append(conquered)
                    self._show_message(
                        f"⚠️ {bot_name} захватил {conquered}!",
                        (255, 100, 100)
                    )
            except Exception as e:
                print(f"⚠️ Ошибка в ходе бота {bot_name}: {e}")
                continue

    def _start_bot_turn(self, bot_name: str):
        self.bot_turn_active = True
        self.bot_turn_timer = 60
        self.current_bot_name = bot_name
        self._show_bot_overlay(bot_name)

    def _show_bot_overlay(self, bot_name: str):
        pass

    def move_army(self):
        if self.turn_blocked:
            return

        self.moving = True
        choice = UILabel(text="Выберите провинцию", text_color=(40, 40, 40), width=300)
        panel = UIBoxLayout(vertical=True, space_between=10)
        panel.with_padding(top=14, bottom=14, left=16, right=16)
        panel.with_background(color=(250, 250, 250, 230))
        panel.add(choice)
        self.move_anchor = UIAnchorLayout()
        self.move_anchor.add(
            panel,
            anchor_x="left",
            anchor_y="top",
            align_x=15,
            align_y=-450
        )
        self.manager.add(self.move_anchor)

    def moving_to(self):
        if self.turn_blocked:
            return

        if self.prov_center not in self.army_positions:
            if self.player_country.can_buy_army():
                if (self.last_prov_centre and
                        self.last_prov_centre in self.army_positions and
                        self.army_positions[self.last_prov_centre] == 0):
                    from neighbors import province_neighbors
                    if self.prov_name in province_neighbors.get(self.last_prov_name, []):

                        if self.player_country.economy.spend_gold(Economy.ARMY_COST):
                            self._update_economic_panel()

                            self.army_positions[self.prov_center] = self.country
                            while self.last_prov_centre in self.army_positions:
                                del self.army_positions[self.last_prov_centre]

                            conquered = False
                            for prov in self.all_provinces:
                                if prov.name == self.prov_name:
                                    if (prov.color.r != self.player_country.color[0] or
                                            prov.color.g != self.player_country.color[1] or
                                            prov.color.b != self.player_country.color[2]):
                                        prov.color = tuple(self.player_country.color)
                                        self.create_conquest_particles(
                                            prov.center_x, prov.center_y, self.player_country.color
                                        )
                                        stats_manager.increment_conquered(1)
                                        conquered = True
                                    break

                            if conquered:
                                self._show_message("Провинция захвачена!", (0, 255, 0))
                            else:
                                self._show_message("Армия перемещена!", (0, 255, 255))
                        else:
                            self._show_message("Недостаточно золота!", (255, 0, 0))
                            self.moving = False
                            return
                    else:
                        self._show_message("Провинции не соседние!", (255, 0, 0))
                        self.moving = False
                        return
                else:
                    self._show_message("Эта армия уже ходила!", (255, 0, 0))
                    self.moving = False
                    return
            else:
                self._show_message(f"Нужно {Economy.ARMY_COST} золота!", (255, 0, 0))
                self.moving = False
                return

        self.moving = False

    def close_help(self):
        if self.moving_anchor is not None and self.manager:
            self.manager.remove(self.moving_anchor)
            self.moving_anchor = None

    def close_province_message(self):
        if self.province_panel is not None and self.manager:
            self.manager.remove(self.province_panel)
            self.province_panel = None
        self.province_panel_opened = False

    def close_top_message(self, panel, panel_flag_name):
        if panel is not None and self.manager:
            self.manager.remove(panel)

        self.manager.add(self.country_button_container)
        self.manager.add(self.economics_button_container)
        self.manager.add(self.tech_button_container)

        if panel_flag_name == "country_panel_opened":
            self.country_panel_opened = False
        elif panel_flag_name == "economics_panel_opened":
            self.economics_panel_opened = False

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        if self.turn_blocked:
            return

        if button == arcade.MOUSE_BUTTON_MIDDLE:
            self.dragging = True
            self.last_mouse_x = x
            self.last_mouse_y = y
            self.manager.on_mouse_press(x, y, button, modifiers)
            return

        world_x, world_y, _ = self.world_camera.unproject((x, y))

        for prov in self.all_provinces:
            if prov.collides_with_point((world_x, world_y)):
                self.last_prov_name = self.prov_name
                self.last_prov_centre = self.prov_center

                self.prov_name = prov.name
                self.prov_resource = prov.resource
                self.prov_center = (prov.center_x, prov.center_y)

                with open(f"countries{self.year}.json", "r", encoding="utf-8") as country_file:
                    country_data = json.load(country_file)
                    prov_color = [prov.color.r, prov.color.g, prov.color.b]

                    if prov_color == country_data[self.country]["color"]:
                        self.close_province_message()
                        has_army = self.prov_center in self.army_positions
                        self.show_province_panel(has_army)

                if self.moving:
                    self.manager.remove(self.move_anchor)
                    self.moving_to()

                return

        self.manager.on_mouse_press(x, y, button, modifiers)

    def on_key_press(self, symbol, modifiers):
        if symbol in self.keys:
            self.keys[symbol] = True

    def on_key_release(self, symbol, modifiers):
        if symbol in self.keys:
            self.keys[symbol] = False

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        zoom_factor = 1.1 if scroll_y > 0 else 1 / 1.1
        new_zoom = self.world_camera.zoom * zoom_factor

        min_zoom_x = self.window.width / self.map_width
        min_zoom_y = self.window.height / self.map_height
        safe_min_zoom = max(min_zoom_x, min_zoom_y, self.min_zoom)

        self.world_camera.zoom = max(safe_min_zoom, min(self.max_zoom, new_zoom))

        cx, cy = self.world_camera.position
        cx, cy = self.clamp_camera(cx, cy)
        self.world_camera.position = (cx, cy)

    def on_mouse_motion(self, x, y, dx, dy):
        if not self.dragging:
            return

        zoom = self.world_camera.zoom
        cam_x, cam_y = self.world_camera.position
        cam_x -= dx / zoom
        cam_y -= dy / zoom
        cam_x, cam_y = self.clamp_camera(cam_x, cam_y)
        self.world_camera.position = (cam_x, cam_y)

    def on_mouse_release(self, x, y, button, modifiers):
        if button == arcade.MOUSE_BUTTON_MIDDLE:
            self.dragging = False

    def clamp_camera(self, x, y):
        zoom = self.world_camera.zoom

        half_w = (self.window.width / zoom) / 2
        half_h = (self.window.height / zoom) / 2

        left = half_w
        right = self.map_width - half_w
        bottom = half_h
        top = self.map_height - half_h

        x = max(left, min(right, x))
        y = max(bottom, min(top, y))

        return x, y

    def on_update(self, delta_time: float):
        # Обновление камеры от клавиш (WASD)
        x, y = self.world_camera.position
        if self.keys[arcade.key.W]:
            y += self.pan_speed
        if self.keys[arcade.key.S]:
            y -= self.pan_speed
        if self.keys[arcade.key.A]:
            x -= self.pan_speed
        if self.keys[arcade.key.D]:
            x += self.pan_speed

        x, y = self.clamp_camera(x, y)
        self.world_camera.position = (x, y)

        # Обновление частиц
        emitters_to_remove = []
        for emitter in self.particle_emitters:
            emitter.update(delta_time)
            if emitter.can_reap():
                emitters_to_remove.append(emitter)

        for emitter in emitters_to_remove:
            self.particle_emitters.remove(emitter)

        # ⏱ ТАЙМЕР ХОДА (работает всегда, независимо от перетаскивания карты)
        if self.turn_active and not self.turn_blocked:
            self.turn_timer -= delta_time
            if self.turn_timer <= 0:
                self.turn_timer = 0
                self.turn_active = False
                self.new_turn(auto_end=True)

        # Таймер хода ботов
        if self.bot_turn_active:
            self.bot_turn_timer -= delta_time
            if self.bot_turn_timer <= 0:
                self.bot_turn_active = False

    def on_draw(self):
        self.clear()

        self.world_camera.use()
        self.background.draw()
        self.all_provinces.draw()

        self.army_sprite_list.clear()
        for pos in self.army_positions:
            if pos not in self.army_sprite_cache:
                self.army_sprite_cache[pos] = arcade.Sprite("images/шлем зеленый 3.png", scale=2)
                self.army_sprite_cache[pos].center_x = pos[0]
                self.army_sprite_cache[pos].center_y = pos[1]
            self.army_sprite_list.append(self.army_sprite_cache[pos])

        self.army_sprite_list.draw()

        for emitter in self.particle_emitters:
            emitter.draw()

        self.gui_camera.use()
        self.manager.draw()

        if self.turn_active and not self.turn_blocked:
            minutes = int(self.turn_timer) // 60
            seconds = int(self.turn_timer) % 60
            timer_text = f"⏱ Время хода: {minutes}:{seconds:02d}"

            color = (255, 100, 100) if self.turn_timer < 30 else (255, 255, 255)

            arcade.draw_text(
                timer_text,
                self.window.width - 180,
                self.window.height - 50,
                color,
                20,
                anchor_x="right",
                font_name=("Courier New",),
                bold=True
            )

    def _invest_resource(self, resource_name: str):
        if self.turn_blocked:
            return

        if self.player_country.invest(resource_name):
            self._update_economic_panel()
            self._show_message(f"Инвестиция в {resource_name}! (-{Economy.INVESTMENT_COST} золота)", (0, 255, 255))
        else:
            self._show_message("Недостаточно золота или макс. уровень", (255, 100, 100))

    def _update_economic_panel(self):
        if self.economics_panel_opened:
            self.manager.remove(self.economics_panel)
            self.economic_panel()

    def _update_province_panel(self):
        if self.province_panel_opened:
            has_army = self.prov_center in self.army_positions
            self.manager.remove(self.province_panel)
            self.show_province_panel(has_army)

    def _show_message(self, text: str, color: tuple):
        if hasattr(self, 'message_anchor') and self.message_anchor and self.manager:
            self.manager.remove(self.message_anchor)

        msg = UILabel(text=text, text_color=color, width=300)
        panel = UIBoxLayout(vertical=True)
        panel.with_background(color=(250, 250, 250, 230))
        panel.add(msg)

        anchor = UIAnchorLayout()
        anchor.add(panel, anchor_x="left", anchor_y="top", align_x=15, align_y=-650)
        self.manager.add(anchor)

        self.message_anchor = anchor

        def remove_msg(dt):
            if hasattr(self, 'message_anchor') and self.message_anchor and self.manager:
                self.manager.remove(self.message_anchor)
                self.message_anchor = None

        arcade.schedule(remove_msg, 2.0)