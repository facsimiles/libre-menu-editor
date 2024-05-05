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


import os, subprocess, threading, gi

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

        self._icon_names = []

        self._string_separator = ";"

        self._search_string = ""

        self._lower_string = ""

        self._can_set_active = False

        self._default_text = ""

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

        if not self._entry["widget"].get_text() == self._default_text:

            self.set_active(True)

    def _on_event_controller_focus_leave(self, controller):

        GLib.idle_add(self._after_event_controller_focus_leave)

    def _after_event_controller_focus_leave(self):

        if not self.get_parent().get_focus_child():

            self.set_active(False)

    def _on_event_controller_key_pressed(self, controller, keyval, keycode, state):

        if keyval == 65307:

            if self.get_active():

                self._entry["widget"].grab_focus()

            self._toggle_set_active()

    def _on_entry_activated(self, entry):

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

        self.set_default_text(self._list_store[position].name)

        self._entry["widget"].grab_focus()

        self.set_active(False)

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

        self._stop_search_thread()

        self._list_store.remove_all()

        self._search_thread = threading.Thread(target=self._search_thread_target)

        self._search_thread.start()

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

    def _search_thread_target(self):

        text = self._entry["widget"].get_text()

        names = self._get_names(text, exclude=[text])

        if len(names):

            self._name_slices = [names[i:i+self._slice_length] for i in range(0, len(names), self._slice_length)]

            self._slice_call_id = GLib.idle_add(self._add_next_slice)

            self._can_set_active = True

            if not text == self._default_text:

                GLib.idle_add(self.set_active, True)

            else:

                GLib.idle_add(self.set_active, False)

        else:

            self._can_set_active = False

            GLib.idle_add(self.set_active, False)

        self._search_thread = None

    def _add_next_slice(self):

        try:

            self._list_store.splice(len(self._list_store), 0, self._name_slices.pop(0))

        except IndexError:

            self._slice_call_id = None

            return GLib.SOURCE_REMOVE

        else:

            self._slice_call_id = GLib.idle_add(self._add_next_slice)

            return GLib.SOURCE_REMOVE

    def _get_names(self, text, exclude=[]):

        names = []

        for string in text.lower().split(self._string_separator):

            if len(string):

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

                                names.append(IconName(name))

                            break

                        else:

                            name = self._search_string[start_pos:end_pos]

                            if not name in exclude:

                                names.append(IconName(name))

                            start_pos = end_pos + len(self._string_separator)

                            if not len(self._search_string) > start_pos:

                                break

                else:

                    return []

        else:

            return names

    def get_search_entry(self):

        return self._entry["widget"]

    def set_search_entry(self, entry):

        try:

            self._entry["widget"].remove_controller(self._entry_event_controller_focus)

            self._entry["widget"].remove_controller(self._entry_event_controller_key)

            self._entry["widget"].disconnect(self._entry["entry-activated-event-id"])

            self._entry["widget"].disconnect(self._entry["changed-event-id"])

        except KeyError:

            pass

        entry.add_controller(self._entry_event_controller_focus)

        entry.add_controller(self._entry_event_controller_key)

        self._entry["entry-activated-event-id"] = entry.connect("entry-activated", self._on_entry_activated)

        self._entry["changed-event-id"] = entry.connect("changed", self._on_entry_changed)

        self._entry["widget"] = entry

    def get_default_text(self):

        return self._default_text

    def set_default_text(self, text):

        self._default_text = text

        if not text == self._entry["widget"].get_text():

            self._entry["widget"].set_text(text)

    def get_active(self):

        return self._revealer.get_reveal_child()

    def set_active(self, value, check=True):

        if check and not self._can_set_active:

            value = False

        elif not self.get_parent().get_focus_child():

            value = False

        self._revealer.set_reveal_child(value)


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

        self._error_image = self._icon_finder.get_image("action-unavailable-symbolic")

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


class CommandChooserRow(FileChooserRow):

    def __init__(self, app, *args, **kwargs):

        super().__init__(app, *args, **kwargs)

        self.add_css_class("error")

    def _on_file_chooser_dialog_response(self, dialog, response):

        self._file_chooser_dialog.hide()

        if response == Gtk.ResponseType.ACCEPT:

            path = self._file_chooser_dialog.get_file().get_path().replace(" ", "\ ")

            self.set_text(path)

    def _on_changed(self, editable):

        text = editable.get_text()

        self._events.trigger("text-changed", self, text)

        if not len(text.replace(" ", "")):

            self.add_css_class("error")

        else:

            self.remove_css_class("error")


class IconChooserRow(FileChooserRow):

    def __init__(self, app, *args, **kwargs):

        super().__init__(app, *args, **kwargs)

        self._icon_image = Gtk.Image()

    def _on_changed(self, editable):

        text = editable.get_text()

        self._events.trigger("text-changed", self, text)

        if len(text):

            try:

                self._icon_finder.set_image(self._icon_image, text, missing_ok=False)

            except IconNotFoundError:

                self.add_css_class("error")

                self._icon_image.set_from_file(None)

            else:

                self.remove_css_class("error")

        else:

            self.remove_css_class("error")

            self._icon_image.set_from_file(None)

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

        self._list_box.add_css_class("navigation-sidebar")

        self._list_box.set_selection_mode(Gtk.SelectionMode.BROWSE)

        self._list_box.connect("selected-rows-changed", self._on_list_box_selected_rows_changed)

        self._list_box.add_controller(self._list_box_event_controller_key)

        self._list_box.connect("row-activated", self._on_list_box_child_activated)

        self._scrolled_window = Gtk.ScrolledWindow()

        self._scrolled_window.set_vexpand(True)

        self._scrolled_window.set_kinetic_scrolling(True)

        self._scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._scrolled_window.set_child(self._list_box)

        self.set_orientation(Gtk.Orientation.VERTICAL)

        self.append(self._search_bar)

        self.append(self._scrolled_window)

    def _on_list_box_selected_rows_changed(self, listbox):

        self._list_box.unselect_all()

        self._list_box.select_row(self._active_row)

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

    def _on_list_box_child_activated(self, list_box, child):

        self._active_row = child

        self._list_box.select_row(child)

        self._events.trigger("item-activated", self._names[child])

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

    def set_active_item(self, name):

        item = self._children[name]["widget"]

        if not item == self._active_row:

            item.activate()

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

    def update(self, name, text, icon, keywords):

        if name in self._children:

            image = self._children[name]["image"]

            label = self._children[name]["label"]

            try:

                self._icon_finder.set_image(image, icon, missing_ok=False)

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

            self._list_box.prepend(child)

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

        self._common_user_data_dirs = [

            os.path.join(os.path.sep, "home", os.getenv("USER"), ".local", "share")

            ]

        ###############################################################################################################

        if os.getenv("APP_RUNNING_AS_FLATPAK") == "true":

            self._system_data_dirs = [

                os.path.join(GLib.get_user_data_dir(), "flatpak", "exports", "share"),

                os.path.join(os.path.sep, "var", "lib", "flatpak", "exports", "share"),

                os.path.join(os.path.sep, "var", "lib", "snapd", "desktop"),

                os.path.join(self._flatpak_filesystem_prefix, "usr", "local", "share"),

                os.path.join(self._flatpak_filesystem_prefix, "usr", "share")

                ]

            self._icon_search_dirs = [

                os.path.join(self._flatpak_filesystem_prefix, "home", os.getenv("USER"), ".icons"),

                os.path.join(self._flatpak_filesystem_prefix, "home", os.getenv("USER"), ".pixmaps")

                ]

            for path in self._common_user_data_dirs:

                self._icon_search_dirs.append(self._join_path_prefix(

                    self._flatpak_filesystem_prefix,

                    os.path.join(path, "icons")

                    ))

                self._icon_search_dirs.append(self._join_path_prefix(

                    self._flatpak_filesystem_prefix,

                    os.path.join(path, "pixmaps")

                    ))

            for path in self._system_data_dirs:

                self._icon_search_dirs.append(os.path.join(path, "icons"))

                self._icon_search_dirs.append(os.path.join(path, "pixmaps"))

            self._icon_search_dirs.append(os.path.join(self.get_project_dir(), "icons"))

            self._icon_finder.add_search_paths(*self._icon_search_dirs)

        else:

            self._system_data_dirs = [

                os.path.join(GLib.get_user_data_dir(), "flatpak", "exports", "share"),

                os.path.join(os.path.sep, "var", "lib", "flatpak", "exports", "share"),

                os.path.join(os.path.sep, "var", "lib", "snapd", "desktop"),

                os.path.join(os.path.sep, "usr", "local", "share"),

                os.path.join(os.path.sep, "usr", "share")

                ]

            if not os.getenv("XDG_DATA_DIRS") is None:

                for path in os.getenv("XDG_DATA_DIRS").split(":"):

                    if not path in self._system_data_dirs:

                        self._system_data_dirs.append(path)

            self._icon_search_dirs = [

                os.path.join(GLib.get_user_data_dir(), "icons"),

                os.path.join(GLib.get_user_data_dir(), "pixmaps"),

                os.path.join(GLib.get_home_dir(), ".icons"),

                os.path.join(GLib.get_home_dir(), ".pixmaps")

                ]

            for path in self._system_data_dirs:

                self._icon_search_dirs.append(os.path.join(path, "icons"))

                self._icon_search_dirs.append(os.path.join(path, "pixmaps"))

            self._icon_search_dirs.append(os.path.join(self.get_project_dir(), "icons"))

            self._icon_finder.add_search_paths(*self._icon_search_dirs)

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
