import arcade
import random
import pyglet
import menu

class MainWindow(arcade.Window):
    def __init__(self):
        screen_width, screen_height = arcade.get_display_size()
        super().__init__(screen_width, screen_height, "Steel Dawn 2", fullscreen=True)
        self.player = None
        self.music_files = [
            "Andreas_Waldetoft_-_Morning_Of_D_Day_72081712",
            "Andreas_Waldetoft_-_The_Royal_Air_Force_(musmore.org)",
            "Hearts_of_Iron_IV_OST_-_Hearts_of_Men_(Zvyki.com)",
            "Hearts_of_Iron_IV_OST_Krakow_(www.lightaudio.ru)",
            "Hearts_of_Iron_4_Katyusha_(www.lightaudio.ru)",
            "Hearts_of_iron_4_Коминтерн(www.lightaudio.ru)",
            "Heart_of_Iron_4_We_are_soldiers_(www.lightaudio.ru)",
            "Hearts_of_Iron_4_Надвигается_буря(www.lightaudio.ru)",
            "Hearts_of_Iron_IV_OST_-_End_of_the_Tour_(Zvyki.com)",
            "Hearts_of_Iron_IV_(День_Победы_4)_OST_Mother_Russia(www.lightaudio.ru)"
        ]

    def setup(self):
        self.show_view(menu.Menu())
        self.play_random_music()

    def play_random_music(self):
        if self.player:
            self.player.pause()
            self.player.delete()

        music_file = random.choice(self.music_files)
        music_path = f"music/{music_file}.mp3"

        music = pyglet.media.load(music_path, streaming=True)
        self.player = music.play()

        def on_eos():
            self.play_random_music()

        self.player.push_handlers(on_eos=on_eos)

    def on_key_press(self, key, modifiers):
        if key == arcade.key.F:
            self.set_fullscreen(not self.fullscreen)

if __name__ == "__main__":
    window = MainWindow()
    window.setup()
    arcade.run()