# DK64 Lib

A library for extracting data from a Donkey Kong 64 ROM

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

## To-do
- Extract texture data and convert to appropriately formatted images
- Extract models and convert to objs
- Extract audio and convert to some sort of audio file
- Extract everything else