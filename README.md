# DK64 Lib

A library for extracting data from a Donkey Kong 64 ROM

## Installation

`pip install dk64-lib`

## Examples

### Text data

```python
from dk64_lib.rom import Rom
rom = Rom("Donkey Kong 64 (USA).z64")

for text_line in rom.text_tables[0].text_lines:
    print(text_line.text)

# WELCOME TO THE BONUS STAGE!
# HIT AS MANY KREMLINGS AS YOU CAN! PRESS a_button TO FIRE A MELON.
# KEEP THE TURTLES SPINNING BY FEEDING THE SNAKES MELONS. PRESS a_button TO FIRE A MELON.
# LINE UP FOUR BANANAS TO WIN THE JACKPOT! PRESS a_button TO SPIN AND STOP THE REELS.
# RELOAD!
# HURRY!
# ...

```

### Geometry data

Export every map to an obj
```python
from dk64_lib.rom import Rom
rom = Rom("Donkey Kong 64 (USA).z64")

for map_num, geometry_map in enumerate(rom.geometry_tables):
    geometry_map.save_to_obj(f'{map_num}.obj')
```

Export a map to OBJ with an MTL file and PNG texture assets:
```python
from dk64_lib.rom import Rom
rom = Rom("Donkey Kong 64 (USA).z64")

rom.geometry_tables[0].save_to_obj("0.obj", include_textures=True)
```

## To-do
- Expand textured geometry export format coverage and texture-state accuracy
- Extract models and convert to objs
- Extract audio and convert to some sort of audio file
- Extract everything else
