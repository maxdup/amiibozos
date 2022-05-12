# amiibozos

This is a 3D model generator for a collection NFC enabled tokens.
The current collection covers the whole smash series. Other series remain to be adressed.

## Where to get the models

### Printables.com

Get the generated models directly from the printables.com collection.

### Generating models from source
**_NOTE:_** This section assumes you have a Python/git development environment ready to go.

Clone the source files:
```
git clone https://github.com/maxdup/amiibozos.git
```

Go into the project folder:
```
cd amiibozos
```

Install the dependencies:
```
pip install -r requirements.txt
```

run tokenify.py
```
python tokenify.py
```

The generated models can be found in `amiibozos/models/`

## What you need for printing
- 25mm diameter NTAG215 NFC stickers
- A pausable 3D printer
- Your filament of choice (slicer settings optimized to enhance the appearance of silky colors)

## What slicer settings to use

It's highly recommended to use PrusaSlicer even if you don't use a prusa printer. The models are optimized for PrusaSlicer and PruciaSlicer offers unique options that will enhance your print.

### Print Settings

| Printer settings       |        |
| :--------------------- | ------ |
| Nozzle diameter        | 0.4mm  |

| Layers and permimeters |        |
| :--------------------- | ------ |
| Layer height           | 0.24mm |
| First layer height     | 0.24mm |
| Perimeters             | 3      |
| Solid layers (top)     | 1      |
| Solid layers (bottom)  | 1      |

| Infill                              |                    |
| :---------------------------------- | ------------------ |
| Fill density                        | 100%               |
| Fill pattern                        | Archimedean Chords |
| Length of the infill anchor         | 100%               |
| Maximum length of the infill anchor | 100%               |
| Top fill pattern                    | Archimedean Chords |
| Bottom fill pattern                 | Archimedean Chords |

### Pause
Add a pause instruction on layer 7 to give you an opportunity to add your NFC sticker.


# Contributing
I'm personally taking a break from designing further models but I will gladly look at outside contributions. Only your SVG models are needed but you're expected to run the generator and make sure your designs slice nicely with the target slicer settings. 
