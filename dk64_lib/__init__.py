import os
import json

BASE_PATH = os.path.dirname(__file__)

ASSET_PATH = os.path.join(BASE_PATH, "assets")

with open(os.path.join(ASSET_PATH, "maps.json")) as map_file:
    MAPS = json.load(map_file)

with open(os.path.join(ASSET_PATH, "release_sprites.json")) as sprites_file:
    RELEASE_SPRITES = json.load(sprites_file)

with open(os.path.join(ASSET_PATH, "kiosk_sprites.json")) as sprites_file:
    KIOSK_SPRITES = json.load(sprites_file)
