import arcade

class Province(arcade.Sprite):
    def __init__(self, filename: str, center_x: int, center_y: int, color: arcade.color.WHITE, name: str, resource: str):
        super().__init__(filename, scale=1)
        self.center_x = center_x
        self.center_y = center_y
        self.color = color
        self.name = name
        self.resource = resource
        self.level = 1