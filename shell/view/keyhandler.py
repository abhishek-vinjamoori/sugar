# Copyright (C) 2006-2007, Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import os
import signal
import logging

import dbus
import gobject
import gtk

from hardware import hardwaremanager
from model.shellmodel import ShellModel
from sugar._sugarext import KeyGrabber

_BRIGHTNESS_STEP = 2
_VOLUME_STEP = 10
_BRIGHTNESS_MAX = 15
_VOLUME_MAX = 100

_actions_table = {
    'F1'             : 'zoom_mesh',
    'F2'             : 'zoom_friends',
    'F3'             : 'zoom_home',
    'F4'             : 'zoom_activity',
    'F9'             : 'brightness_down',
    'F10'            : 'brightness_up',
    '<ctrl>F9'       : 'brightness_min',
    '<ctrl>F10'      : 'brightness_max',
    'F11'            : 'volume_down',
    'F12'            : 'volume_up',
    '<ctrl>F11'      : 'volume_min',
    '<ctrl>F12'      : 'volume_max',
    '<alt>1'         : 'screenshot',
    '<alt>equal'     : 'console',
    '<alt>0'         : 'console',
    '<alt>f'         : 'frame',
    '0x93'           : 'frame',
    '<alt>o'         : 'overlay',
    '0xE0'           : 'overlay',
    '0xEB'           : 'rotate',
    '<alt>r'         : 'rotate',
    '<alt>q'         : 'quit_emulator',
    '<alt>tab'       : 'next_window',
    '<alt>n'         : 'next_window',
    '<ctrl><alt>tab' : 'previous_window',
    '<alt>p'         : 'previous_window',
    '<ctrl>escape'   : 'close_window',
    '<ctrl>q'        : 'close_window'
}

class KeyHandler(object):
    def __init__(self, shell):
        self._shell = shell
        self._screen_rotation = 0
        self._key_pressed = None
        self._keycode_pressed = 0
        self._keystate_pressed = 0

        self._key_grabber = KeyGrabber()
        self._key_grabber.connect('key-pressed',
                                  self._key_pressed_cb)
        self._key_grabber.connect('key-released',
                                  self._key_released_cb)

        for key in _actions_table.keys():
            self._key_grabber.grab(key)            

    def _change_volume(self, step=None, value=None):
        hw_manager = hardwaremanager.get_manager()

        if step is not None:
            volume = hw_manager.get_volume() + step
        elif value is not None:
            volume = value

        volume = min(max(0, volume), _VOLUME_MAX)

        hw_manager.set_volume(volume)
        hw_manager.set_mute(volume == 0)

    def _change_brightness(self, step=None, value=None):
        hw_manager = hardwaremanager.get_manager()

        if step is not None:
            level = hw_manager.get_display_brightness() + step
        elif value is not None:
            level = value

        level = min(max(0, level), _BRIGHTNESS_MAX)

        hw_manager.set_display_brightness(level)
        if level == 0:
            hw_manager.set_display_mode(hardwaremanager.B_AND_W_MODE)
        else:
            hw_manager.set_display_mode(hardwaremanager.COLOR_MODE)

    def handle_previous_window(self):
        self._shell.activate_previous_activity()

    def handle_next_window(self):
        self._shell.activate_next_activity()

    def handle_close_window(self):
        self._shell.close_current_activity()

    def handle_zoom_mesh(self):
        self._shell.set_zoom_level(ShellModel.ZOOM_MESH)

    def handle_zoom_friends(self):
        self._shell.set_zoom_level(ShellModel.ZOOM_FRIENDS)

    def handle_zoom_home(self):
        self._shell.set_zoom_level(ShellModel.ZOOM_HOME)

    def handle_zoom_activity(self):
        self._shell.set_zoom_level(ShellModel.ZOOM_ACTIVITY)

    def handle_brightness_max(self):
        self._change_brightness(value=_BRIGHTNESS_MAX)

    def handle_brightness_min(self):
        self._change_brightness(value=0)

    def handle_volume_max(self):
        self._change_volume(value=_VOLUME_MAX)

    def handle_volume_min(self):
        self._change_volume(value=0)

    def handle_brightness_up(self):
        self._change_brightness(step=_BRIGHTNESS_STEP)

    def handle_brightness_down(self):
        self._change_brightness(step=-_BRIGHTNESS_STEP)

    def handle_volume_up(self):
        self._change_volume(step=_VOLUME_STEP)

    def handle_volume_down(self):
        self._change_volume(step=-_VOLUME_STEP)

    def handle_screenshot(self):
        self._shell.take_screenshot()

    def handle_console(self):
        gobject.idle_add(self._toggle_console_visibility_cb)

    def handle_frame(self):
        self._shell.get_frame().notify_key_press()

    def handle_overlay(self):
        self._shell.toggle_chat_visibility()

    def handle_rotate(self):
        states = [ 'normal', 'left', 'inverted', 'right']

        self._screen_rotation += 1
        if self._screen_rotation == len(states):
            self._screen_rotation = 0

        gobject.spawn_async(['xrandr', '-o', states[self._screen_rotation]],
                            flags=gobject.SPAWN_SEARCH_PATH)

    def handle_quit_emulator(self):
        if os.environ.has_key('SUGAR_EMULATOR_PID'):
            pid = int(os.environ['SUGAR_EMULATOR_PID'])
            os.kill(pid, signal.SIGTERM)

    def _key_pressed_cb(self, grabber, keycode, state):
        key = grabber.get_key(keycode, state)
        logging.debug('_key_pressed_cb: %i %i %s' % (keycode, state, key))
        if key:
            self._key_pressed = key
            self._keycode_pressed = keycode
            self._keystate_pressed = state

            """
            status = gtk.gdk.keyboard_grab(gtk.gdk.get_default_root_window(),
                                           owner_events=False, time=0L)
            if status != gtk.gdk.GRAB_SUCCESS:
                logging.error("KeyHandler._key_pressed_cb(): keyboard grab failed: " + status)
            """

            action = _actions_table[key]
            method = getattr(self, 'handle_' + action)
            method()

            return True

        return False

    def _key_released_cb(self, grabber, keycode, state):
        if self._keycode_pressed == keycode:
            self._keycode_pressed = 0

        if self._keystate_pressed == state:
            self._keystate_pressed = 0

        if not self._keycode_pressed and not self._keystate_pressed and \
           self._key_pressed:
            gtk.gdk.keyboard_ungrab(time=0L)

            if self._key_pressed == '<alt>f':
                self._shell.get_frame().notify_key_release()
            elif self._key_pressed == '0x93':
                self._shell.get_frame().notify_key_release()

            return True

        return False

    def _toggle_console_visibility_cb(self):
        bus = dbus.SessionBus()
        proxy = bus.get_object('org.laptop.sugar.Console',
                               '/org/laptop/sugar/Console')
        console = dbus.Interface(proxy, 'org.laptop.sugar.Console')
        console.ToggleVisibility()
