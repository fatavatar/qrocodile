#
# Copyright (c) 2018 Chris Campbell
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

import argparse
import json
import os
import subprocess
import sys
from time import sleep
import urllib
import urllib2
import string
import pickle

from evdev import InputDevice
from select import select

# Parse the command line arguments
arg_parser = argparse.ArgumentParser(description='Translates QR codes detected by a camera into Sonos commands.')
arg_parser.add_argument('--default-device', default='Living Room', help='the name of your default device/room')
arg_parser.add_argument('--hostname', default='localhost', help='the hostname or IP address of the machine running `node-sonos-http-api`')
arg_parser.add_argument('--skip-load', action='store_true', help='skip loading of the music library (useful if the server has already loaded it)')
arg_parser.add_argument('--debug-file', help='read commands from a file instead of launching scanner')
args = arg_parser.parse_args()
print args


base_url = 'http://' + args.hostname + ':5005'
global swipe_to_cmd

# Load the most recently used device, if available, otherwise fall back on the `default-device` argument
try:
    with open('.last-device', 'r') as device_file:
        current_devices
         = pickle.load(device_file)
        create_group(current_devices)
        print('Defaulting to last used room: ' + current_devices)

except:
    current_devices = args.default_device
    print('Initial room: ' + current_devices)

if os.path.exists('swipeToCmd.json'):
    with open('swipeToCmd.json') as json_file:
        swipe_to_cmd = json.load(json_file)
else:
    print("Error, associate your cards first with associateCards.py")
    sys.exit(1)


# Keep track of the last-seen code
last_qrcode = ''


class Mode:
    PLAY_SONG_IMMEDIATELY = 1
    PLAY_ALBUM_IMMEDIATELY = 2
    BUILD_QUEUE = 3

current_mode = Mode.PLAY_SONG_IMMEDIATELY

dev = InputDevice('/dev/input/event0')

scancodes = {
    # Scancode: ASCIICode
    0: None, 2: u'1', 3: u'2', 4: u'3', 5: u'4', 6: u'5', 7: u'6', 8: u'7', 9: u'8',
    10: u'9', 11: u'0', 12: u'-', 13: u'=', 16: u'Q', 17: u'W', 18: u'E', 19: u'R',
    20: u'T', 21: u'Y', 22: u'U', 23: u'I', 24: u'O', 25: u'P', 26: u'[', 27: u']', 28: u'\n',
    30: u'A', 31: u'S', 32: u'D', 33: u'F', 34: u'G', 35: u'H', 36: u'J', 37: u'K', 38: u'L', 39: u';',
    40: u'"', 41: u'`', 43: u'\\', 44: u'Z', 45: u'X', 46: u'C', 47: u'V', 48: u'B', 49: u'N',
    50: u'M', 51: u',', 52: u'.', 53: u'/', 57: u' '
}


def read_swipe():
    toPrint = ""
    while True:
        r,w,x = select([dev], [], [], .7)
        if len(r) == 0:
            if len(toPrint) > 0:
                print(toPrint)
                return toPrint.strip()
        else:
            for event in dev.read():
                if event.type==1 and event.value==1:
                    if event.code in scancodes:
                        toPrint = toPrint + scancodes[event.code]

def get_cmd_for_code(swipecode):
    if swipecode in swipe_to_cmd:
        return swipe_to_cmd[swipecode]
    else:
        print("Code not found in table.")
        return None


def perform_request(url):
    print(url)
    response = urllib2.urlopen(url)
    result = response.read()
    print(result)


def perform_global_request(path):
    perform_request(base_url + '/' + path)


def perform_room_request(path):
    qdevice = urllib.quote(current_devices[0])
    perform_request(base_url + '/' + qdevice + '/' + path)

def add_to_group(rooms):
    qdevice = urllib.quote(current_devices[0])
    new_devices = []
    if current_devices[0] in rooms:
        new_devices.append(current_devices[0])

    for room in rooms:
        if room not in new_devices:
            new_devices.append(room)
        if room not in current_devices:
            qadding = urllib.quote(room)
            perform_request(base_url + '/' + qadding + '/join/' + qdevice)
    for room in current_devices:
        if room not in rooms:
            qleaving = urllib.quote(room)
            perform_request(base_url + '/' + qleaving + '/leave')
            perform_request(base_url + '/' + qleaving + '/pause0')

def switch_to_rooms(rooms):
    global current_devices
    global combine_rooms

    if combine_rooms:
        if rooms[0] not in current_devices:
            new_group = current_devices.copy()
            new_group.append(room[0])
            add_to_group(new_group)

            
    # perform_global_request('pauseall')
    ordered_list = add_to_group(rooms)
    current_devices = ordered_list
    with open(".last-device", "w") as device_file:
        device_file.write(current_devices)


def speak(phrase):
    print('SPEAKING: \'{0}\''.format(phrase))
    perform_room_request('say/' + urllib.quote(phrase))


# Causes the onboard green LED to blink on and off twice.  (This assumes Raspberry Pi 3 Model B; your
# mileage may vary.)
def blink_led():
    duration = 0.15

    def led_off():
        subprocess.call("echo 0 > /sys/class/leds/led0/brightness", shell=True)

    def led_on():
        subprocess.call("echo 1 > /sys/class/leds/led0/brightness", shell=True)

    # Technically we only need to do this once when the script launches
    subprocess.call("echo none > /sys/class/leds/led0/trigger", shell=True)

    led_on()
    sleep(duration)
    led_off()
    sleep(duration)
    led_on()
    sleep(duration)
    led_off()


def handle_command(qrcode):
    global current_mode
    global combine_rooms

    print('HANDLING COMMAND: ' + qrcode)

    if qrcode == 'cmd:playpause':
        perform_room_request('playpause')
        phrase = None
    elif qrcode == 'cmd:next':
        perform_room_request('next')
        phrase = None
    elif qrcode == 'combinerooms':
        combine_rooms = True
    elif qrcode == 'cmd:playroom':
        switch_to_rooms(['Playroom'])
    elif qrcode == 'cmd:livingroom':
        switch_to_rooms(['Living Room'])
        phrase = 'I\'m switching to the living room'
    elif qrcode == 'cmd:bathroom':
        switch_to_rooms(['Bathroom'])
        phrase = 'I\'m switching to the bathroom'
    elif qrcode == 'cmd:songonly':
        current_mode = Mode.PLAY_SONG_IMMEDIATELY
        phrase = 'Scan a card and I\'ll play that song right away'
    elif qrcode == 'cmd:wholealbum':
        current_mode = Mode.PLAY_ALBUM_IMMEDIATELY
        phrase = 'Scan a card and I\'ll play the whole album'
    elif qecode == 'cmd:everywhere':
        switch_to_rooms(["Playroom", "Living Room", "Bathroom"])
        phrase = 'I\'m switching to the whole house'
    elif qrcode == 'cmd:buildqueue':
        current_mode = Mode.BUILD_QUEUE
        #perform_room_request('pause')
        perform_room_request('clearqueue')
        phrase = 'Let\'s build a list of songs'
    elif qrcode == 'cmd:whatsong':
        perform_room_request('saysong')
        phrase = None
    elif qrcode == 'cmd:whatnext':
        perform_room_request('saynext')
        phrase = None
    else:
        phrase = 'Hmm, I don\'t recognize that command'

    if phrase:
        speak(phrase)


def handle_library_item(uri):
    if not uri.startswith('lib:'):
        return

    print('PLAYING FROM LIBRARY: ' + uri)

    if current_mode == Mode.BUILD_QUEUE:
        action = 'queuesongfromhash'
    elif current_mode == Mode.PLAY_ALBUM_IMMEDIATELY:
        action = 'playalbumfromhash'
    else:
        action = 'playsongfromhash'

    perform_room_request('musicsearch/library/{0}/{1}'.format(action, uri))


def handle_spotify_item(uri):
    print('PLAYING FROM SPOTIFY: ' + uri)

    if current_mode == Mode.BUILD_QUEUE:
        action = 'queue'
    elif current_mode == Mode.PLAY_ALBUM_IMMEDIATELY:
        action = 'clearqueueandplayalbum'
    else:
        action = 'clearqueueandplaysong'

    perform_room_request('spotify/{0}/{1}'.format(action, uri))


def handle_swipe(swipe):


    print('HANDLING SWIPE: ' + swipe)

    cmd = get_cmd_for_code(swipe)
    if cmd is not None:
        if cmd.startswith('cmd:'):
            handle_command(cmd)
        elif cmd.startswith('spotify:'):
            handle_spotify_item(cmd)
        else:
            handle_library_item(cmd)

        # Blink the onboard LED to give some visual indication that a code was handled
        # (especially useful for cases where there's no other auditory feedback, like
        # when adding songs to the queue)
        if not args.debug_file:
            blink_led()
    else:
        print("Command for code not found")


# Monitor the output of the QR code scanner.
def monitor_reader():
    while True:
        code = read_swipe()
        if code is not None:
            handle_swipe(code)


# Read from the `debug.txt` file and handle one code at a time.
def read_debug_script():
    # Read codes from `debug.txt`
    with open(args.debug_file) as f:
        debug_codes = f.readlines()

    # Handle each code followed by a short delay
    for code in debug_codes:
        # Remove any trailing comments and newline (and ignore any empty or comment-only lines)
        code = code.split("#")[0]
        code = code.strip()
        if code:
            handle_swipe(code)
            sleep(4)


perform_global_request('pauseall')
speak('Hello, I\'m qrocodile.')

if not args.skip_load:
    # Preload library on startup (it takes a few seconds to prepare the cache)
    print('Indexing the library...')
    speak('Please give me a moment to gather my thoughts.')
    perform_room_request('musicsearch/library/loadifneeded')
    print('Indexing complete!')
    speak('I\'m ready now!')

speak('Show me a card!')

if args.debug_file:
    # Run through a list of codes from a local file
    read_debug_script()
else:
    monitor_reader()
