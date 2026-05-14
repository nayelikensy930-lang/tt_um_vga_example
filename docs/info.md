## How it works

This project generates a VGA 640x480 signal displaying a 128x128 pixel bitmap logo that bounces around the screen. Each time the logo hits a wall, the color changes using a palette. The design includes a VGA sync generator, a bitmap ROM storing the logo pixels, and a color palette module.

- `ui_in[0]` (cfg_tile): enables tile mode, where the logo repeats across the entire screen
- `ui_in[1]` (cfg_color): enables color cycling on each bounce

## How to test

Connect a VGA monitor using the TinyVGA PMOD on the output pins. Set the clock to 25.175 MHz. After reset, the logo will start bouncing. Toggle `ui_in[0]` to enable tile mode and `ui_in[1]` to enable color cycling.

## External hardware

TinyVGA PMOD connected to the output pins.
