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


import os, threading, subprocess, gi, re

gi.require_version("Adw", "1")

gi.require_version("Gtk", "4.0")

gi.require_version("Gdk", "4.0")

gi.require_version("Gio", "2.0")

gi.require_version("GLib", "2.0")

gi.require_version("GObject", "2.0")

gi.require_version("Pango", "1.0")

from gi.repository import Adw

from gi.repository import Gtk

from gi.repository import Gdk

from gi.repository import Gio

from gi.repository import GLib

from gi.repository import GObject

from gi.repository import Pango

from modules import basic


class Timeout():

    DEFAULT = 2


class Spacing():

    DEFAULT = 6

    LARGE = 11

    LARGER = 24

    LARGEST = 36


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


class IconNotFoundError(Exception):

    pass


class IconFinder():

    def __init__(self, app):

        self._application = app

        self._application_window = app.get_application_window()

        self._alternatives = {}

        self._legacy_icons = {}

        self._icon_theme = Gtk.IconTheme.get_for_display(self._application_window.get_display())

        self._load_legacy_icons(*self._icon_theme.get_search_path())

    def _load_legacy_icons(self, *paths):

        for path in paths:

            if os.path.exists(path):

                for name in os.listdir(path):

                    icon_path = os.path.join(path, name)

                    if os.path.isfile(icon_path):

                        self._legacy_icons[".".join(name.split(".")[:-1])] = icon_path

                        self._legacy_icons[name] = icon_path

    def get_search_paths(self):

        return self._icon_theme.get_search_path()

    def add_search_paths(self, *paths):

        for path in paths:

            if not path in self._icon_theme.get_search_path():

                self._icon_theme.add_search_path(path)

                self._load_legacy_icons(path)

    def get_alternatives(self, name):

        if name in self._alternatives:

            return list(self._alternatives[name])

        else:

            raise IconNotFoundError(name)

    def add_alternatives(self, name, *alternatives):

        if not name in self._alternatives:

            self._alternatives[name] = list(alternatives)

        else:

            for alternative in alternatives:

                self._alternatives[name].append(alternative)

    def get_image(self, icon, missing_ok=True):

        image = Gtk.Image()

        self.set_image(image, icon, missing_ok=missing_ok)

        return image

    def set_image(self, image, icon, missing_ok=True):

        try:

            name = self.get_name(icon, missing_ok=False)

            image.set_from_icon_name(name)

            return True

        except IconNotFoundError:

            if icon in self._legacy_icons:

                icon = self._legacy_icons[icon]

            elif not icon.endswith("-symbolic") and f"{icon}-symbolic" in self._legacy_icons:

                icon = self._legacy_icons[f"{icon}-symbolic"]

            if os.getenv("APP_RUNNING_AS_FLATPAK"):

                icon = self._application.get_flatpak_sandbox_system_path(icon)

            if os.path.exists(icon) and os.path.isfile(icon) and os.access(icon, os.R_OK):

                try:

                    texture = Gdk.Texture.new_from_filename(icon)

                except GLib.GError:

                    pass

                else:

                    image.set_from_paintable(texture)

                    return True

            elif missing_ok:

                if not os.path.sep in icon:

                    image.set_from_icon_name(icon)

                else:

                    image.set_from_file(icon)

                return False

            else:

                raise IconNotFoundError(icon)

    def get_name(self, name, missing_ok=True):

        if self._icon_theme.has_icon(name):

            return name

        elif not name.endswith("-symbolic") and self._icon_theme.has_icon(f"{name}-symbolic"):

            return f"{name}-symbolic"

        elif name in self._alternatives:

            for alternative in self._alternatives[name]:

                if self._icon_theme.has_icon(alternative):

                    return alternative

                elif not alternative.endswith("-symbolic") and self._icon_theme.has_icon(f"{alternative}-symbolic"):

                    return f"{alternative}-symbolic"

        if missing_ok:

            return name

        else:

            raise IconNotFoundError(name)

    def get_theme(self):

        return self._icon_theme


class IconName(GObject.Object):

    name = GObject.Property(type=str)

    def __init__(self, name):

        super().__init__()

        self.name = name


class IconBrowserRow(Adw.PreferencesRow):

    def __init__(self, app, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self._icon_finder = app.get_icon_finder()

        self._events = basic.EventManager()

        self._events.add("search-completed", object)

        self._events.add("active-changed", bool)

        self._icon_names = []

        self._string_separator = ";"

        self._keyword_separator = " "

        self._search_string = ""

        self._results_cache = {}

        self._max_cached_results = 10

        self._results_key = None

        self._min_keywords_length = 0

        self._lower_string = ""

        self._can_set_active = False

        self._default_text = None

        self._default_text_changed = False

        self._entry = {}

        self._entry_timeout_id = None

        self._search_delay = 60

        self._search_thread = None

        self._search_interrupted = False

        self._name_slices = []

        self._slice_length = 90

        self._slice_call_id = None

        self._list_store = Gio.ListStore()

        self._selection_model = Gtk.NoSelection()

        self._selection_model.set_model(self._list_store)

        self._factory = Gtk.SignalListItemFactory()

        self._factory.connect("setup", self._on_factory_setup)

        self._factory.connect("bind", self._on_factory_bind)

        self._grid_view = Gtk.GridView()

        self._grid_view.set_max_columns(48)

        self._grid_view.set_margin_top(Margin.DEFAULT)

        self._grid_view.set_margin_bottom(Margin.DEFAULT)

        self._grid_view.set_margin_start(Margin.DEFAULT)

        self._grid_view.set_margin_end(Margin.DEFAULT)

        self._grid_view.set_single_click_activate(True)

        self._grid_view.connect("activate", self._on_grid_view_activate)

        self._grid_view.set_model(self._selection_model)

        self._grid_view.set_factory(self._factory)

        self._scrolled_window = Gtk.ScrolledWindow()

        self._scrolled_window.set_child(self._grid_view)

        self._scrolled_window.set_size_request(-1, 240)

        self._revealer = Gtk.Revealer()

        self._revealer.set_reveal_child(False)

        self._revealer.set_child(self._scrolled_window)

        self._revealer.connect("notify::reveal-child", self._on_revealer_reveal_child_changed)

        self._revealer.connect("notify::child-revealed", self._on_revealer_child_revealed_changed)

        self._entry_event_controller_focus = Gtk.EventControllerFocus()

        self._entry_event_controller_focus.connect_after("enter", self._on_event_controller_focus_enter)

        self._entry_event_controller_focus.connect_after("leave", self._on_event_controller_focus_leave)

        self._entry_event_controller_key = Gtk.EventControllerKey()

        self._entry_event_controller_key.connect("key-pressed", self._on_event_controller_key_pressed)

        self._main_event_controller_focus = Gtk.EventControllerFocus()

        self._main_event_controller_focus.connect_after("enter", self._on_event_controller_focus_enter)

        self._main_event_controller_focus.connect_after("leave", self._on_event_controller_focus_leave)

        self._main_event_controller_key = Gtk.EventControllerKey()

        self._main_event_controller_key.connect("key-pressed", self._on_event_controller_key_pressed)

        self.set_margin_top(1)

        self.set_activatable(False)

        self.add_css_class("view")

        self.add_controller(self._main_event_controller_focus)

        self.add_controller(self._main_event_controller_key)

        self.set_child(self._revealer)

        self.set_visible(False)

        GLib.idle_add(self._update_search_data)

    def _on_event_controller_focus_enter(self, controller):

        GLib.idle_add(self._after_event_controller_focus_enter)

    def _after_event_controller_focus_enter(self):

        text = self._entry["widget"].get_text()

        if not text in self._icon_names:

            if self.get_parent().get_focus_child():

                self.set_active(True)

    def _on_event_controller_focus_leave(self, controller):

        GLib.idle_add(self._after_event_controller_focus_leave)

    def _after_event_controller_focus_leave(self):

        text = self._entry["widget"].get_text()

        if text in self._icon_names:

            if not self.get_parent().get_focus_child():

                self.set_active(False)

    def _on_event_controller_key_pressed(self, controller, keyval, keycode, state):

        if keyval == Keyval.ESCAPE:

            if self.get_active():

                self._entry["widget"].grab_focus()

            self._toggle_set_active()

    def _on_revealer_reveal_child_changed(self, revealer, gparam):

        if self._revealer.get_reveal_child():

            self.show()

    def _on_revealer_child_revealed_changed(self, revealer, gparam):

        if not self._revealer.get_child_revealed():

            self.hide()

    def _on_factory_setup(self, factory, list_item):

        image = Gtk.Image()

        image.set_pixel_size(48)

        list_item.set_child(image)

    def _on_factory_bind(self, factory, list_item):

        list_item.get_child().set_from_icon_name(list_item.get_item().name)

    def _on_grid_view_activate(self, grid_view, position):

        self.set_active(False)

        self.set_default_text(self._list_store[position].name)

        self._entry["widget"].grab_focus()

    def _on_entry_changed(self, entry):

        if self._entry_timeout_id:

            GLib.source_remove(self._entry_timeout_id)

        self._entry_timeout_id = GLib.timeout_add(self._search_delay, self._after_entry_changed)

    def _after_entry_changed(self):

        self._start_search_thread()

        self._entry_timeout_id = None

        return GLib.SOURCE_REMOVE

    def _toggle_set_active(self):

        if not self.get_active():

            self._entry["widget"].grab_focus()

            self.set_active(True)

        else:

            self.set_active(False)

    def _update_search_data(self):

        self._icon_names = self._icon_finder.get_theme().get_icon_names()

        self._search_string = self._string_separator.join(self._icon_names)

        self._lower_string = self._search_string.lower()

    def _start_search_thread(self):

        text = self._entry["widget"].get_text()

        keywords = set(filter(None, text.lower().replace(self._string_separator, self._keyword_separator).split(self._keyword_separator)))

        results_key = self._keyword_separator.join(keywords)

        if not results_key == self._results_key:

            self._results_key = results_key

            self._stop_search_thread()

            self._list_store.remove_all()

            self._search_thread = threading.Thread(target=self._search_thread_target, args=[text, keywords, results_key])

            self._search_thread.start()

        else:

            self._after_search_thread_finished()

    def _stop_search_thread(self):

        if self._entry_timeout_id:

            GLib.source_remove(self._entry_timeout_id)

            self._entry_timeout_id = None

        if self._slice_call_id:

            GLib.source_remove(self._slice_call_id)

            self._slice_call_id = None

        if self._search_thread:

            self._search_interrupted = True

            self._search_thread.join()

            self._search_interrupted = False

            self._search_thread = None

            return True

    def _search_thread_target(self, text, keywords, results_key):

        try:

            names = self._results_cache[results_key]

        except KeyError:

            if not len(keywords) >= self._min_keywords_length:

                names = []

            else:

                if not len(keywords):

                    names = [IconName(name) for name in self._icon_names]

                else:

                    names = self._get_names(keywords, exclude=[text])

                try:

                    del self._results_cache[list(self._results_cache.keys())[-self._max_cached_results]]

                except IndexError:

                    pass

                self._results_cache[results_key] = names

        if len(names):

            self._name_slices = [names[i:i+self._slice_length] for i in range(0, len(names), self._slice_length)]

            self._slice_call_id = GLib.idle_add(self._add_next_slice)

            self._can_set_active = True

            GLib.idle_add(self._after_search_thread_finished)

        else:

            self._can_set_active = False

            GLib.idle_add(self._after_search_thread_finished)

        self._search_thread = None

    def _after_search_thread_finished(self):

        text = self._entry["widget"].get_text()

        if not text in self._icon_names:

            self._default_text_changed = False

            self.set_active(True)

        elif self._default_text_changed:

            self._default_text_changed = False

            self.set_active(False)

        elif len(self._list_store):

            self._default_text_changed = False

            self.set_active(True)

        else:

            self._default_text_changed = False

            self.set_active(True)

        self._events.trigger("search-completed", self._list_store)

    def _add_next_slice(self):

        try:

            self._list_store.splice(len(self._list_store), 0, self._name_slices.pop(0))

        except IndexError:

            self._slice_call_id = None

            return GLib.SOURCE_REMOVE

        else:

            self._slice_call_id = GLib.idle_add(self._add_next_slice)

            return GLib.SOURCE_REMOVE

    def _get_names(self, keywords, exclude=[]):

        names = []

        for string in keywords:

            names.append([])

            start_pos = 0

            while not self._search_interrupted:

                try:

                    start_pos = self._lower_string.index(string, start_pos)

                except ValueError:

                    break

                else:

                    start_pos -= 1

                    while not self._search_string[start_pos:start_pos + len(self._string_separator)] == self._string_separator:

                        start_pos -= 1

                        if start_pos < 1:

                            start_pos = 0

                            break

                    else:

                        start_pos += 1

                    try:

                        end_pos = self._search_string.index(self._string_separator, start_pos)

                    except ValueError:

                        name = self._search_string[start_pos:]

                        if not name in exclude:

                            names[-1].append(name)

                        break

                    else:

                        name = self._search_string[start_pos:end_pos]

                        if not name in exclude:

                            names[-1].append(name)

                        start_pos = end_pos + len(self._string_separator)

                        if not len(self._search_string) > start_pos:

                            break

            else:

                return []

        else:

            return [IconName(name) for name in self._get_matching_names(names)]

    def _get_matching_names(self, lists):

        first_list = lists.pop(0)

        first_list = set(first_list)

        for remaining_list in lists:

            first_list = first_list.intersection(remaining_list)

        else:

            return first_list

    def get_search_entry(self):

        return self._entry["widget"]

    def set_search_entry(self, entry):

        try:

            self._entry["widget"].remove_controller(self._entry_event_controller_focus)

            self._entry["widget"].remove_controller(self._entry_event_controller_key)

            self._entry["widget"].disconnect(self._entry["changed-event-id"])

        except KeyError:

            pass

        entry.add_controller(self._entry_event_controller_focus)

        entry.add_controller(self._entry_event_controller_key)

        self._entry["changed-event-id"] = entry.connect("changed", self._on_entry_changed)

        self._entry["widget"] = entry

    def get_default_text(self):

        return self._default_text

    def set_default_text(self, text):

        self._default_text = text

        self._default_text_changed = True

        if not text == self._entry["widget"].get_text():

            self._entry["widget"].set_text(text)

        elif not self._default_text and not len(text):

            self._start_search_thread()

    def get_active(self):

        return self._revealer.get_reveal_child()

    def set_active(self, value, check=True):

        if not self._default_text_changed:

            if check and not self._can_set_active:

                value = False

            elif not self.get_parent().get_focus_child():

                value = False

            self._revealer.set_reveal_child(value)

            self._events.trigger("active-changed", value)

    def hook(self, event, callback, *args):

        self._events.hook(event, callback, *args)

    def release(self, id):

        self._events.release(id)


class EntryRow(Adw.EntryRow):

    def __init__(self, app, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

        try:

            self.add_css_class(os.getenv("CUSTOM_ROW_STYLE"))

        except TypeError:

            pass

        # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

        self._icon_finder = app.get_icon_finder()

        self._events = basic.EventManager()

        self._events.add("text-changed", object, str)

        self._event_controller_focus = Gtk.EventControllerFocus()

        self._event_controller_focus.connect("leave", self._on_event_controller_focus_leave)

        self._editable = self.get_delegate()

        self._editable.add_controller(self._event_controller_focus)

        self.set_enable_undo(True)

        self.connect("changed", self._on_changed)

    def _on_event_controller_focus_leave(self, controller):

        self.select_region(0, 0)

    def _on_changed(self, editable):

        text = editable.get_text()

        self._events.trigger("text-changed", self, text)

    def hook(self, event, callback, *args):

        self._events.hook(event, callback, *args)

    def release(self, id):

        self._events.release(id)


class PathChooserRow(EntryRow):

    def __init__(self, app, action, *args, **kwargs):

        super().__init__(app, *args, **kwargs)

        self._icon_finder = app.get_icon_finder()

        self._application_window = app.get_application_window()

        self._default_image = self._icon_finder.get_image("document-open-symbolic")

        self._chooser_button_event_controller_key = Gtk.EventControllerKey()

        self._chooser_button_event_controller_key.connect(

            "key-pressed", self._on_chooser_button_event_controller_key_pressed

            )

        self._chooser_button = Gtk.Button()

        self._chooser_button.add_css_class("flat")

        self._chooser_button.set_valign(Gtk.Align.CENTER)

        self._chooser_button.connect("clicked", self._on_chooser_button_clicked)

        self._chooser_button.add_controller(self._chooser_button_event_controller_key)

        self._chooser_button.set_child(self._default_image)

        self._dialog_accept_button = Gtk.Button()

        self._dialog_accept_button.add_css_class("suggested-action")

        self._dialog_cancel_button = Gtk.Button()

        if not os.getenv("APP_RUNNING_AS_FLATPAK") == "true" or os.getenv("USE_NATIVE_DIALOGS") == "true":

            self._file_chooser_dialog = Gtk.FileChooserNative(action=action)

        else:

            self._file_chooser_dialog = Gtk.FileChooserDialog(action=action)

            self._file_chooser_dialog.add_action_widget(self._dialog_accept_button, Gtk.ResponseType.ACCEPT)

            self._file_chooser_dialog.add_action_widget(self._dialog_cancel_button, Gtk.ResponseType.CANCEL)

            self._file_chooser_dialog.set_default_response(Gtk.ResponseType.ACCEPT)

        self._file_chooser_dialog.connect("response", self._on_file_chooser_dialog_response)

        self._file_chooser_dialog.set_transient_for(self._application_window)

        self._file_chooser_dialog.set_modal(True)

        self.add_suffix(self._chooser_button)

        try:

            self._edit_gizmo = self.get_child().get_first_child().get_next_sibling()

            self._edit_image = self._edit_gizmo.get_next_sibling().get_next_sibling().get_next_sibling()

            self._edit_image.unparent()

        except AttributeError:

            pass

    def _on_chooser_button_event_controller_key_pressed(self, controller, keyval, keycode, state):

        text = self._editable.get_text()

        controller.forward(self._editable)

        if not text == self._editable.get_text():

            if not self._editable.has_focus():

                self._editable.grab_focus_without_selecting()

            return True

    def _on_file_chooser_dialog_response(self, dialog, response):

        self._file_chooser_dialog.hide()

        if response == Gtk.ResponseType.ACCEPT:

            self.set_text(self._file_chooser_dialog.get_file().get_path())

    def _on_chooser_button_clicked(self, button):

        self._file_chooser_dialog.show()

    def get_dialog_accept_button_label(self, text):

        return self._dialog_accept_button.get_label()

    def set_dialog_accept_button_label(self, text):

        self._dialog_accept_button.set_label(text)

    def get_dialog_cancel_button_label(self):

        return self._dialog_cancel_button.get_label()

    def set_dialog_cancel_button_label(self, text):

        self._dialog_cancel_button.set_label(text)

    def set_dialog_title(self, text):

        self._file_chooser_dialog.set_title(text)

    def get_dialog_title(self):

        return self._file_chooser_dialog.get_title()

    def get_chooser_button(self):

        return self._chooser_button


class FileChooserRow(PathChooserRow):

    def __init__(self, app, *args, **kwargs):

        super().__init__(app, action=Gtk.FileChooserAction.OPEN, *args, **kwargs)


class DirectoryChooserRow(PathChooserRow):

    def __init__(self, app, *args, **kwargs):

        super().__init__(app, action=Gtk.FileChooserAction.SELECT_FOLDER, *args, **kwargs)

    def _on_changed(self, editable):

        text = editable.get_text()

        self._events.trigger("text-changed", self, text)

        if len(text):

            if os.path.exists(text) and os.path.isdir(text) and os.access(text, os.R_OK):

                self.remove_css_class("error")

            else:

                self.add_css_class("error")

        else:

            self.remove_css_class("error")


class LinkConverterRow(Gtk.Box):

    def __init__(self, app, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self._application = app

        self._icon_finder = app.get_icon_finder()

        self._entry_connection_id = None

        self._entry = None

        self._url_regex_patterns = [

            r"((http|ftp|https)://)?(([a-zA-Z0-9]{1,}[_-]{1})*[a-zA-Z0-9]{1,}\.)+([a-zA-Z0-9]{2,}){1}" +

            r"(/[a-zA-Z0-9\@\%\&\#\=\~\+\-\_\.\,\;\:\?\!\'\*\$()\[\]\/]+)?$",

            ]

        self._url_open_commands = [

            "xdg-open",

            "open",

            "x-www-browser",

            "gnome-open",

            "kde-open"

            ]

        for command in self._url_open_commands:

            if app.get_command_exists(command):

                self._url_open_command = command

                break

        else:

            self._url_open_command = None

        self._button_label = Gtk.Label()

        self._button_label.set_ellipsize(Pango.EllipsizeMode.END)

        self._button_image = self._icon_finder.get_image("system-run-symbolic")

        self._button_image.set_margin_end(Margin.DEFAULT)

        self._center_box = Gtk.CenterBox()

        self._center_box.set_margin_start(Margin.LARGE)

        self._center_box.set_margin_end(Margin.LARGE)

        self._center_box.set_start_widget(self._button_image)

        self._center_box.set_center_widget(self._button_label)

        self._button = Gtk.Button()

        self._button.add_css_class("accent")

        self._button.add_css_class("circular")

        self._button.connect("clicked", self._on_button_clicked)

        self._button.set_child(self._center_box)

        self._clamp = Adw.Clamp(maximum_size=480, tightening_threshold=380)

        self._clamp.set_margin_top(Margin.LARGE)

        self._clamp.set_margin_bottom(Margin.LARGE)

        self._clamp.set_child(self._button)

        self._revealer = Gtk.Revealer()

        self._revealer.set_child(self._clamp)

        self._revealer.connect("notify::reveal-child", self._on_revealer_reveal_child_changed)

        self._revealer.connect("notify::child-revealed", self._on_revealer_child_revealed_changed)

        self.set_visible(False)

        self.set_orientation(Gtk.Orientation.VERTICAL)

        self.append(self._revealer)

    def _on_button_clicked(self, button):

        self._convert_url_to_command()

    def _on_entry_changed(self, entry):

        if self._url_open_command and self._get_string_is_valid_url(entry.get_text().strip()):

            entry.add_css_class("warning")

            entry.remove_css_class("error")

            self._revealer.set_reveal_child(True)

        else:

            entry.remove_css_class("warning")

            self._revealer.set_reveal_child(False)

    def _on_revealer_reveal_child_changed(self, revealer, gparam):

        if self._revealer.get_reveal_child():

            self.show()

    def _on_revealer_child_revealed_changed(self, revealer, gparam):

        if not self._revealer.get_child_revealed():

            self.hide()

    def _convert_url_to_command(self):

        text = self._entry.get_text().strip()

        if text.startswith("http://"):

            text = text.replace("http://", "https://")

        elif not text.startswith("https://"):

            text = f"https://{text}"

        self._entry.set_text(f"{self._url_open_command} {text}")

    def _get_string_is_valid_url(self, text):

        if not " " in text and not self._application.get_command_exists(text, include_lookup_cwd=True):

            for pattern in self._url_regex_patterns:

                if re.match(pattern, text):

                    return True

    def get_entry(self, entry):

        return self._entry

    def set_entry(self, entry):

        if not self._entry == None:

            self._entry.dicsonnect(self._entry_connection_id)

        self._entry = entry

        self._entry_connection_id = self._entry.connect("changed", self._on_entry_changed)

    def get_label(self):

        return self._button_label.get_text()

    def set_label(self, text):

        self._button_label.set_text(text)


class CommandChooserRow(FileChooserRow):

    def __init__(self, app, *args, **kwargs):

        super().__init__(app, *args, **kwargs)

        self._application = app

        self.add_css_class("error")

    def _on_file_chooser_dialog_response(self, dialog, response):

        self._file_chooser_dialog.hide()

        if response == Gtk.ResponseType.ACCEPT:

            path = self._file_chooser_dialog.get_file().get_path().replace(" ", "\ ")

            self.set_text(path)

    def _on_changed(self, editable):

        text = editable.get_text()

        self._events.trigger("text-changed", self, text)

        if not len(text.strip()):

            self.add_css_class("error")

        elif not self._application.get_command_exists(text, skip_empty_path=True, include_lookup_cwd=True):

            self.add_css_class("error")

        else:

            self.remove_css_class("error")


class IconChooserRow(FileChooserRow):

    def __init__(self, app, *args, **kwargs):

        super().__init__(app, *args, **kwargs)

        self.add_css_class("warning")

        self._default_icon_image = self.get_chooser_button().get_child()

        self._default_icon_image.get_parent().set_child(None)

        self._search_icon_image = self._icon_finder.get_image("system-search-symbolic")

        self._icon_image_stack = Gtk.Stack()

        self._icon_image_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        self._icon_image_stack.set_transition_duration(int(self._icon_image_stack.get_transition_duration() / 2))

        self._icon_image_stack.add_child(self._search_icon_image)

        self._icon_image_stack.add_child(self._default_icon_image)

        self.get_chooser_button().set_child(self._icon_image_stack)

    def _on_changed(self, editable):

        text = editable.get_text()

        self._events.trigger("text-changed", self, text)

        try:

            self._icon_finder.set_image(self._icon_image, text, missing_ok=False)

        except IconNotFoundError:

            self.add_css_class("warning")

            self._icon_image.set_from_file(None)

        else:

            self.remove_css_class("warning")

    def get_show_search_icon(self):

        return self._icon_image_stack.get_visible_child() == self._search_icon_image

    def set_show_search_icon(self, value):

        if value:

            self._icon_image_stack.set_visible_child(self._search_icon_image)

        else:

            self._icon_image_stack.set_visible_child(self._default_icon_image)

    def get_image(self):

        return self._icon_image

    def set_image(self, image):

        self._icon_image = image


class IconViewRow(Adw.PreferencesRow):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        icon_image = Gtk.Image()

        self.set_image(icon_image)

        self.set_activatable(False)

        self.set_can_focus(False)

        self.set_can_target(False)

        self.add_css_class("view")

    def get_image(self):

        return self.get_child()

    def set_image(self, image):

        self.set_child(image)

        image.set_pixel_size(128)

        image.set_margin_top(Margin.LARGER)

        image.set_margin_bottom(Margin.LARGER)

        image.set_margin_start(Margin.LARGER)

        image.set_margin_end(Margin.LARGER)


class DeleteRow(Adw.ActionRow):

    def __init__(self, app, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

        try:

            self.add_css_class(os.getenv("CUSTOM_ROW_STYLE"))

        except TypeError:

            pass

        # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

        self._icon_finder = app.get_icon_finder()

        self._delete_button = Gtk.Button()

        self._delete_button.set_icon_name(self._icon_finder.get_name("edit-delete-symbolic"))

        self._delete_button.add_css_class("flat")

        self._delete_button.set_can_focus(False)

        self._delete_button.set_can_target(False)

        self._delete_button.set_valign(Gtk.Align.CENTER)

        self.add_css_class("warning")

        self.set_activatable(True)

        self.add_suffix(self._delete_button)

    def get_text(self, text):

        return self.get_subtitle()

    def set_text(self, text):

        if len(text):

            self.add_css_class("property")

        else:

            self.remove_css_class("property")

        self.set_subtitle(text)


class SwitchRow(Adw.ActionRow):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

        try:

            self.add_css_class(os.getenv("CUSTOM_ROW_STYLE"))

        except TypeError:

            pass

        # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

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


class TaggedRowTag(Gtk.FlowBoxChild):

    def __init__(self, app, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self._application = app

        self._icon_finder = app.get_icon_finder()

        self._flow_row = None

        self._show_warning = False

        self._tag_dark_css_class = "background" #FIXME

        self._button_label = Gtk.Label()

        self._button_label.set_ellipsize(Pango.EllipsizeMode.END)

        self._button_image = self._icon_finder.get_image("window-close-symbolic")

        self._button_image.set_margin_start(Margin.DEFAULT)

        self._center_box = Gtk.CenterBox()

        self._center_box.set_margin_start(Margin.LARGE)

        self._center_box.set_margin_end(Margin.LARGE)

        self._center_box.set_center_widget(self._button_label)

        self._center_box.set_end_widget(self._button_image)

        self._tag_button = Gtk.Button()

        self._tag_button.add_css_class("circular")

        self._tag_button.add_css_class(self._tag_dark_css_class)

        self._tag_button.connect("clicked", self._on_tag_button_clicked)

        self._tag_button.set_child(self._center_box)

        self._event_controller_focus = Gtk.EventControllerFocus()

        self._event_controller_focus.connect("enter", self._on_event_controller_focus_enter)

        self.add_controller(self._event_controller_focus)

        self.set_child(self._tag_button)

        self._style_manager = Adw.StyleManager.get_default()

        self._style_manager.connect("notify::dark", self._on_style_manager_dark_changed)

        self._update_tag_button_style()

    def _on_tag_button_clicked(self, button):

        if self._flow_row:

            self._flow_row.remove(self)

        else:

            self.get_parent().remove(self)

    def _on_event_controller_focus_enter(self, controller):

        self.set_can_focus(False)

        self.set_can_focus(True)

        GLib.idle_add(self._after_event_controller_focus_enter)

    def _after_event_controller_focus_enter(self):

        self._tag_button.grab_focus()

    def _on_style_manager_dark_changed(self, style_manager, gparam):

        self._update_tag_button_style()

    def _update_tag_button_style(self):

        if self._show_warning:

            self._tag_button.add_css_class("warning")

            self._tag_button.remove_css_class(self._tag_dark_css_class)

        else:

            self._tag_button.remove_css_class("warning")

            if self._style_manager.get_dark():

                self._tag_button.add_css_class(self._tag_dark_css_class)

            else:

                self._tag_button.remove_css_class(self._tag_dark_css_class)

    def get_text(self):

        return self._button_label.get_text()

    def set_text(self, text):

        self._button_label.set_text(text)

    def get_flow_row(self):

        return self._flow_row

    def set_flow_row(self, flow_row):

        self._flow_row = flow_row

    def get_show_warning(self):

        return self._show_warning

    def set_show_warning(self, value):

        self._show_warning = value

        self._update_tag_button_style()


class TagNotFoundError(Exception):

    pass


class TaggedFlowRow(Adw.PreferencesRow):

    def __init__(self, app, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self._events = basic.EventManager()

        self._events.add("text-changed", object, str)

        self._application = app

        self._icon_finder = app.get_icon_finder()

        self._ends_with_delimiter = None

        self._duplicate_tag_warnings = []

        self._delimiters = [";"]

        self._entry_row = None

        self._entry_row_default_values = {}

        self._entry_row_connection_ids = []

        self._flow_box_extra_margin = 1

        self._flow_box = Gtk.FlowBox()

        self._flow_box.set_margin_top(Margin.DEFAULT) #FIXME: + self._flow_box_extra_margin)

        self._flow_box.set_margin_bottom(Margin.DEFAULT) #FIXME: + self._flow_box_extra_margin)

        self._flow_box.set_margin_start(Margin.DEFAULT + self._flow_box_extra_margin)

        self._flow_box.set_margin_end(Margin.DEFAULT + self._flow_box_extra_margin)

        self._flow_box.set_selection_mode(Gtk.SelectionMode.NONE)

        self._revealer = Gtk.Revealer()

        # FIXME: self._revealer.set_transition_duration(self._revealer.get_transition_duration() / 2)

        self._revealer.connect("notify::reveal-child", self._on_revealer_reveal_child_changed)

        self._revealer.connect("notify::child-revealed", self._on_revealer_child_revealed_changed)

        self._revealer.set_child(self._flow_box)

        self.set_activatable(False)

        self.set_visible(False)

        self.set_child(self._revealer)

    def _on_revealer_reveal_child_changed(self, revealer, gparam):

        if self._revealer.get_reveal_child():

            self.show()

    def _on_revealer_child_revealed_changed(self, revealer, gparam):

        if not self._revealer.get_child_revealed():

            self.hide()

    def _on_entry_row_apply(self, entry_row):

        self.add_tags(entry_row.get_text(), allow_duplicates=False)

        self._entry_row.set_text("")

    def _on_entry_row_changed(self, editable):

        self._update_entry_row()

    def _do_flow_box_children_changed(self):

        self._events.trigger("text-changed", self, self.get_text())

        self._update_reveal_child()

        self._update_entry_row()

    def _update_reveal_child(self):

        self._revealer.set_reveal_child(self._flow_box.get_first_child())

    def _update_entry_row(self):

        text = self._entry_row.get_text()

        strings = self._split_text(text)

        duplicate_strings, duplicate_tags = self._get_duplicates(*strings, mark_duplicates=True)

        #FIXME: strings = [string for string in strings if not string in duplicate_strings]

        if not len(strings):

            self._entry_row.set_show_apply_button(False)

            self._entry_row.set_show_apply_button(True)

    def _split_text(self, *strings):

        for string in strings:

            for delimiter in self._delimiters:

                pieces = []

                for string in strings:

                    pieces += string.split(delimiter)

                strings = pieces

        else:

            return list(filter(None, strings))

    def _get_duplicates(self, *strings, mark_duplicates=False):

        duplicate_strings, duplicate_tags = [], []

        for string in strings:

            if not string in duplicate_strings:

                for tag in self.get_tags():

                    if string == tag.get_text():

                        duplicate_tags.append(tag)

                        if not string in duplicate_strings:

                            duplicate_strings.append(string)

        else:

            if mark_duplicates:

                for tag in self._duplicate_tag_warnings:

                    tag.set_show_warning(False)

                self._duplicate_tag_warnings = duplicate_tags

                for tag in duplicate_tags:

                    tag.set_show_warning(True)

            return duplicate_strings, duplicate_tags

    def get_entry_row(self):

        return self._entry_row

    def set_entry_row(self, entry_row):

        if self._entry_row:

            try:

                edit_gizmo = self._entry_row.get_child().get_first_child().get_next_sibling()

                edit_image = edit_gizmo.get_next_sibling().get_next_sibling().get_next_sibling()

                edit_image.set_from_icon_name(self._entry_row_default_values["icon-name"])

            except AttributeError:

                pass

            for connection_id in self._entry_row_connection_ids:

                self._entry_row.disconnect(connection_id)

            self._entry_row.set_show_apply_button(self._entry_row_default_values["show-apply-button"])

        self._entry_row = entry_row

        self._entry_row_default_values["show-apply-button"] = entry_row.get_show_apply_button()

        entry_row.set_show_apply_button(True)

        try:

            edit_gizmo = entry_row.get_child().get_first_child().get_next_sibling()

            edit_image = edit_gizmo.get_next_sibling().get_next_sibling().get_next_sibling()

            self._entry_row_default_values["icon-name"] = edit_image.get_icon_name()

            edit_image.set_from_icon_name(self._icon_finder.get_name("list-add-symbolic"))

        except AttributeError:

            pass

        self._entry_row_connection_ids.append(entry_row.connect("apply", self._on_entry_row_apply))

        self._entry_row_connection_ids.append(entry_row.connect("changed", self._on_entry_row_changed))

    def get_delimiters(self):

        return self._delimiters

    def set_delimiters(self, *strings):

        self._delimiters = list(*strings)

    def get_text(self):

        return self._delimiters[0].join([tag.get_text() for tag in self.get_tags()]) + int(bool(self._ends_with_delimiter))*";"

    def set_text(self, *strings):

        self._ends_with_delimiter = strings[-1].endswith(self._delimiters[0])

        self._flow_box.remove_all()

        self._update_reveal_child()

        self._update_entry_row()

        self.add_tags(*strings)

    def get_tags(self):

        tags = [self._flow_box.get_first_child()]

        if tags[0]:

            while True:

                next_sibling = tags[-1].get_next_sibling()

                if next_sibling:

                    tags.append(next_sibling)

                else:

                    return tags

        else:

            return []

    def add_tags(self, *strings, allow_duplicates=True):

        strings = self._split_text(*strings)

        if not allow_duplicates:

            duplicate_strings, duplicate_tags = self._get_duplicates(*strings)

            strings = [string for string in strings if not string in duplicate_strings]

        for string in strings:

            self.add(string, send_signals=False)

        if len(strings):

            self._do_flow_box_children_changed()

    def add(self, text, send_signals=True):

        if isinstance(text, TaggedRowTag):

            tag = text

        else:

            tag = TaggedRowTag(self._application)

            tag.set_text(text)

        tag.set_flow_row(self)

        self._flow_box.insert(tag, -1)

        if send_signals:

            self._do_flow_box_children_changed()

    def remove(self, text):

        if isinstance(text, TaggedRowTag):

            self._flow_box.remove(text)

            self._do_flow_box_children_changed()

        else:

            for tag in self.get_tags():

                if tag.get_text() == text:

                    self._flow_box.remove(tag)

                    self._do_flow_box_children_changed()

                    break

            else:

                raise TagNotFoundError(text)

    def reset(self):

        self._entry_row.set_text("")

        if self._flow_box.get_first_child():

            self._flow_box.remove_all()

            self._do_flow_box_children_changed()

        self._update_reveal_child()

    def hook(self, event, callback):

        return self._events.hook(event, callback)

    def release(self, id):

        self._events.release(id)


class ItemAlreadyExistingError(Exception):

    pass


class ItemNotFoundError(Exception):

    pass


class SearchList(Gtk.Box):

    def __init__(self, app, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self._events = basic.EventManager()

        self._events.add("item-activated", str)

        self._names = {}

        self._children = {}

        self._active_row = None

        self._ignore_selection = False

        self._reset_by_unfocus = False

        self._icon_finder = app.get_icon_finder()

        self._application_window = app.get_application_window()

        self._toggle_button = Gtk.ToggleButton()

        self._toggle_button.set_icon_name(self._icon_finder.get_name("system-search-symbolic"))

        self._toggle_button.connect("toggled", self._on_toggle_button_toggled)

        self._search_entry_event_controller_focus = Gtk.EventControllerFocus()

        self._search_entry_event_controller_focus.connect("leave", self._on_search_entry_event_controller_focus_leave)

        self._search_entry_event_controller_key = Gtk.EventControllerKey()

        self._search_entry_event_controller_key.connect("key-pressed", self._on_search_entry_controller_key_pressed)

        self._search_entry = Gtk.SearchEntry()

        self._search_entry.set_hexpand(True)

        self._search_entry.add_controller(self._search_entry_event_controller_focus)

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

        self._list_box_event_controller_key = Gtk.EventControllerKey()

        self._list_box_event_controller_key.connect("key-pressed", self._on_list_box_controller_key_pressed)

        self._list_box = Gtk.ListBox()

        self._list_box.set_sort_func(self._do_list_box_sort)

        self._list_box.add_css_class("navigation-sidebar")

        self._list_box.set_selection_mode(Gtk.SelectionMode.BROWSE)

        self._list_box.connect("selected-rows-changed", self._on_list_box_selected_rows_changed)

        self._list_box.add_controller(self._list_box_event_controller_key)

        self._list_box.connect("row-activated", self._on_list_box_row_activated)

        self._scrolled_window = Gtk.ScrolledWindow()

        self._scrolled_window.set_vexpand(True)

        self._scrolled_window.set_kinetic_scrolling(True)

        self._scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._scrolled_window.set_child(self._list_box)

        self.set_orientation(Gtk.Orientation.VERTICAL)

        self.append(self._search_bar)

        self.append(self._scrolled_window)

    def _on_toggle_button_toggled(self, button):

        self._search_bar.set_search_mode(button.get_active())

    def _on_search_entry_search_changed(self, search_entry):

        if not len(self._search_entry.get_text()) and not self._search_bar.get_focus_child():

            self._search_bar.set_search_mode(False)

        self._update_search_results()

    def _on_search_bar_search_mode_enabled_changed(self, search_bar, property):

        value = self._search_bar.get_search_mode()

        if self._reset_by_unfocus and self._application_window.get_focus() == self._toggle_button:

            self._reset_by_unfocus = False

        else:

            self._toggle_button.set_active(value)

        if not value and self._search_bar.get_focus_child():

            self._list_box.child_focus(Gtk.DirectionType.DOWN)

    def _on_search_entry_event_controller_focus_leave(self, controller):

        if self._search_bar.get_search_mode() and not len(self._search_entry.get_text()):

            self._reset_by_unfocus = True

            GLib.idle_add(self._search_bar.set_search_mode, False)

    def _on_search_entry_controller_key_pressed(self, controller, keyval, keycode, state):

        if keyval == Keyval.ESCAPE:

            self._search_bar.set_search_mode(False)

            return True

        elif keyval == Keyval.UP or keyval == Keyval.PAGEUP:

            self._toggle_button.grab_focus()

            if not len(self._search_entry.get_text()):

                self._toggle_button.set_active(False)

            return True

        elif keyval == Keyval.DOWN or keyval == Keyval.PAGEDOWN:

            if not len(self._search_entry.get_text()):

                self._search_bar.set_search_mode(False)

            else:

                self._list_box.child_focus(Gtk.DirectionType.DOWN)

            return True

        elif keyval == Keyval.TAB and self._active_row and not self._active_row.get_visible():

            self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)

            self._list_box.set_selection_mode(Gtk.SelectionMode.BROWSE)

    def _on_list_box_controller_key_pressed(self, controller, keyval, keycode, state):

        if keyval == Keyval.ESCAPE and self._search_bar.get_search_mode():

            self._search_bar.grab_focus()

            self._search_bar.set_search_mode(False)

            return True

        elif (

        (keyval == Keyval.UP or keyval == Keyval.PAGEUP)

        and self._list_box.get_focus_child() == self._list_box.get_first_child()

        ):

            if not self._search_bar.get_search_mode():

                self._search_bar.set_search_mode(True)

            self._search_entry.grab_focus()

            return True

    def _on_list_box_selected_rows_changed(self, listbox):

        if not self._ignore_selection:

            self._list_box.unselect_all()

            if self._active_row in self._names:

                self._list_box.select_row(self._active_row)

            else:

                self._list_box.select_row(None)

    def _on_list_box_row_activated(self, list_box, row):

        self._ignore_selection = True

        if not self._events.trigger("item-activated", self._names[row]):

            self._active_row = row

        self._list_box.select_row(self._active_row)

        self._ignore_selection = False

    def _do_list_box_sort(self, row_1, row_2):

        labels = [

            self._children[self._names[row_1]]["label"].get_text(),

            self._children[self._names[row_2]]["label"].get_text()

            ]

        if labels[0] == labels[1]:

            return 0

        else:

            if sorted(labels, key=str.lower)[0] == labels[0]:

                return -1

            else:

                return 1

    def _get_visible_children(self):

        children = []

        for child in list(reversed(self._children.values())):

            if child["widget"].get_visible():

                children.append(child["widget"])

        return children

    def _update_search_results(self):

        text = self._search_entry.get_text().lower()

        for name in self._children:

            for keyword in self._children[name]["keywords"]:

                if text in keyword:

                    self._children[name]["widget"].set_visible(True)

                    break

            else:

                self._children[name]["widget"].set_visible(False)

    def get_active_item(self):

        return self._active_row

    def set_active_item(self, name, activate=True):

        if name is None:

            self._list_box.unselect_all()

            self._active_row = None

        else:

            item = self._children[name]["widget"]

            if not item == self._active_row and activate:

                item.activate()

            else:

                self._list_box.select_row(item)

    def get_search_mode(self):

        return self._search_bar.get_search_mode()

    def set_search_mode(self, value):

        self._search_bar.set_search_mode(value)

    def get_search_bar(self):

        return self._search_bar

    def get_search_button(self):

        return self._toggle_button

    def get_search_entry(self):

        return self._search_entry

    def get_visible_items(self):

        items = []

        for child in self._children:

            if self._children[child]["widget"].get_visible():

                items.append(child)

        else:

            return items

    def list(self):

        return list(self._children)

    def clear(self):

        for name in self.list():

            self.remove(name)

    def update(self, name, text, icon, keywords, invalidate_sort=True):

        if name in self._children:

            image = self._children[name]["image"]

            label = self._children[name]["label"]

            try:

                self._icon_finder.set_image(image, icon, missing_ok=False)

            except IconNotFoundError:

                image.clear()

            label.set_text(text)

            self._children[name]["keywords"] = [keyword.lower() for keyword in keywords]

            if invalidate_sort:

                self._list_box.invalidate_sort()

            self._update_search_results()

        else:

            raise ItemNotFoundError(name)

    def add(self, name, text, icon=None, keywords=None):

        if not name in self._children:

            image = Gtk.Image()

            image.set_pixel_size(48)

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

            child = Gtk.ListBoxRow()

            child.set_child(box)

            self._names[child] = name

            self._children[name] = {}

            self._children[name]["widget"] = child

            self._children[name]["image"] = image

            self._children[name]["label"] = label

            if not isinstance(keywords, list):

                keywords = [text]

            self.update(name, text, icon, keywords, invalidate_sort=False)

            self._list_box.prepend(child)

            self._update_search_results()

        else:

            raise ItemAlreadyExistingError(name)

    def remove(self, name):

        if name in self._children:

            child = self._children[name]["widget"]

            self._list_box.remove(child)

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

        super().__init__(*args, **kwargs)

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

        super().__init__(*args, **kwargs)

        self._application_window = Adw.ApplicationWindow()

        self._project_dir = os.path.abspath(os.path.realpath(project_dir))

        self._app_name = os.path.basename(self._project_dir)

        self._config_dir = os.path.join(GLib.get_user_data_dir(), self._app_name)

        self._cache_dir = os.path.join(GLib.get_user_cache_dir(), self._app_name)

        self._flatpak_filesystem_prefix = os.path.join(os.path.sep, "run", "host")

        ###############################################################################################################

        if os.getenv("APP_RUNNING_AS_FLATPAK") == "true":

            home_var = self.get_flatpak_host_environment_variable("HOME")

            if home_var:

                self._flatpak_real_home = os.path.abspath(home_var)

            else:

                self._flatpak_real_home = os.path.join(os.path.sep, "home", os.getenv("USER"))

        else:

            self._flatpak_real_home = None

        ###############################################################################################################

        self._config_manager = basic.ConfigManager(

            os.path.join(self._project_dir, "default.json"),

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

        if os.getenv("APP_RUNNING_AS_FLATPAK") == "true":

            self._system_data_dirs = [

                os.path.join(GLib.get_user_data_dir(), "flatpak", "exports", "share"),

                os.path.join(os.path.sep, "var", "lib", "flatpak", "exports", "share"),

                os.path.join(os.path.sep, "var", "lib", "snapd", "desktop"),

                os.path.join(self._flatpak_filesystem_prefix, "usr", "local", "share"),

                os.path.join(self._flatpak_filesystem_prefix, "usr", "share")

                ]

            try:

                for path in self.get_flatpak_host_environment_variable("XDG_DATA_DIRS").split(":"):

                    if path.startswith("~"):

                        path = self._join_path_prefix(self._flatpak_real_home, path[1:])

                    if path.startswith(self._flatpak_real_home) and not path in self._system_data_dirs:

                        self._system_data_dirs.append(path)

                    path = self._join_path_prefix(self._flatpak_filesystem_prefix, path)

                    if not path in self._system_data_dirs:

                        self._system_data_dirs.append(path)

            except AttributeError as e:

                if self.get_flatpak_host_environment_variable("XDG_DATA_DIRS"):

                    raise e

            self._icon_search_dirs = [

                self._join_path_prefix(self._flatpak_filesystem_prefix, self._flatpak_real_home, ".local", "share", "icons"),

                self._join_path_prefix(self._flatpak_filesystem_prefix, self._flatpak_real_home, ".local", "share", "pixmaps"),

                self._join_path_prefix(self._flatpak_filesystem_prefix, self._flatpak_real_home, ".icons"),

                self._join_path_prefix(self._flatpak_filesystem_prefix, self._flatpak_real_home, ".pixmaps")

                ]

            for path in self._system_data_dirs:

                self._icon_search_dirs.append(os.path.join(path, "icons"))

                self._icon_search_dirs.append(os.path.join(path, "pixmaps"))

        else:

            self._system_data_dirs = [

                os.path.join(GLib.get_user_data_dir(), "flatpak", "exports", "share"),

                os.path.join(os.path.sep, "var", "lib", "flatpak", "exports", "share"),

                os.path.join(os.path.sep, "var", "lib", "snapd", "desktop"),

                os.path.join(os.path.sep, "usr", "local", "share"),

                os.path.join(os.path.sep, "usr", "share")

                ]

            try:

                for path in os.getenv("XDG_DATA_DIRS").split(":"):

                    if path.startswith("~"):

                        path = self._join_path_prefix(GLib.get_home_dir(), path[1:])

                    if not path in self._system_data_dirs:

                        self._system_data_dirs.append(path)

            except AttributeError as e:

                if os.getenv("XDG_DATA_DIRS"):

                    raise e

            self._icon_search_dirs = [

                os.path.join(GLib.get_user_data_dir(), "icons"),

                os.path.join(GLib.get_user_data_dir(), "pixmaps"),

                os.path.join(GLib.get_home_dir(), ".icons"),

                os.path.join(GLib.get_home_dir(), ".pixmaps")

                ]

            for path in self._system_data_dirs:

                self._icon_search_dirs.append(os.path.join(path, "icons"))

                self._icon_search_dirs.append(os.path.join(path, "pixmaps"))

        ###############################################################################################################

        self._icon_search_dirs.append(os.path.join(self.get_project_dir(), "icons"))

        self._icon_finder.add_search_paths(*self._icon_search_dirs)

        ###############################################################################################################

        self._command_dirs = []

        ###############################################################################################################

        if os.getenv("APP_RUNNING_AS_FLATPAK") == "true":

            self._command_lookup_cwd = self._flatpak_real_home

            try:

                for path in self.get_flatpak_host_environment_variable("PATH").split(":"):

                    if path.startswith("~"):

                        path = self._join_path_prefix(self._flatpak_real_home, path[1:])

                    if path.startswith(self._flatpak_real_home) and not path in self._command_dirs:

                        self._command_dirs.append(path)

                    path = self._join_path_prefix(self._flatpak_filesystem_prefix, path)

                    if not path in self._command_dirs:

                        self._command_dirs.append(path)

            except AttributeError as e:

                if self.get_flatpak_host_environment_variable("PATH"):

                    raise e

        else:

            self._command_lookup_cwd = GLib.get_home_dir()

            try:

                for path in os.getenv("PATH").split(":"):

                    if path.startswith("~"):

                        path = self._join_path_prefix(GLib.get_home_dir(), path[1:])

                    if not path in self._command_dirs:

                        self._command_dirs.append(path)

            except AttributeError as e:

                if os.getenv("PATH"):

                    raise e

        ###############################################################################################################

        self.connect("activate", self._on_activate)

        self.connect("shutdown", self._on_shutdown)

    def _on_activate(self, app):

        GLib.set_prgname(self._app_name)

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

    def get_cache_dir(self):

        return self._cache_dir

    def get_config_manager(self):

        return self._config_manager

    def get_locale_manager(self):

        return self._locale_manager

    def get_icon_finder(self):

        return self._icon_finder

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

    def get_flatpak_host_environment_variable(self, variable):

        printenv_commands = [

            ["flatpak-spawn", "--host", "printenv", variable],

            ["flatpak-spawn", "--host", "sh", "-c", f"echo ${variable}"]

            ]

        for command in printenv_commands:

            process = subprocess.Popen(command, stdout=subprocess.PIPE)

            stdout, stderr = process.communicate()

            if not process.returncode:

                decoded_stdout = stdout.decode().split("\n")[0]

                if len(decoded_stdout):

                    return decoded_stdout

    def get_command_exists(self, text, skip_empty_path=False, include_lookup_cwd=False):

        filtered_pieces = []

        escaped_pieces = text.strip().split("\ ")

        for escaped_piece in escaped_pieces:

            if not " " in escaped_piece:

                filtered_pieces.append(escaped_piece)

            else:

                filtered_pieces.append(escaped_piece.split(" ")[0])

                break

        command = "\ ".join(filtered_pieces)

        if os.path.sep in command:

            path = command.replace("\ ", " ")

            if command.startswith(os.path.sep):

                if os.getenv("APP_RUNNING_AS_FLATPAK") == "true" and not path.startswith(self._flatpak_real_home):

                    path = self._join_path_prefix(self._flatpak_filesystem_prefix, path)

            elif include_lookup_cwd:

                path = os.path.join(self._command_lookup_cwd, path)

            if os.access(path, os.X_OK) and os.path.isfile(path):

                return path

        elif skip_empty_path and not len(self._command_dirs):

            return True

        elif len(command):

            command_dirs = self._command_dirs

            if include_lookup_cwd:

                command_dirs.append(self._command_lookup_cwd)

            for command_dir in command_dirs:

                path = self._join_path_prefix(command_dir, command)

                if os.access(path, os.X_OK) and os.path.isfile(path):

                    return path

    def get_flatpak_real_home(self):

        return self._flatpak_real_home
