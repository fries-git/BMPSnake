from PIL import Image
import time
import keyboard
import random

fileformat = "png"
size = 20

def reset(size):
    global img, pixels
    img = Image.new("RGB", (size, size))
    pixels = img.load()

    for y in range(size):
        for x in range(size):
            r,g,b = 0, 0, 0
            pixels[x, y] = (r,g,b)

    img.save(f"game.{fileformat}")

def setpixel(x, y, color):
    global state
    try:
        pixels[x,y] = color
        img.save(f"game.{fileformat}")
    except Exception as e:
        state = "wallhit"

snakebody = []

keyboard.on_press_key("w", lambda e: set_direction(3))
keyboard.on_press_key("s", lambda e: set_direction(2))
keyboard.on_press_key("a", lambda e: set_direction(1))
keyboard.on_press_key("d", lambda e: set_direction(0))

def set_direction(key):
    global snakedir
    if key == 0 and snakedir != 1:
        snakedir = key
    if key == 1 and snakedir != 0:
        snakedir = key
    if key == 2 and snakedir != 3:
        snakedir = key
    if key == 3 and snakedir != 2:
        snakedir = key

headx, heady, = 0, int((round(size/2)))

reset(size)
img = Image.open(f"game.{fileformat}").convert("RGB")

snakedir = 0
length = 3

def moveapple():
    return (random.randint(0,size - 1),random.randint(0,size - 1))

applex, appley = moveapple()

state = "playing"
reset(size)

while state == "playing":
    snakebody.append((headx, heady))
    if snakedir == 0:
        headx += 1
    elif snakedir == 1:
        headx -= 1
    elif snakedir == 2:
        heady += 1
    elif snakedir == 3:
        heady -= 1

    if (headx,heady) in snakebody:
        state = "selfhit"

    if headx == applex and heady == appley:
        length += 1
        applex, appley = moveapple()

    setpixel(headx,heady,(0,255,0))
    brightness = 245
    if len(snakebody) > length:
        setpixel(snakebody[0][0], snakebody[0][1], (0, 0, 0))
        snakebody.pop(0)
    for i in snakebody:
        setpixel(i[0],i[1],(0,brightness,0))
        brightness -= 10
        if brightness < 105 :
            brightness = 105

    setpixel(applex,appley,(200,0,0))
    if fileformat == "jpg":
        setpixel(applex + 1,appley,(200,0,0))
        setpixel(applex - 1,appley,(200,0,0))
        setpixel(applex,appley + 1,(200,0,0))
        setpixel(applex,appley - 1,(200,0,0))
    time.sleep(0.2)
