#!/usr/bin/python3

# Copyright (C) 2022 Free Software Foundation, Inc.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.


import os, subprocess, gi

gi.require_version("Adw", "1")

gi.require_version("Gtk", "4.0")

gi.require_version("Gdk", "4.0")

gi.require_version("Gio", "2.0")

gi.require_version("GLib", "2.0")

gi.require_version("Pango", "1.0")

from gi.repository import Adw

from gi.repository import Gtk

from gi.repository import Gdk

from gi.repository import Gio

from gi.repository import GLib

from gi.repository import Pango

from modules import basic


class Timeout():

    DEFAULT = 2


class Spacing():

    DEFAULT = 6


class Margin():

    DEFAULT = 6

    LARGE = 11

    LARGER = 24

    LARGEST = 36


class Keyval():

    TAB = 65289

    ESCAPE = 65307

    LEFT = 65361

    UP = 65362

    RIGHT = 65363

    DOWN = 65364

    PAGEUP = 65365

    PAGEDOWN = 65366

    F2 = 65471


class ImageSize():

    LARGE = 96


class IconNotFoundError(Exception):

    pass


class IconFinder():

    def __init__(self, app):

        self._application = app

        self._application_window = app.get_application_window()

        self._icon_theme = Gtk.IconTheme.get_for_display(self._application_window.get_display())

        self._alternatives = {}

    def add_alternatives(self, name, *alternatives):

        if not name in self._alternatives:

            self._alternatives[name] = list(alternatives)

        else:

            for alternative in alternatives:

                self._alternatives[name].append(alternative)

    def add_search_path(self, path):

        if not path in self._icon_theme.get_search_path():

            self._icon_theme.add_search_path(path)

    def get_image(self, *icons):

        image = Gtk.Image()

        self.set_image(image, *icons)

        return image

    def set_image(self, image, *icons):

        for icon in icons:

            name = self.get_name(icon)

            if self._icon_theme.has_icon(name):

                image.set_from_icon_name(name)

                return True

            else:

                if os.getenv("APP_RUNNING_AS_FLATPAK"):

                    icon = self._application.get_flatpak_sandbox_system_path(icon)

                if os.path.exists(icon):

                    try:

                        texture = Gdk.Texture.new_from_filename(icon)

                    except GLib.GError:

                        pass

                    else:

                        image.set_from_paintable(texture)

                        return True

        else:

            raise IconNotFoundError(*icons)

    def get_name(self, name):

        if not self._icon_theme.has_icon(name):

            try:

                for alternative in self._alternatives[name]:

                    if self._icon_theme.has_icon(alternative):

                        return alternative

            except KeyError:

                return name

        else:

            return name


class SuffixLabel(Gtk.Label):

    def __init__(self):

        Gtk.Label.__init__(self)

        self.set_halign(Gtk.Align.END)

        self.set_margin_start(Margin.LARGEST)

        self.set_ellipsize(Pango.EllipsizeMode.END)


class SuffixEntry(Gtk.Entry):

    def __init__(self):

        Gtk.Entry.__init__(self)

        self.set_hexpand(True)

        self.set_margin_start(Margin.LARGEST)

        self.set_halign(Gtk.Align.FILL)

        self.set_valign(Gtk.Align.CENTER)

        self.set_alignment(1)


class EntryRow(Adw.ActionRow):

    def __init__(self, app):

        Adw.ActionRow.__init__(self)

        self._icon_finder = app.get_icon_finder()

        self._events = basic.EventManager()

        self._events.add("text-changed", object, str)

        self._events.add("edit-mode-enabled-changed", bool)

        self._show_edit_button = True

        self._edit_mode_enabled = False

        self._text = ""

        self._label = SuffixLabel()

        self._entry = SuffixEntry()

        self._entry.connect("activate", self._on_entry_activate)

        self._edit_button = Gtk.ToggleButton()

        self._edit_button.set_can_focus(False)

        self._edit_button.set_valign(Gtk.Align.CENTER)

        self._edit_button.set_icon_name(self._icon_finder.get_name("document-edit-symbolic"))

        self._edit_button.add_css_class("flat")

        self._edit_button.connect("toggled", self._on_edit_button_toggled)

        self._stack = Gtk.Stack()

        self._stack.set_hexpand(True)

        self._stack.add_child(self._label)

        self._stack.add_child(self._entry)

        self._event_controller_key = Gtk.EventControllerKey()

        self._event_controller_key.connect("key-pressed", self._on_event_controller_key_pressed)

        self.set_activatable(True)

        self.set_title_lines(1)

        self.add_controller(self._event_controller_key)

        self.connect("activated", self._on_activated)

        self.add_suffix(self._stack)

        self.add_suffix(self._edit_button)

    def _on_activated(self, action_row):

        self.set_edit_mode_enabled(self.get_edit_mode_enabled() == False)

    def _on_event_controller_key_pressed(self, controller, keyval, keycode, state):

        if keyval == Keyval.ESCAPE:

            self._entry.set_text(self.get_text())

            self.set_edit_mode_enabled(False)

        elif keyval == Keyval.F2:

            self.set_edit_mode_enabled(self._edit_mode_enabled == False)

    def _on_edit_button_toggled(self, toggle_button):

        self.set_edit_mode_enabled(self._edit_button.get_active())

    def _on_entry_activate(self, entry):

        self.set_edit_mode_enabled(False)

    def get_show_edit_button(self):

        return self._show_edit_button

    def set_show_edit_button(self, value):

        if not self._edit_mode_enabled:

            self._edit_button.set_visible(value)

        self._show_edit_button = value

    def get_edit_mode_enabled(self):

        return self._edit_mode_enabled

    def set_edit_mode_enabled(self, value):

        if value and not self._edit_mode_enabled:

            self._stack.set_visible_child(self._entry)

            self._entry.grab_focus()

            self._entry.set_text(self.get_text())

            self._entry.set_position(-1)

            self._edit_button.set_active(True)

            self._edit_button.set_visible(True)

            self._events.trigger("edit-mode-enabled-changed", bool(value))

        elif not value and self._edit_mode_enabled:

            self.grab_focus()

            self._stack.set_visible_child(self._label)

            if not self._text == self._entry.get_text():

                self.set_text(self._entry.get_text())

            self._edit_button.set_active(False)

            self._edit_button.set_visible(self._show_edit_button)

            self._events.trigger("edit-mode-enabled-changed", bool(value))

        self._edit_mode_enabled = value

    def get_text(self):

        return self._text

    def set_text(self, text):

        self._text = text

        self._events.trigger("text-changed", self, text)

        self._label.set_text(text)

    def hook(self, event, callback, *args):

        self._events.hook(event, callback, *args)

    def release(self, id):

        self._events.release(id)


class PathChooserRow(EntryRow):

    def __init__(self, app):

        EntryRow.__init__(self, app)

        self._icon_finder = app.get_icon_finder()

        self._application_window = app.get_application_window()

        self._events.hook("edit-mode-enabled-changed", self._on_edit_mode_enabled_changed)

        self._error_image = self._icon_finder.get_image("action-unavailable-symbolic")

        self._default_image = self._icon_finder.get_image("document-open-symbolic")

        self._chooser_button = Gtk.Button()

        self._chooser_button.set_valign(Gtk.Align.CENTER)

        self._chooser_button.set_child(self._default_image)

        self._chooser_button.connect("clicked", self._on_chooser_button_clicked)

        self._chooser_button.add_css_class("flat")

        self._file_chooser_dialog = Gtk.FileChooserNative()

        self._file_chooser_dialog.connect("response", self._on_file_chooser_dialog_response)

        self._file_chooser_dialog.set_transient_for(self._application_window)

        self._file_chooser_dialog.set_modal(True)

        self.set_show_edit_button(False)

        self.add_suffix(self._chooser_button)

    def _on_edit_mode_enabled_changed(self, event, value):

        self._chooser_button.set_visible(value == False)

    def _on_file_chooser_dialog_response(self, dialog, response):

        self._file_chooser_dialog.hide()

        if response == -3:

            self.set_text(self._file_chooser_dialog.get_file().get_path())

    def _on_chooser_button_clicked(self, button):

        self._file_chooser_dialog.show()

    def get_chooser_button(self):

        return self._chooser_button

    def set_dialog_title(self, text):

        self._file_chooser_dialog.set_title(text)

    def set_text(self, text):

        self._text = text

        self._events.trigger("text-changed", self, text)


class CommandChooserRow(PathChooserRow):

    def __init__(self, app):

        PathChooserRow.__init__(self, app)

        self._application_window = app.get_application_window()

        self.connect("unmap", self._on_unmap)

    def _on_unmap(self, widget):

        self.remove_css_class("error")

    def set_text(self, text):

        PathChooserRow.set_text(self, text)

        self._label.set_text(text)

        if not os.getenv("APP_RUNNING_AS_FLATPAK") == "true":

            if os.path.exists(text) and os.path.isfile(text) and os.access(text, os.X_OK):

                self.remove_css_class("error")

            elif not subprocess.getstatusoutput("type %s" % text.split(" ")[0])[0]:

                self.remove_css_class("error")

            elif not len(text):

                self.remove_css_class("error")

            else:

                self.add_css_class("error")


class IconChooserRow(PathChooserRow):

    def __init__(self, app):

        PathChooserRow.__init__(self, app)

        self._icon_finder = app.get_icon_finder()

        self._application_window = app.get_application_window()

        self.connect("unmap", self._on_unmap)

    def _on_unmap(self, widget):

        self.remove_css_class("error")

    def set_text(self, text):

        PathChooserRow.set_text(self, text)

        self._label.set_text(os.path.basename(text))

        if len(text):

            try:

                image = self._icon_finder.get_image(text)

            except IconNotFoundError:

                self.add_css_class("error")

                self._chooser_button.set_child(self._error_image)

            else:

                self.remove_css_class("error")

                self._chooser_button.set_child(image)

        else:

            self.remove_css_class("error")

            self._chooser_button.set_child(self._default_image)


class SwitchRow(Adw.ActionRow):

    def __init__(self):

        Adw.ActionRow.__init__(self)

        self._events = basic.EventManager()

        self._events.add("value-changed", object, bool)

        self._switch = Gtk.Switch()

        self._switch.set_can_focus(False)

        self._switch.set_valign(Gtk.Align.CENTER)

        self._switch.connect("notify::active", self._on_switch_active_changed)

        self.set_activatable(True)

        self.connect("activated", self._on_activated)

        self.add_suffix(self._switch)

    def _on_activated(self, action_row):

        self._switch.activate()

    def _on_switch_active_changed(self, switch, property):

        self._events.trigger("value-changed", self, switch.get_active())

    def get_switch(self):

        return self._switch

    def set_switch(self, switch):

        self._remove(self._switch)

        self._add_suffix(switch)

        self._switch = switch

    def get_active(self):

        return self._switch.get_active()

    def set_active(self, value):

        self._switch.set_active(value)

    def hook(self, event, callback, *args):

        self._events.hook(event, callback, *args)

    def release(self, id):

        self._events.release(id)


class ItemAlreadyExistingError(Exception):

    pass


class ItemNotFoundError(Exception):

    pass


class SearchList(Gtk.Box):

    def __init__(self, app, *args, **kwargs):

        Gtk.Box.__init__(self, *args, **kwargs)

        self._events = basic.EventManager()

        self._events.add("item-activated", str)

        self._names = {}

        self._children = {}

        self._min_row_width = 0

        self._icon_finder = app.get_icon_finder()

        self._application_window = app.get_application_window()

        self._focus_chain_widget = None

        self._toggle_button = Gtk.ToggleButton()

        self._toggle_button.set_icon_name(self._icon_finder.get_name("system-search-symbolic"))

        self._toggle_button.connect("toggled", self._on_toggle_button_toggled)

        self._search_entry_event_controller_key = Gtk.EventControllerKey()

        self._search_entry_event_controller_key.connect("key-pressed", self._on_search_entry_controller_key_pressed)

        self._search_entry = Gtk.SearchEntry()

        self._search_entry.set_hexpand(True)

        self._search_entry.add_controller(self._search_entry_event_controller_key)

        self._search_entry.connect("search-changed", self._on_search_entry_search_changed)

        self._search_bar = Gtk.SearchBar()

        self._search_bar.set_key_capture_widget(self._application_window)

        self._search_bar.connect("notify::search-mode-enabled", self._on_search_bar_search_mode_enabled_changed)

        self._search_bar.set_child(self._search_entry)

        self._search_bar_box = Gtk.Box()

        self._search_revealer = self._search_bar.get_child().get_parent().get_parent()

        self._search_revealer.set_child(self._search_bar_box)

        self._search_bar_box.append(self._search_entry)

        self._search_bar.connect_entry(self._search_entry)

        self._flow_box_event_controller_key = Gtk.EventControllerKey()

        self._flow_box_event_controller_key.connect("key-pressed", self._on_flow_box_controller_key_pressed)

        self._flow_box = Gtk.FlowBox()

        self._flow_box.set_homogeneous(True)

        self._flow_box.set_valign(Gtk.Align.START)

        self._flow_box.set_margin_top(Margin.DEFAULT)

        self._flow_box.set_margin_bottom(Margin.DEFAULT)

        self._flow_box.set_margin_start(Margin.DEFAULT)

        self._flow_box.set_margin_end(Margin.DEFAULT)

        self._flow_box.set_row_spacing(Spacing.DEFAULT)

        self._flow_box.set_column_spacing(Spacing.DEFAULT)

        self._flow_box.set_selection_mode(Gtk.SelectionMode.NONE)

        self._flow_box.add_controller(self._flow_box_event_controller_key)

        self._flow_box.connect("child-activated", self._on_flow_box_child_activated)

        self._scrolled_window = Gtk.ScrolledWindow()

        self._scrolled_window.set_vexpand(True)

        self._scrolled_window.set_kinetic_scrolling(True)

        self._scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._scrolled_window.set_child(self._flow_box)

        self._flow_box.set_vadjustment(self._scrolled_window.get_vadjustment())

        self.set_orientation(Gtk.Orientation.VERTICAL)

        self.append(self._search_bar)

        self.append(self._scrolled_window)

    def _on_toggle_button_toggled(self, button):

        self._search_bar.set_search_mode(button.get_active())

    def _on_search_entry_search_changed(self, search_entry):

        self._update_search_results()

    def _on_search_bar_search_mode_enabled_changed(self, search_bar, property):

        self._toggle_button.set_active(self._search_bar.get_search_mode())

    def _on_search_entry_controller_key_pressed(self, controller, keyval, keycode, state):

        if keyval == Keyval.ESCAPE:

            self._toggle_button.grab_focus()

            self._search_bar.set_search_mode(False)

            return True

        elif keyval == Keyval.UP:

            if not len(self._search_entry.get_text()):

                self._search_bar.set_search_mode(False)

            self._toggle_button.grab_focus()

            return True

        elif keyval == Keyval.DOWN:

            if not len(self._search_entry.get_text()):

                self._search_bar.set_search_mode(False)

    def _on_flow_box_controller_key_pressed(self, controller, keyval, keycode, state):

        if keyval == Keyval.ESCAPE and self._search_bar.get_search_mode():

            self._toggle_button.grab_focus()

            self._search_bar.set_search_mode(False)

            return True

        elif keyval == Keyval.TAB:

            return self._focus_chain_widget_grab_focus()

        elif keyval == Keyval.UP and self._flow_box.get_focus_child() in self._get_top_children():

            if not self._search_bar.get_search_mode():

                self._search_bar.set_search_mode(True)

            self._search_entry.grab_focus()

            return True

        elif keyval == Keyval.RIGHT:

            visible_children = self._get_visible_children()

            focused_child_index = visible_children.index(self._flow_box.get_focus_child())

            division_result = (focused_child_index + 1) / len(self._get_top_children())

            if division_result == int(division_result):

                return self._focus_chain_widget_grab_focus()

    def _on_flow_box_child_activated(self, flow_box, child):

        self._events.trigger("item-activated", self._names[child])

    def _get_visible_children(self):

        children = []

        for child in list(reversed(self._children.values())):

            if child["widget"].get_visible():

                children.append(child["widget"])

        return children

    def _get_children_at_row(self, value):

        children = []

        visible_children = self._get_visible_children()

        child_width = visible_children[0].get_width()

        child_height = visible_children[0].get_height()

        vertical_position = value * (child_height + self._flow_box.get_row_spacing())

        step_width = child_width + self._flow_box.get_column_spacing()

        for n in range(int(self._flow_box.get_width() / step_width)):

            child = self._flow_box.get_child_at_pos((child_width / 2) + (n * step_width), vertical_position)

            if not child == None:

                children.append(child)

        return children

    def _get_top_children(self):

        return self._get_children_at_row(0)

    def _update_search_results(self):

        text = self._search_entry.get_text().lower()

        for name in self._children:

            for keyword in self._children[name]["keywords"]:

                if text in keyword:

                    self._children[name]["widget"].set_visible(True)

                    break

            else:

                self._children[name]["widget"].set_visible(False)

    def _focus_chain_widget_grab_focus(self):

        if not self._focus_chain_widget == None and self._focus_chain_widget.get_mapped():

            self._focus_chain_widget.grab_focus()

            return True

    def get_min_row_width(self):

        return self._min_row_width

    def set_min_row_width(self, value):

        if not value == self._min_row_width:

            for child in self._children:

                child.set_size_request(value, -1)

            self._min_row_width = value

    def get_focus_chain_widget(self, widget):

        return self._focus_chain_widget

    def set_focus_chain_widget(self, widget):

        self._focus_chain_widget = widget

    def get_search_button(self):

        return self._toggle_button

    def list(self):

        return list(self._children)

    def clear(self):

        for name in self.list():

            self.remove(name)

    def update(self, name, text, icon, keywords):

        if name in self._children:

            image = self._children[name]["image"]

            label = self._children[name]["label"]

            try:

                self._icon_finder.set_image(image, icon)

            except IconNotFoundError:

                image.clear()

            label.set_text(text)

            self._children[name]["keywords"] = [keyword.lower() for keyword in keywords]

            self._update_search_results()

        else:

            raise ItemNotFoundError(name)

    def add(self, name, text, icon=None, keywords=None):

        if not name in self._children:

            image = Gtk.Image()

            image.set_icon_size(Gtk.IconSize.LARGE)

            label = Gtk.Label()

            label.set_ellipsize(Pango.EllipsizeMode.END)

            box = Gtk.Box()

            box.set_margin_top(Margin.DEFAULT)

            box.set_margin_bottom(Margin.DEFAULT)

            box.set_margin_start(Margin.DEFAULT)

            box.set_margin_end(Margin.DEFAULT)

            box.set_spacing(Spacing.DEFAULT)

            box.append(image)

            box.append(label)

            child = Gtk.FlowBoxChild()

            child.add_css_class("frame")

            child.set_child(box)

            child.set_size_request(self._min_row_width, 0)

            self._flow_box.prepend(child)

            self._names[child] = name

            self._children[name] = {}

            self._children[name]["widget"] = child

            self._children[name]["image"] = image

            self._children[name]["label"] = label

            if not isinstance(keywords, list):

                keywords = [text]

            self.update(name, text, icon, keywords)

            self._update_search_results()

        else:

            raise ItemAlreadyExistingError(name)

    def remove(self, name):

        if name in self._children:

            child = self._children[name]["widget"]

            self._flow_box.remove(child)

            del self._names[child]

            del self._children[name]

            self._update_search_results()

        else:

            raise ItemNotFoundError(name)

    def hook(self, event, callback):

        return self._events.hook(event, callback)

    def release(self, id):

        self._events.release(id)

    def grab_focus(self):

        if not self._search_bar.get_search_mode():

            self._search_bar.set_search_mode(True)

        self._search_entry.grab_focus()


class ItemNotSwitchError(Exception):

    pass


class Menu(Gio.Menu):

    def __init__(self, app, *args, **kwargs):

        Gio.Menu.__init__(self, *args, **kwargs)

        self._events = basic.EventManager()

        self._application_window = app.get_application_window()

        self._names = {}

        self._widgets = {}

    def _on_action_event(self, action, property):

        self._events.trigger(self._names[action])

    def get_switch_state(self, name):

        if isinstance(self._widgets[name], Gtk.Switch):

            return self._widgets[name].get_active()

        else:

            raise ItemNotSwitchError(name)

    def set_switch_state(self, name, value):

        if isinstance(self._widgets[name], Gtk.Switch):

            self._widgets[name].set_active(value)

        else:

            raise ItemNotSwitchError(name)

    def _add_action(self, action, widget, name, label):

        self.append(label, "win.%s" % name)

        self._events.add(name)

        self._names[action] = name

        self._widgets[name] = widget

        self._application_window.add_action(action)

    def get_enabled(self, name):

        for action in self._names:

            if self._names[action] == name:

                return action.get_enabled()

        else:

            raise ItemNotFoundError(name)

    def set_enabled(self, name, value):

        for action in self._names:

            if self._names[action] == name:

                action.set_enabled(value)

                break
        else:

            raise ItemNotFoundError(name)

    def add_button(self, name, label):

        action = Gio.SimpleAction.new(name, None)

        action.connect("activate", self._on_action_event)

        self._add_action(action, None, name, label)

    def add_switch(self, name, label):

        widget = Gtk.Switch()

        action = Gio.PropertyAction.new(name, widget, "active")

        action.connect("notify", self._on_action_event)

        self._add_action(action, widget, name, label)

    def hook(self, name, callback):

        return self._events.hook(name, callback)

    def release(self, id):

        self._events.release(id)


class Application(Adw.Application):

    def __init__(self, project_dir, *args, **kwargs):

        Adw.Application.__init__(self, *args, **kwargs)

        self._application_window = Adw.ApplicationWindow()

        self._flatpak_filesystem_prefix = os.path.join(os.path.sep, "run", "host")

        self._project_dir = os.path.abspath(os.path.realpath(project_dir))

        self._app_name = os.path.basename(self._project_dir)

        self._config_dir = os.path.join(GLib.get_user_data_dir(), self._app_name)

        ###############################################################################################################

        self._config_manager = basic.ConfigManager(

            os.path.join(self._project_dir, "config.json"),

            os.path.join(self._config_dir, "config.json")

            )

        self._locale_manager = basic.LocaleManager(

            os.path.join(self._project_dir, "locales")

            )

        ###############################################################################################################

        self._icon_finder = IconFinder(self)

        self._style_manager = Adw.StyleManager.get_default()

        self._style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

        ###############################################################################################################

        self._flatpak_host_user_data_dirs = [

            os.path.join(os.path.sep, "home", os.getenv("USER"), ".local", "share")

            ]

        self._system_data_dirs = [

            os.path.join(GLib.get_user_data_dir(), "flatpak", "exports", "share"),

            os.path.join(os.path.sep, "var", "lib", "flatpak", "exports", "share"),

            os.path.join(os.path.sep, "var", "lib", "snapd", "desktop")

            ]

        ###############################################################################################################

        if not os.getenv("APP_RUNNING_AS_FLATPAK") == "true":

            self._system_data_dirs += [

                os.path.join(os.path.sep, "usr", "local", "share"),

                os.path.join(os.path.sep, "usr", "share")

                ]

            if not os.getenv("XDG_DATA_DIRS") is None:

                for path in os.getenv("XDG_DATA_DIRS").split(":"):

                    if not path in self._system_data_dirs:

                        self._system_data_dirs.append(path)

        else:

            self._system_data_dirs += [

                os.path.join(self._flatpak_filesystem_prefix, "usr", "local", "share"),

                os.path.join(self._flatpak_filesystem_prefix, "usr", "share")

                ]

        ###############################################################################################################

        for path in self._system_data_dirs:

            self._icon_finder.add_search_path(os.path.join(path, "icons"))

        ###############################################################################################################

        self.connect("activate", self._on_activate)

        self.connect("shutdown", self._on_shutdown)

    def _on_activate(self, app):

        self._application_window.set_default_size(

            self._config_manager.get("window.width"),

            self._config_manager.get("window.height")

            )

        if self._config_manager.get("window.maximized"):

            self._application_window.maximize()

        self._application_window.set_application(self)

        self._application_window.show()

    def _on_shutdown(self, app):

        self._config_manager.set("window.width", self._application_window.get_default_size()[0])

        self._config_manager.set("window.height", self._application_window.get_default_size()[1])

        self._config_manager.set("window.maximized", self._application_window.is_maximized())

        self._config_manager.save()

    def _join_path_prefix(self, *paths):

        names = [""]

        for path in paths:

            names.append(os.path.sep.join(list(filter(None, path.split(os.path.sep)))))

        return os.path.sep.join(names)

    def get_application_window(self):

        return self._application_window

    def get_project_dir(self):

        return self._project_dir

    def get_app_name(self):

        return self._app_name

    def get_config_dir(self):

        return self._config_dir

    def get_config_manager(self):

        return self._config_manager

    def get_locale_manager(self):

        return self._locale_manager

    def get_icon_finder(self):

        return self._icon_finder

    def get_flatpak_host_user_data_path(self, path):

        if path.startswith(GLib.get_user_data_dir()):

            for directory in self._flatpak_host_user_data_dirs:

                test = self._join_path_prefix(directory, path[len(GLib.get_user_data_dir()):])

                if os.path.exists(test):

                    return test

            else:

                return test

        else:

            return path

    def get_flatpak_host_system_path(self, path):

        if path.startswith(self._flatpak_filesystem_prefix):

            return os.path.join(os.path.sep, path[len(self._flatpak_filesystem_prefix):])

        else:

            return path

    def get_flatpak_sandbox_system_path(self, path):

        if not os.path.exists(path):

            target = path

            while True:

                if os.path.islink(target):

                    target = os.path.realpath(path)

                test = os.path.join(self._join_path_prefix(self._flatpak_filesystem_prefix, target))

                if os.path.exists(test):

                    return test

                elif os.path.islink(test):

                    target = os.path.realpath(test)

                else:

                    return path

        else:

            return path
