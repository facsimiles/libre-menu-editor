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


import os, sys, string, random, shutil, subprocess, gi

gi.require_version("Adw", "1")

gi.require_version("Gtk", "4.0")

gi.require_version("GLib", "2.0")

gi.require_version("Pango", "1.0")

from gi.repository import Adw

from gi.repository import Gtk

from gi.repository import GLib

from gi.repository import Pango

from configparser import ConfigParser

from modules import gui, basic


class DesktopParser():

    def __init__(self, load_path, save_path):

        self._config_parser = ConfigParser(interpolation=None, strict=False)

        self._config_parser.optionxform = str

        self._system_locale_names = [

            os.getenv("LANG").split(".")[0].split("_")[0],

            os.getenv("LANG").split(".")[0],

            os.getenv("LANG")

            ]

        self._config_parser.read(load_path)

        self._load_path = load_path

        self._save_path = save_path

    def _get_action_from_section(self, section):

        return section[len("Desktop Action "):]

    def _get_section_from_action(self, action):

        return "Desktop Action %s" % action

    def _get_str(self, key, section="Desktop Entry", localized=False, value=""):

        if self._config_parser.has_section(section):

            if localized:

               for locale in self._system_locale_names:

                    localized_key = "%s[%s]" % (key, locale)

                    if self._config_parser.has_option(section, localized_key):

                        return self._config_parser.get(section, localized_key)

            if self._config_parser.has_option(section, key):

                return self._config_parser.get(section, key)

        return value

    def _get_bool(self, key, section="Desktop Entry"):

        if self._config_parser.has_section(section):

            if self._config_parser.has_option(section, key):

                try:

                    return self._config_parser.getboolean(section, key)

                except ValueError as error:

                    if self._debug_mode_enabled:

                        raise error

                    else:

                        print("error 1:", error)

                        return False

            else:

                return False

        else:

            return False

    def _set(self, key, value, section="Desktop Entry", localized=False):

        if isinstance(value, bool):

            if value:

                value = "true"

            else:

                value = "false"

        self._config_parser.set(section, key, value)

        if localized:

            for locale in self._system_locale_names:

                self._config_parser.set(section, "%s[%s]" % (key, locale), value)

    def get_action_name(self, action):

        return self.get_name(section=self._get_section_from_action(action))

    def set_action_name(self, action, name):

        self.set_name(name, section=self._get_section_from_action(action))

    def get_action_command(self, action):

        return self.get_command(section=self._get_section_from_action(action))

    def set_action_command(self, action, command):

        self.set_command(command, section=self._get_section_from_action(action))

    def get_name(self, section="Desktop Entry"):

        return self._get_str("Name", section=section, localized=True)

    def set_name(self, name, section="Desktop Entry"):

        self._set("Name", name, section=section, localized=True)

    def get_comment(self, section="Desktop Entry"):

        return self._get_str("Comment", section=section, localized=True)

    def set_comment(self, comment, section="Desktop Entry"):

        self._set("Comment", comment, section=section, localized=True)

    def get_icon(self, section="Desktop Entry"):

        return self._get_str("Icon", section=section)

    def set_icon(self, icon, section="Desktop Entry"):

        self._set("Icon", icon, section=section)

    def get_command(self, section="Desktop Entry"):

        return self._get_str("Exec", section=section)

    def set_command(self, command, section="Desktop Entry"):

        self._set("Exec", command, section=section)

    def get_hidden(self, section="Desktop Entry"):

        return self._get_bool("NoDisplay", section=section)

    def set_hidden(self, value, section="Desktop Entry"):

        self._set("NoDisplay", value, section=section)

    def get_disabled(self, section="Desktop Entry"):

        return self._get_bool("Hidden", section=section)

    def set_disabled(self, value, section="Desktop Entry"):

        self._set("Hidden", value, section=section)

    def get_load_path(self):

        return self._load_path

    def get_save_path(self):

        return self._save_path

    def get_search_data(self):

        data = []

        data.append(self.get_name())

        data.append(self.get_icon())

        data.append(self.get_command())

        data.append(self._get_str("MimeType"))

        data.append(self._get_str("Keywords", localized=True))

        data.append(os.path.basename(self._load_path))

        return list(filter(None, data))

    def get_actions(self):

        actions = []

        for section in self._config_parser.sections():

            if section.startswith("Desktop Action "):

                actions.append(self._get_action_from_section(section))

        return actions

    def add_action(self, action):

        section = self._get_section_from_action(action)

        if not self._config_parser.has_section(section):

            self._config_parser.add_section(section)

    def remove_action(self, action):

        self._config_parser.remove_section(self._get_section_from_action(action))

    def save(self):

        self._set("Actions", ";".join(self.get_actions()))

        if os.path.exists(self._save_path):

            os.remove(self._save_path)

        os.makedirs(os.path.dirname(self._save_path), exist_ok=True)

        with open(self._save_path, "w") as file:

            self._config_parser.write(file, space_around_delimiters=False)


class DesktopActionGroup(Adw.PreferencesGroup):

    def __init__(self, app):

        Adw.PreferencesGroup.__init__(self)

        self._application_window = app.get_application_window()

        self._locale_manager = app.get_locale_manager()

        self._events = basic.EventManager()

        self._events.add("data-changed", object, tuple)

        self._events.add("row-deleted", object)

        self._children = []

        self._delete_mode_enabled  = False

        self._delete_label_placeholder_text = self._locale_manager.get("UNNAMED_ACTION_PLACEHOLDER_TEXT")

        self._entry_row = gui.EntryRow(app)

        self._entry_row.set_title(self._locale_manager.get("NAME_ENTRY_ROW_TITLE"))

        self._entry_row.hook("text-changed", self._on_child_row_text_changed)

        self._command_chooser_row = gui.CommandChooserRow(app)

        self._command_chooser_row.set_title(self._locale_manager.get("COMMAND_CHOOSER_ROW_TITLE"))

        self._command_chooser_row.hook("text-changed", self._on_child_row_text_changed)

        self._delete_label = gui.SuffixLabel()

        self._delete_row = Adw.ActionRow()

        self._delete_row.set_title_lines(1)

        self._delete_row.set_activatable(True)

        self._delete_row.connect("activated", self._on_delete_row_activated)

        self._delete_row.add_suffix(self._delete_label)

        self.add(self._entry_row)

        self.add(self._command_chooser_row)

    def _on_delete_row_activated(self, action_row):

        self._events.trigger("row-deleted", self)

    def _on_child_row_text_changed(self, event, child, text):

        data = self._entry_row.get_text(), self._command_chooser_row.get_text()

        self._events.trigger("data-changed", self, data)

    def get_name(self):

        return self._entry_row.get_text()

    def set_name(self, name):

        self._entry_row.set_text(name)

    def get_command(self):

        return self._command_chooser_row.get_text()

    def set_command(self, command):

        self._command_chooser_row.set_text(command)

    def get_edit_mode_enabled(self):

        values = self._entry_row.get_edit_mode_enabled(), self._command_chooser_row.get_edit_mode_enabled()

        return True in values

    def set_edit_mode_enabled(self, value):

        self._entry_row.set_edit_mode_enabled(value)

        self._command_chooser_row.set_edit_mode_enabled(value)

    def get_delete_mode_enabled(self):

        return self._delete_mode_enabled

    def set_delete_mode_enabled(self, value):

        if value and not self._delete_mode_enabled:

            self.remove(self._entry_row)

            self.remove(self._command_chooser_row)

            name_text = self._entry_row.get_text()

            if not len(name_text):

                name_text = self._delete_label_placeholder_text

            self._delete_row.set_title(name_text)

            self._delete_label.set_text(self._command_chooser_row.get_text())

            self.add(self._delete_row)

        elif not value and self._delete_mode_enabled:

            self.remove(self._delete_row)

            self.add(self._entry_row)

            self.add(self._command_chooser_row)

        self._delete_mode_enabled = value

    def add(self, child):

        self._children.append(child)

        Adw.PreferencesGroup.add(self, child)

    def remove(self, child):

        self._children.remove(child)

        Adw.PreferencesGroup.remove(self, child)

    def hook(self, event, callback, *args):

        self._events.hook(event, callback, *args)

    def release(self, id):

        self._events.release(id)

    def grab_focus(self):

        if not self._delete_mode_enabled:

            self._entry_row.grab_focus()

        else:

            self._delete_row.grab_focus()

    def reset(self):

        for hook in list(self._events.get_hooks()):

            self._events.release(hook)

        self.set_name("")

        self.set_command("")

        self.set_sensitive(True)

        self.set_delete_mode_enabled(False)

        self.set_header_suffix(None)

        self.set_title("")


class SettingsPage(Gtk.Box):

    def __init__(self, app, *args, **kwargs):

        Gtk.Box.__init__(self, *args, **kwargs)

        self._locale_manager = app.get_locale_manager()

        self._icon_finder = app.get_icon_finder()

        self._application = app

        self._current_name = None

        self._current_parser = None

        self._delete_mode_enabled = False

        self._placeholder_action_visible = True

        self._desktop_action_groups_cache = []

        self._current_desktop_actions = []

        self._current_desktop_action_groups = {}

        self._input_children_changes = {}

        ###############################################################################################################

        self._save_button = Gtk.Button()

        self._save_button.add_css_class("suggested-action")

        self._save_button.set_label(self._locale_manager.get("SAVE_BUTTON_LABEL"))

        self._reload_button = Gtk.Button()

        self._reload_button.set_label(self._locale_manager.get("RELOAD_BUTTON_LABEL"))

        self._enabled_switch = Gtk.Switch()

        self._enabled_switch.connect("notify::active", self._on_enabled_switch_active_changed)

        ###############################################################################################################

        self._top_event_controller_key = Gtk.EventControllerKey()

        self._top_event_controller_key.connect("key-pressed", self._on_top_controller_key_pressed)

        self._icon_chooser_row = gui.IconChooserRow(self._application)

        self._icon_chooser_row.set_title(self._locale_manager.get("ICON_CHOOSER_ROW_TITLE"))

        self._icon_chooser_row.set_dialog_title(self._locale_manager.get("ICON_CHOOSER_ROW_DIALOG_TITLE"))

        self._icon_chooser_row.add_controller(self._top_event_controller_key)

        self._icon_chooser_row.hook("text-changed", self._on_input_child_data_changed)

        self._icon_preferences_group = Adw.PreferencesGroup()

        self._icon_preferences_group.set_title(self._locale_manager.get("DESCRIPTION_GROUP_TITLE"))

        self._icon_preferences_group.add(self._icon_chooser_row)

        ###############################################################################################################

        self._name_entry_row = gui.EntryRow(app)

        self._name_entry_row.set_title(self._locale_manager.get("NAME_ENTRY_ROW_TITLE"))

        self._name_entry_row.hook("text-changed", self._on_input_child_data_changed)

        self._comment_entry_row = gui.EntryRow(app)

        self._comment_entry_row.set_title(self._locale_manager.get("COMMENT_ENTRY_ROW_TITLE"))

        self._comment_entry_row.hook("text-changed", self._on_input_child_data_changed)

        self._description_preferences_group = Adw.PreferencesGroup()

        self._description_preferences_group.add(self._name_entry_row)

        self._description_preferences_group.add(self._comment_entry_row)

        ###############################################################################################################

        self._command_chooser_row = gui.CommandChooserRow(self._application)

        self._command_chooser_row.set_title(self._locale_manager.get("COMMAND_CHOOSER_ROW_TITLE"))

        self._command_chooser_row.set_dialog_title(self._locale_manager.get("COMMAND_CHOOSER_ROW_DIALOG_TITLE"))

        self._command_chooser_row.hook("text-changed", self._on_input_child_data_changed)

        self._command_preferences_group = Adw.PreferencesGroup()

        self._command_preferences_group.add(self._command_chooser_row)

        ###############################################################################################################

        self._primary_event_controller_key = Gtk.EventControllerKey()

        self._primary_event_controller_key.connect("key-pressed", self._on_primary_controller_key_pressed)

        self._primary_action_create_button = Gtk.Button()

        self._primary_action_create_button.set_icon_name(self._icon_finder.get_name("list-add-symbolic"))

        self._primary_action_create_button.add_css_class("flat")

        self._primary_action_create_button.connect("clicked", self._on_action_create_button_clicked)

        self._primary_action_delete_button = Gtk.Button()

        self._primary_action_delete_button.set_icon_name(self._icon_finder.get_name("list-remove-symbolic"))

        self._primary_action_delete_button.add_css_class("flat")

        self._primary_action_delete_button.connect("clicked", self._on_action_delete_button_clicked)

        self._primary_header_suffix_box = Gtk.Box()

        self._primary_header_suffix_box.set_spacing(gui.Spacing.DEFAULT)

        self._primary_header_suffix_box.append(self._primary_action_create_button)

        self._primary_header_suffix_box.append(self._primary_action_delete_button)

        self._primary_header_suffix_box.add_controller(self._primary_event_controller_key)

        ###############################################################################################################

        self._placeholder_event_controller_key = Gtk.EventControllerKey()

        self._placeholder_event_controller_key.connect("key-pressed", self._on_placeholder_controller_key_pressed)

        self._placeholder_action_create_button = Gtk.Button()

        self._placeholder_action_create_button.set_icon_name(self._icon_finder.get_name("list-add-symbolic"))

        self._placeholder_action_create_button.add_css_class("flat")

        self._placeholder_action_create_button.connect("clicked", self._on_action_create_button_clicked)

        self._placeholder_action_create_button.add_controller(self._placeholder_event_controller_key)

        self._placeholder_action_group = Adw.PreferencesGroup()

        self._placeholder_action_group.set_title(self._locale_manager.get("ACTIONS_GROUP_TITLE"))

        self._placeholder_action_group.set_header_suffix(self._placeholder_action_create_button)

        ###############################################################################################################

        self._display_switch_row = gui.SwitchRow()

        self._display_switch_row.set_title(self._locale_manager.get("DISPLAY_SWITCH_ROW_TITLE"))

        self._display_switch_row.hook("value-changed", self._on_input_child_data_changed)

        self._display_preferences_group = Adw.PreferencesGroup()

        self._display_preferences_group.set_title(self._locale_manager.get("DISPLAY_GROUP_TITLE"))

        self._display_preferences_group.add(self._display_switch_row)

        ###############################################################################################################

        self._info_bar_event_controller_key = Gtk.EventControllerKey()

        self._info_bar_event_controller_key.connect("key-pressed", self._on_info_bar_controller_key_pressed)

        self._info_bar_label = Gtk.Label()

        self._info_bar_label.set_ellipsize(Pango.EllipsizeMode.END)

        self._info_bar_label.set_margin_start(gui.Margin.LARGER)

        self._info_bar_label.set_text(self._locale_manager.get("INFO_BAR_LABEL_TEXT"))

        self._info_bar_cancel_button = Gtk.Button()

        self._info_bar_cancel_button.set_margin_top(gui.Margin.LARGE)

        self._info_bar_cancel_button.set_margin_bottom(gui.Margin.LARGE)

        self._info_bar_cancel_button.set_margin_start(gui.Margin.LARGEST)

        self._info_bar_cancel_button.set_margin_end(gui.Margin.LARGER)

        self._info_bar_cancel_button.set_label(self._locale_manager.get("INFO_BAR_CANCEL_BUTTON_LABEL"))

        self._info_bar = Gtk.InfoBar()

        self._info_bar.set_revealed(False)

        self._info_bar.connect("response", self._on_info_bar_response)

        self._info_bar.add_controller(self._info_bar_event_controller_key)

        self._info_bar.add_child(self._info_bar_label)

        self._info_bar.add_action_widget(self._info_bar_cancel_button, 1)

        ###############################################################################################################

        self._page_event_controller_key = Gtk.EventControllerKey()

        self._page_event_controller_key.connect("key-pressed", self._on_page_controller_key_pressed)

        self._preferences_page = Adw.PreferencesPage()

        self._preferences_page.add_controller(self._page_event_controller_key)

        self._preferences_page.add(self._icon_preferences_group)

        self._preferences_page.add(self._description_preferences_group)

        self._preferences_page.add(self._command_preferences_group)

        self._preferences_page.add(self._placeholder_action_group)

        self._preferences_page.add(self._display_preferences_group)

        self.set_orientation(Gtk.Orientation.VERTICAL)

        self.connect("unmap", self._on_unmap)

        self.append(self._info_bar)

        self.append(self._preferences_page)

        self._update_input_children_sensitive(False)

        self._update_action_children_sensitive(False)

    def _on_unmap(self, widget):

        self._enabled_switch.set_active(False)

        self._update_action_children_sensitive(False)

    def _on_page_controller_key_pressed(self, controller, keyval, keycode, state):

        if keyval == gui.Keyval.ESCAPE:

            if self._delete_mode_enabled:

                self.set_delete_mode_enabled(False)

                return True

    def _on_info_bar_response(self, info_bar, response):

        self.set_delete_mode_enabled(False)

    def _on_enabled_switch_active_changed(self, switch, property):

        self._update_input_children_sensitive(self._enabled_switch.get_active())

        self._on_input_child_data_changed("value-changed", switch, switch.get_active())

    def _on_action_create_button_clicked(self, button):

        while True:

            action = ''.join(random.choices(string.digits, k=6))

            if not action in self._current_desktop_actions:

                self._add_desktop_action(action, set_focus=True)

                break

    def _on_action_delete_button_clicked(self, button):

        self.set_delete_mode_enabled(True)

    def _on_info_bar_controller_key_pressed(self, controller, keyval, keycode, state):

        if keyval == gui.Keyval.DOWN or keyval == gui.Keyval.PAGEDOWN:

            self._current_desktop_action_groups[self._current_desktop_actions[0]].grab_focus()

            return True

        elif keyval == gui.Keyval.ESCAPE:

            self.set_delete_mode_enabled(False)

    def _on_top_controller_key_pressed(self, controller, keyval, keycode, state):

        if keyval == gui.Keyval.UP or keyval == gui.Keyval.PAGEUP:

            if self._icon_chooser_row.has_focus():

                self._enabled_switch.grab_focus()

                return True

    def _on_primary_controller_key_pressed(self, controller, keyval, keycode, state):

        if keyval == gui.Keyval.TAB or keyval == gui.Keyval.DOWN or keyval == gui.Keyval.PAGEDOWN:

            if self._primary_action_create_button.has_focus():

                self._primary_action_delete_button.grab_focus()

                return True

            else:

                self._current_desktop_action_groups[self._current_desktop_actions[0]].grab_focus()

                return True

        elif keyval == gui.Keyval.UP or keyval == gui.Keyval.PAGEUP:

            if self._primary_action_delete_button.has_focus():

                self._primary_action_create_button.grab_focus()

                return True

            else:

                self._command_chooser_row.get_chooser_button().grab_focus()

                return True

    def _on_placeholder_controller_key_pressed(self, controller, keyval, keycode, state):

        if keyval == gui.Keyval.TAB or keyval == gui.Keyval.DOWN or keyval == gui.Keyval.PAGEDOWN:

            self._display_switch_row.grab_focus()

            return True

        elif keyval == gui.Keyval.UP or keyval == gui.Keyval.PAGEUP:

            self._command_chooser_row.get_chooser_button().grab_focus()

            return True

    def _on_desktop_action_group_row_deleted(self, event, desktop_action_group):

        index = list(self._current_desktop_action_groups.values()).index(desktop_action_group)

        action = self._current_desktop_actions[index]

        self._remove_desktop_action(action, set_focus=True)

    def _on_input_child_data_changed(self, event, child, data):

        if not isinstance(child, DesktopActionGroup):

            if child == self._icon_chooser_row:

                self._input_children_changes[child] = data == self._current_parser.get_icon()

            elif child == self._name_entry_row:

                self._input_children_changes[child] = data == self._current_parser.get_name()

            elif child == self._comment_entry_row:

                self._input_children_changes[child] = data == self._current_parser.get_comment()

            elif child == self._command_chooser_row:

                self._input_children_changes[child] = data == self._current_parser.get_command()

            elif child == self._display_switch_row:

                self._input_children_changes[child] = not data == self._current_parser.get_hidden()

            elif child == self._enabled_switch:

                self._input_children_changes[child] = not data == self._current_parser.get_disabled()

        self._update_action_children_sensitive()

    def _get_desktop_action_groups_changed(self):

        try:

            parser_actions = self._current_parser.get_actions()

        except AttributeError:

            return False

        if not self._current_desktop_actions == parser_actions:

            parser_actions_count = len(parser_actions)

            if len(self._current_desktop_actions) > parser_actions_count:

                for n, current_action in enumerate(self._current_desktop_actions[:parser_actions_count]):

                    current_name = self._current_desktop_action_groups[current_action].get_name()

                    parser_name = self._current_parser.get_action_name(parser_actions[n])

                    if not current_name == parser_name:

                        return True

                    current_command = self._current_desktop_action_groups[current_action].get_command()

                    parser_command = self._current_parser.get_action_command(parser_actions[n])

                    if not current_command == parser_command:

                        return True

                else:

                    for action in self._current_desktop_actions[parser_actions_count:]:

                        desktop_action_group = self._current_desktop_action_groups[action]

                        if len(desktop_action_group.get_name()) or len(desktop_action_group.get_command()):

                            return True

            else:

                return True

        else:

            for action in self._current_desktop_actions:

                name = self._current_desktop_action_groups[action].get_name()

                if not name == self._current_parser.get_action_name(action):

                    return True

                command = self._current_desktop_action_groups[action].get_command()

                if not command == self._current_parser.get_action_command(action):

                    return True

    def _show_placeholder_desktop_action(self):

        if not self._placeholder_action_visible:

            self._preferences_page.add(self._placeholder_action_group)

            self._placeholder_action_visible = True

    def _hide_placeholder_desktop_action(self):

        if self._placeholder_action_visible:

            self._preferences_page.remove(self._placeholder_action_group)

            self._placeholder_action_visible = False

    def _create_new_desktop_action_group(self):

        try:

            desktop_action_group = self._desktop_action_groups_cache.pop(0)

        except IndexError:

            desktop_action_group = DesktopActionGroup(self._application)

        finally:

            desktop_action_group.hook("row-deleted", self._on_desktop_action_group_row_deleted)

            desktop_action_group.hook("data-changed", self._on_input_child_data_changed)

            return desktop_action_group

    def _add_desktop_action(self, action, set_focus=False):

        desktop_action_group = self._create_new_desktop_action_group()

        if action in self._current_parser.get_actions():

            desktop_action_group.set_name(self._current_parser.get_action_name(action))

            desktop_action_group.set_command(self._current_parser.get_action_command(action))

        self._current_desktop_action_groups[action] = desktop_action_group

        self._current_desktop_actions.append(action)

        self._preferences_page.add(desktop_action_group)

        if set_focus:

            GLib.idle_add(desktop_action_group.grab_focus)

        self._update_top_desktop_action_group_header()

        self._hide_placeholder_desktop_action()

        self._update_bottom_preferences_group_position()

        self._update_action_children_sensitive()

    def _remove_desktop_action(self, action, set_focus=False):

        index = self._current_desktop_actions.index(action)

        desktop_action_group = self._current_desktop_action_groups[action]

        del self._current_desktop_action_groups[action]

        self._current_desktop_actions.remove(action)

        if not len(self._current_desktop_actions):

            self._show_placeholder_desktop_action()

            self.set_delete_mode_enabled(False)

        if set_focus:

            if not len(self._current_desktop_actions):

                self._placeholder_action_create_button.grab_focus()

            elif index < len(self._current_desktop_actions):

                self._current_desktop_action_groups[self._current_desktop_actions[index]].grab_focus()

            else:

                self._current_desktop_action_groups[self._current_desktop_actions[-1]].grab_focus()

        self._preferences_page.remove(desktop_action_group)

        desktop_action_group.reset()

        self._desktop_action_groups_cache.append(desktop_action_group)

        self._update_top_desktop_action_group_header()

        self._update_bottom_preferences_group_position()

        self._update_action_children_sensitive()

    def _update_top_desktop_action_group_header(self):

        if len(self._current_desktop_actions):

            desktop_action_group = self._current_desktop_action_groups[self._current_desktop_actions[0]]

            if desktop_action_group.get_header_suffix() == None:

                desktop_action_group.set_title(self._locale_manager.get("ACTIONS_GROUP_TITLE"))

                desktop_action_group.set_header_suffix(self._primary_header_suffix_box)

    def _update_bottom_preferences_group_position(self):

        self._preferences_page.remove(self._display_preferences_group)

        self._preferences_page.add(self._display_preferences_group)

    def _update_input_children_sensitive(self, value=True):

        self._enabled_switch.set_sensitive(self._delete_mode_enabled == False)

        self._enabled_switch.set_active(value)

        for action in self._current_desktop_actions:

            self._current_desktop_action_groups[action].set_sensitive(value)

        if value and self._delete_mode_enabled:

            value = False

        self._primary_header_suffix_box.set_sensitive(value)

        self._icon_preferences_group.set_sensitive(value)

        self._description_preferences_group.set_sensitive(value)

        self._command_preferences_group.set_sensitive(value)

        self._placeholder_action_group.set_sensitive(value)

        self._display_preferences_group.set_sensitive(value)

    def _update_action_children_sensitive(self, value=True):

        if value and not self.get_input_children_changed():

            value = False

        self._save_button.set_sensitive(value)

        self._reload_button.set_sensitive(value)

    def _reset_input_children_modes(self):

        self.set_delete_mode_enabled(False)

        for desktop_action_group in self._current_desktop_action_groups.values():

            desktop_action_group.set_edit_mode_enabled(False)

        self._icon_chooser_row.set_edit_mode_enabled(False)

        self._name_entry_row.set_edit_mode_enabled(False)

        self._comment_entry_row.set_edit_mode_enabled(False)

        self._command_chooser_row.set_edit_mode_enabled(False)

    def get_delete_mode_enabled(self):

        return self._delete_mode_enabled

    def set_delete_mode_enabled(self, value):

        if value and not self._delete_mode_enabled:

            self._info_bar.set_revealed(True)

            for action in self._current_desktop_actions:

                desktop_action_group = self._current_desktop_action_groups[action]

                desktop_action_group.set_delete_mode_enabled(True)

            self._delete_mode_enabled = value

            self._update_input_children_sensitive()

            self.grab_focus()

        elif not value and self._delete_mode_enabled:

            self._info_bar.set_revealed(False)

            for action in self._current_desktop_actions:

                desktop_action_group = self._current_desktop_action_groups[action]

                desktop_action_group.set_delete_mode_enabled(False)

            self._delete_mode_enabled = value

            self._update_input_children_sensitive()

            self.grab_focus()

    def load_desktop_starter(self, name, parser):

        self._current_name = name

        self._current_parser = parser

        self._input_children_changes.clear()

        self._reset_input_children_modes()

        for action in list(self._current_desktop_actions):

            self._remove_desktop_action(action)

        for action in self._current_parser.get_actions():

            self._add_desktop_action(action)

        self._icon_chooser_row.set_text(self._current_parser.get_icon())

        self._name_entry_row.set_text(self._current_parser.get_name())

        self._comment_entry_row.set_text(self._current_parser.get_comment())

        self._command_chooser_row.set_text(self._current_parser.get_command())

        self._display_switch_row.set_active(self._current_parser.get_hidden() == False)

        self._update_input_children_sensitive(self._current_parser.get_disabled() == False)

    def save_desktop_starter(self):

        for action in self._current_parser.get_actions():

            if not action in self._current_desktop_actions:

                self._current_parser.remove_action(action)

        for action in list(self._current_desktop_actions):

            desktop_action_group = self._current_desktop_action_groups[action]

            if not len(desktop_action_group.get_name()) and not len(desktop_action_group.get_command()):

                if action in self._current_parser.get_actions():

                    self._current_parser.remove_action(action)

                self._remove_desktop_action(action)

            else:

                if not action in self._current_parser.get_actions():

                    self._current_parser.add_action(action)

                self._current_parser.set_action_name(action, desktop_action_group.get_name())

                self._current_parser.set_action_command(action, desktop_action_group.get_command())

        self._current_parser.set_icon(self._icon_chooser_row.get_text())

        self._current_parser.set_name(self._name_entry_row.get_text())

        self._current_parser.set_comment(self._comment_entry_row.get_text())

        self._current_parser.set_command(self._command_chooser_row.get_text())

        self._current_parser.set_hidden(self._display_switch_row.get_active() == False)

        self._current_parser.set_disabled(self._enabled_switch.get_active() == False)

        self._current_parser.save()

        self._input_children_changes.clear()

        self._reset_input_children_modes()

        self._update_action_children_sensitive(False)

    def get_input_children_changed(self):

        if False in self._input_children_changes.values():

            return True

        else:

            return self._get_desktop_action_groups_changed()

    def get_save_button(self):

        return self._save_button

    def get_reload_button(self):

        return self._reload_button

    def get_enabled_switch(self):

        return self._enabled_switch

    def hook(self, event, callback):

        return self._events.hook(event, callback)

    def release(self, id):

        self._events.release(id)

    def grab_focus(self):

        if self._delete_mode_enabled:

            self._info_bar_cancel_button.grab_focus()

        elif self._icon_preferences_group.get_sensitive():

            self._icon_chooser_row.grab_focus()

        else:

            self._enabled_switch.grab_focus()


class GreeterWindow(Adw.Window):

    def __init__(self, app, *args, **kwargs):

        Adw.Window.__init__(self, *args, **kwargs)

        self._icon_finder = app.get_icon_finder()

        self._application_window = app.get_application_window()

        self._locale_manager = app.get_locale_manager()

        self._events = basic.EventManager()

        self._events.add("confirmed", object)

        self._head_label_text = self._locale_manager.get("GREETER_WINDOW_HEAD")

        self._head_label = Gtk.Label()

        self._head_label.set_markup("<b><span size='xx-large'>%s</span></b>" %(self._head_label_text))

        self._body_image = self._icon_finder.get_image("dialog-information-symbolic")

        self._body_image.set_pixel_size(gui.ImageSize.LARGE)

        self._body_label = Gtk.Label()

        self._body_label.set_wrap(True)

        self._body_label.set_wrap_mode(Gtk.NaturalWrapMode.WORD)

        self._body_label.set_justify(Gtk.Justification.CENTER)

        self._body_label.set_text(self._locale_manager.get("GREETER_WINDOW_BODY"))

        self._continue_button = Gtk.Button()

        self._continue_button.add_css_class("pill")

        self._continue_button.add_css_class("suggested-action")

        self._continue_button.set_margin_top(gui.Margin.LARGE)

        self._continue_button.set_margin_start(gui.Margin.LARGE)

        self._continue_button.set_margin_end(gui.Margin.LARGE)

        self._continue_button.connect("clicked", self._on_continue_button_clicked)

        self._continue_button.set_label(self._locale_manager.get("GREETER_BUTTON_TEXT"))

        self._content_box = Gtk.Box()

        self._content_box.set_orientation(Gtk.Orientation.VERTICAL)

        self._content_box.set_margin_bottom(gui.Margin.LARGEST)

        self._content_box.set_margin_start(gui.Margin.LARGEST)

        self._content_box.set_margin_end(gui.Margin.LARGEST)

        self._content_box.set_spacing(gui.Margin.LARGE)

        self._content_box.append(self._head_label)

        self._content_box.append(self._body_image)

        self._content_box.append(self._body_label)

        self._content_box.append(self._continue_button)

        self._top_header_bar = Gtk.HeaderBar()

        self._top_header_bar.add_css_class("flat")

        self._top_header_bar.set_show_title_buttons(True)

        self._bottom_header_bar = Gtk.HeaderBar()

        self._bottom_header_bar.add_css_class("flat")

        self._bottom_header_bar.set_show_title_buttons(False)

        self._bottom_header_bar.set_title_widget(self._content_box)

        self._main_box = Gtk.Box()

        self._main_box.set_orientation(Gtk.Orientation.VERTICAL)

        self._main_box.append(self._top_header_bar)

        self._main_box.append(self._bottom_header_bar)

        self._horizontal_clamp = Adw.Clamp()

        self._horizontal_clamp.set_maximum_size(0)

        self._horizontal_clamp.set_child(self._main_box)

        self._vertical_clamp = Adw.Clamp()

        self._vertical_clamp.set_maximum_size(0)

        self._vertical_clamp.set_orientation(Gtk.Orientation.VERTICAL)

        self._vertical_clamp.set_child(self._horizontal_clamp)

        self._event_controller_key = Gtk.EventControllerKey()

        self._event_controller_key.connect("key-pressed", self._on_event_controller_key_pressed)

        self.set_transient_for(self._application_window)

        self.set_resizable(False)

        self.set_modal(True)

        self.set_content(self._vertical_clamp)

    def _on_event_controller_key_pressed(self, controller, keyval, keycode, state):

        if keyval == gui.Keyval.ESCAPE:

            self.close()

    def _on_continue_button_clicked(self, button):

        self._events.trigger("confirmed", self)

        self.close()

    def hook(self, event, callback, *args):

        self._events.hook(event, callback, *args)

    def release(self, id):

        self._events.release(id)


class StarterAlreadyExistingError(Exception):

    pass


class StarterNotFoundError(Exception):

    pass


class Application(gui.Application):

    def __init__(self, *args, **kwargs):

        gui.Application.__init__(self, *args, **kwargs)

        self._current_desktop_starter_name = None

        self._desktop_starter_parsers = {}

        self._unsaved_custom_starters = []

        self._debug_mode_enabled = "--debug" in sys.argv

        ###############################################################################################################

        self._icon_finder.add_alternatives(

            "system-search-symbolic",

            "find-symbolic",

            "gtk-find-symbolic",

            "edit-find-symbolic",

            "filefind-symbolic",

            "stock_search-symbolic",

            "system-search",

            "find",

            "gtk-find",

            "edit-find",

            "filefind",

            "stock_search"

            )

        self._icon_finder.add_alternatives(

            "document-edit-symbolic",

            "edit-symbolic",

            "gtk-edit-symbolic",

            "edit-entry-symbolic",

            "edit-rename-symbolic",

            "entry-edit-symbolic",

            "edittext-symbolic",

            "stock_edit-symbolic",

            "document-edit",

            "edit",

            "gtk-edit",

            "edit-entry",

            "edit-rename",

            "entry-edit",

            "edittext",

            "stock_edit"

            )

        self._icon_finder.add_alternatives(

            "document-open-symbolic",

            "folder-open-symbolic"

            "gtk-open-symbolic"

            "fileopen-symbolic"

            "stock_open-symbolic"

            "document-open"

            "folder-open"

            "gtk-open"

            "fileopen"

            "stock_open"

            )

        self._icon_finder.add_alternatives(

            "action-unavailable-symbolic",

            "error-symbolic",

            "no-symbolic",

            "gtk-no-symbolic",

            "stock_no-symbolic",

            "emblem-error-symbolic",

            "emblem-unavailable-symbolic",

            "dialog-error-symbolic",

            "dialog-no-symbolic",

            "system-error-symbolic",

            "action-unavailable",

            "error",

            "no",

            "gtk-no",

            "stock_no",

            "emblem-error",

            "emblem-unavailable",

            "dialog-error",

            "dialog-no",

            "system-error"

            )

        ###############################################################################################################

        self._icon_finder.add_alternatives(

            "open-menu-symbolic",

            "application-menu-symbolic",

            "stock_file-properties-symbolic",

            "overflow-menu-symbolic",

            "open-menu",

            "application-menu",

            "stock_file-properties",

            "overflow-menu"

            )

        self._icon_finder.add_alternatives(

            "list-add-symbolic",

            "add-symbolic",

            "gtk-add-symbolic",

            "edit-add-symbolic",

            "list-add",

            "add",

            "gtk-add",

            "edit-add"

            )

        self._icon_finder.add_alternatives(

            "list-remove-symbolic",

            "remove-symbolic",

            "gtk-remove-symbolic",

            "edit-remove-symbolic",

            "list-remove",

            "remove",

            "gtk-remove",

            "edit-remove"

            )

        self._icon_finder.add_alternatives(

            "dialog-information-symbolic",

            "help-info-symbolic",

            "info-symbolic",

            "gtk-info-symbolic",

            "gtk-dialog-info-symbolic",

            "gtk-dialog-warning-symbolic",

            "dialog-warning-symbolic",

            "state-information-symbolic",

            "state-warning-symbolic",

            "emblem-information-symbolic",

            "emblem-warning-symbolic",

            "stock_dialog-info-symbolic",

            "dialog-information",

            "help-info",

            "info",

            "gtk-info",

            "gtk-dialog-info",

            "gtk-dialog-warning",

            "dialog-warning",

            "state-information",

            "state-warning",

            "emblem-information",

            "emblem-warning",

            "stock_dialog-info",

            "page.codeberg.libre_menu_editor.LibreMenuEditor"

            )

        ###############################################################################################################

        self._desktop_starter_custom_create_name = "custom-desktop-starter"

        self._desktop_starter_template_path = os.path.join(self.get_project_dir(), "custom.desktop")

        self._desktop_starter_override_dir = os.path.join(GLib.get_user_data_dir(), "applications")

        ###############################################################################################################

        self._application_window.set_size_request(-1, 240)

        self._application_window.set_title(self._locale_manager.get("WINDOW_TITLE"))

        self._application_window.connect("close-request", self._on_application_window_close_request)

        self._application_window.connect("map", self._on_application_window_map)

        ###############################################################################################################

        self._welcome_page = Gtk.Box()

        self._settings_page = SettingsPage(self)

        ###############################################################################################################

        self._search_list = gui.SearchList(self)

        self._search_list.set_min_row_width(240)

        self._search_list.hook("item-activated", self._on_search_list_item_activated)

        self._search_list.set_focus_chain_widget(self._settings_page)

        ###############################################################################################################

        self._save_button = self._settings_page.get_save_button()

        self._save_button.set_visible(False)

        self._save_button.connect("clicked", self._on_save_button_clicked)

        self._reload_button = self._settings_page.get_reload_button()

        self._reload_button.set_visible(False)

        self._reload_button.connect("clicked", self._on_reload_button_clicked)

        self._enabled_switch = self._settings_page.get_enabled_switch()

        self._enabled_switch.set_visible(False)

        self._create_button = Gtk.Button()

        self._create_button.set_icon_name(self._icon_finder.get_name("list-add-symbolic"))

        self._create_button.connect("clicked", self._on_create_button_clicked)

        self._search_button = self._search_list.get_search_button()

        ###############################################################################################################

        self._view_menu_section = gui.Menu(self)

        self._view_menu_section.add_switch("show_disabled", self._locale_manager.get("SHOW_DISABLED_SWITCH_LABEL"))

        self._view_menu_section.set_switch_state("show_disabled", self._config_manager.get("starters.show_disabled"))

        self._view_menu_section.hook("show_disabled", self._on_show_disabled_switch_changed)

        self._view_menu_section.add_switch("show_hidden", self._locale_manager.get("SHOW_HIDDEN_SWITCH_LABEL"))

        self._view_menu_section.set_switch_state("show_hidden", self._config_manager.get("starters.show_hidden"))

        self._view_menu_section.hook("show_hidden", self._on_show_hidden_switch_changed)

        self._reset_menu_section = gui.Menu(self)

        self._reset_menu_section.add_button("reset", self._locale_manager.get("RESET_BUTTON_LABEL"))

        self._reset_menu_section.hook("reset", self._on_reset_button_clicked)

        self._delete_menu_section = gui.Menu(self)

        self._delete_menu_section.add_button("delete", self._locale_manager.get("DELETE_BUTTON_LABEL"))

        self._delete_menu_section.hook("delete", self._on_delete_button_clicked)

        self._external_menu_section = gui.Menu(self)

        self._external_menu_section.add_button("file", self._locale_manager.get("FILE_BUTTON_LABEL"))

        self._external_menu_section.hook("file", self._on_file_button_clicked)

        self._external_menu_section.add_button("directory", self._locale_manager.get("DIRECTORY_BUTTON_LABEL"))

        self._external_menu_section.hook("directory", self._on_directory_button_clicked)

        self._start_menu = gui.Menu(self)

        self._start_menu.append_section(None, self._view_menu_section)

        self._reset_menu = gui.Menu(self)

        self._reset_menu.append_section(None, self._view_menu_section)

        self._reset_menu.append_section(None, self._reset_menu_section)

        self._reset_menu.append_section(None, self._external_menu_section)

        self._delete_menu = gui.Menu(self)

        self._delete_menu.append_section(None, self._view_menu_section)

        self._delete_menu.append_section(None, self._delete_menu_section)

        self._delete_menu.append_section(None, self._external_menu_section)

        self._menu_button = Gtk.MenuButton()

        self._menu_button.set_icon_name(self._icon_finder.get_name("open-menu-symbolic"))

        self._menu_button.set_menu_model(self._start_menu)

        ###############################################################################################################

        self._left_event_controller_key = Gtk.EventControllerKey()

        self._left_event_controller_key.connect("key-pressed", self._on_left_event_controller_key_pressed)

        self._left_header_bar_label = Gtk.Label()

        self._left_header_bar = Gtk.HeaderBar()

        self._left_header_bar.set_show_title_buttons(False)

        self._left_header_bar.add_controller(self._left_event_controller_key)

        self._left_header_bar.set_title_widget(self._left_header_bar_label)

        self._left_header_bar.pack_start(self._search_button)

        self._left_header_bar.pack_end(self._create_button)

        self._right_event_controller_key = Gtk.EventControllerKey()

        self._right_event_controller_key.connect("key-pressed", self._on_right_event_controller_key_pressed)

        self._right_header_bar_label = Gtk.Label()

        self._right_header_bar = Gtk.HeaderBar()

        self._right_header_bar.add_controller(self._right_event_controller_key)

        self._right_header_bar.set_title_widget(self._right_header_bar_label)

        self._right_header_bar.pack_start(self._enabled_switch)

        self._right_header_bar.pack_end(self._menu_button)

        self._right_header_bar.pack_end(self._reload_button)

        self._right_header_bar.pack_end(self._save_button)

        ###############################################################################################################

        self._main_stack = Gtk.Stack()

        self._main_stack.add_child(self._welcome_page)

        self._main_stack.add_child(self._settings_page)

        self._toast_overlay = Adw.ToastOverlay()

        self._toast_overlay.set_vexpand(True)

        self._toast_overlay.set_child(self._main_stack)

        ###############################################################################################################

        self._left_area_box = Gtk.Box()

        self._left_area_box.set_orientation(Gtk.Orientation.VERTICAL)

        self._left_area_box.append(self._left_header_bar)

        self._left_area_box.append(self._search_list)

        self._right_area_box = Gtk.Box()

        self._right_area_box.set_orientation(Gtk.Orientation.VERTICAL)

        self._right_area_box.append(self._right_header_bar)

        self._right_area_box.append(self._toast_overlay)

        self._main_paned = Gtk.Paned()

        self._main_paned.set_position(self._config_manager.get("sidebar.position"))

        self._main_paned.set_shrink_start_child(False)

        self._main_paned.set_resize_start_child(False)

        self._main_paned.set_shrink_end_child(False)

        self._main_paned.set_start_child(self._left_area_box)

        self._main_paned.set_end_child(self._right_area_box)

        ###############################################################################################################

        self._greeter_window = GreeterWindow(self)

        self._greeter_window.hook("confirmed", self._on_greeter_window_confirmed)

        ###############################################################################################################

        self._application_window.set_content(self._main_paned)

        self.load_desktop_starter_dirs()

        self.parse_command_line_args()

    def _on_greeter_window_confirmed(self, event, window):

        self._config_manager.set("greeter-confirmed", True)

    def _on_unsaved_message_dialog_response(self, message_dialog, response):

        if response == "save":

            self._save_settings_page()

            self._load_settings_page(self._unsaved_message_dialog_new_starter_name)

        elif response == "discard":

            self._load_settings_page(self._unsaved_message_dialog_new_starter_name)

        else:

            self._show_settings_page()

    def _on_application_window_map(self, window):

        if not self._config_manager.get("greeter-confirmed"):

            self._greeter_window.set_application(self)

            self._greeter_window.show()

    def _on_application_window_close_request(self, window):

        self._config_manager.set("sidebar.position", self._main_paned.get_position())

    def _on_left_event_controller_key_pressed(self, controller, keyval, keycode, state):

        if keyval == gui.Keyval.DOWN:

            self._search_list.grab_focus()

            return True

    def _on_right_event_controller_key_pressed(self, controller, keyval, keycode, state):

        if keyval == gui.Keyval.DOWN:

            if self._main_stack.get_visible_child() == self._settings_page:

                if not self._enabled_switch.get_active():

                    self._enabled_switch.set_active(True)

                self._settings_page.grab_focus()

            return True

    def _on_show_disabled_switch_changed(self, name):

        state = self._view_menu_section.get_switch_state(name)

        if not self._config_manager.get("starters.show_disabled") == state:

            self._config_manager.set("starters.show_disabled", state)

            self.reload_search_list_items()

    def _on_show_hidden_switch_changed(self, name):

        state = self._view_menu_section.get_switch_state(name)

        if not self._config_manager.get("starters.show_hidden") == state:

            self._config_manager.set("starters.show_hidden", state)

            self.reload_search_list_items()

    def _on_reset_button_clicked(self, event):

        self._reset_desktop_starter(self._current_desktop_starter_name)

    def _on_delete_button_clicked(self, event):

        self._delete_desktop_starter(self._current_desktop_starter_name)

    def _on_file_button_clicked(self, event):

        path = self._get_current_starter_external_path()

        subprocess.Popen(["xdg-open", path])

    def _on_directory_button_clicked(self, event):

        path = self._get_current_starter_external_path()

        subprocess.Popen(["xdg-open", os.path.dirname(path)])

    def _on_create_button_clicked(self, button):

        self._create_desktop_starter()

    def _on_save_button_clicked(self, button):

        self._save_settings_page()

    def _on_reload_button_clicked(self, button):

        self._reload_settings_page()

    def _on_search_list_item_activated(self, event, name):

        if not name == self._current_desktop_starter_name:

            if not self._current_desktop_starter_name is None and self._settings_page.get_input_children_changed():

                self._unsaved_message_dialog_new_starter_name = name

                discard_message_dialog = Adw.MessageDialog.new(

                    self._application_window,

                    self._locale_manager.get("UNSAVED_DIALOG_HEAD"),

                    self._locale_manager.get("UNSAVED_DIALOG_BODY")

                    )

                discard_message_dialog.add_response(

                    "back", self._locale_manager.get("UNSAVED_DIALOG_BACK_BUTTON_TEXT")

                    )

                discard_message_dialog.add_response(

                    "save", self._locale_manager.get("UNSAVED_DIALOG_SAVE_BUTTON_TEXT")

                    )

                discard_message_dialog.add_response(

                    "discard", self._locale_manager.get("UNSAVED_DIALOG_DISCARD_BUTTON_TEXT")

                    )

                discard_message_dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)

                discard_message_dialog.connect("response", self._on_unsaved_message_dialog_response)

                discard_message_dialog.show()

            else:

                self._load_settings_page(name)

        else:

            self._settings_page.grab_focus()

    def _update_menu_button_menu_model(self):

        if self._main_stack.get_visible_child() == self._settings_page:

            if os.path.exists(self._get_current_starter_external_path()):

                self._external_menu_section.set_enabled("file", True)

                self._external_menu_section.set_enabled("directory", True)

            else:

                self._external_menu_section.set_enabled("file", False)

                self._external_menu_section.set_enabled("directory", False)

            if self._get_desktop_starter_has_default(self._current_desktop_starter_name):

                if self._get_desktop_starter_has_override(self._current_desktop_starter_name):

                    self._reset_menu_section.set_enabled("reset", True)

                else:

                    self._reset_menu_section.set_enabled("reset", False)

                self._menu_button.set_menu_model(self._reset_menu)

            else:

                self._menu_button.set_menu_model(self._delete_menu)

        else:

            self._menu_button.set_menu_model(self._start_menu)

    def parse_command_line_args(self):

        if len(sys.argv) > 1 and "--new" in sys.argv[1:]:

            self._create_desktop_starter()

    def _get_current_starter_external_path(self):

        path = self._desktop_starter_parsers[self._current_desktop_starter_name].get_save_path()

        if not os.path.exists(path):

            path = self._desktop_starter_parsers[self._current_desktop_starter_name].get_load_path()

        if os.getenv("APP_RUNNING_AS_FLATPAK") == "true":

            return self.get_flatpak_host_user_data_path(path)

        else:

            return path

    def _get_desktop_starter_has_default(self, name):

        return os.path.exists(self._get_desktop_starter_default_path(name, include_host=True))

    def _get_desktop_starter_has_override(self, name):

        return os.path.exists(self._get_desktop_starter_override_path(name))

    def _get_desktop_starter_default_path(self, name, include_host=False):

        for directory in self._system_data_dirs:

            path = os.path.join(directory, "applications", "%s.desktop" % name)

            if os.getenv("APP_RUNNING_AS_FLATPAK") == "true" and include_host:

                path = self.get_flatpak_sandbox_system_path(path)

            if os.path.exists(path):

                return path

        else:

            return os.path.join(self._system_data_dirs[0], "applications", "%s.desktop" % name)

    def _get_desktop_starter_override_path(self, name, include_host=False):

        path = os.path.join(self._desktop_starter_override_dir, "%s.desktop" % name)

        if os.getenv("APP_RUNNING_AS_FLATPAK") == "true" and include_host:

            path = self.get_flatpak_sandbox_system_path(path)

        return path

    def _get_desktop_starter_names(self):

        names = []

        for directory in self._system_data_dirs:

            directory = os.path.join(directory, "applications")

            if os.path.exists(directory):

                for file in os.listdir(directory):

                    if file.endswith(".desktop"):

                        name = file[:-len(".desktop")]

                        if not name in names:

                            names.append(name)

        if os.path.exists(self._desktop_starter_override_dir):

            for file in os.listdir(self._desktop_starter_override_dir):

                if file.endswith(".desktop"):

                    name = file[:-len(".desktop")]

                    if not name in names:

                        names.append(name)

            else:

                return names

        else:

            return names

    def _load_settings_page(self, name):

        if not name == self._current_desktop_starter_name:

            self._current_desktop_starter_name = name

            parser = self._desktop_starter_parsers[name]

            self._settings_page.load_desktop_starter(name, parser)

        self._show_settings_page()

    def _save_settings_page(self):

        try:

            self._settings_page.save_desktop_starter()

        except Exception as error:

            if self._debug_mode_enabled:

                raise error

            else:

                print("error 2:", error)

                self._send_interface_alert(self._locale_manager.get("STARTER_SAVE_ERROR_TEXT"), error=True)

                return True

        if self._current_desktop_starter_name in self._unsaved_custom_starters:

            self._unsaved_custom_starters.remove(self._current_desktop_starter_name)

        parser = self._desktop_starter_parsers[self._current_desktop_starter_name]

        text = parser.get_name()

        if not len(text):

            text = self._locale_manager.get("UNNAMED_APPLICATION_PLACEHOLDER_TEXT")

        self._send_interface_alert(self._locale_manager.get("STARTER_SAVE_MESSAGE_TEXT") % text)

        self._update_search_list_item(self._current_desktop_starter_name)

        self._update_menu_button_menu_model()

    def _reload_settings_page(self):

        name = self._current_desktop_starter_name

        self._current_desktop_starter_name = None

        self._load_settings_page(name)

    def _show_settings_page(self):

        if not self._main_stack.get_visible_child() == self._settings_page:

            self._save_button.set_visible(True)

            self._reload_button.set_visible(True)

            self._enabled_switch.set_visible(True)

            self._main_stack.set_visible_child(self._settings_page)

        self._update_menu_button_menu_model()

        self._settings_page.grab_focus()

        GLib.idle_add(self._fix_header_bar_height)

    def _hide_settings_page(self):

        if self._main_stack.get_visible_child() == self._settings_page:

            self._save_button.set_visible(False)

            self._reload_button.set_visible(False)

            self._enabled_switch.set_visible(False)

            self._main_stack.set_visible_child(self._welcome_page)

            self._update_menu_button_menu_model()

        self._current_desktop_starter_name = None

        GLib.idle_add(self._fix_header_bar_height)

    def _fix_header_bar_height(self):

        height = sorted([self._left_header_bar.get_height(), self._right_header_bar.get_height()])[-1]

        self._left_header_bar.set_property("height-request", height)

        self._right_header_bar.set_property("height-request", height)

        self._left_header_bar.queue_resize()

        self._right_header_bar.queue_resize()

    def _create_desktop_starter(self):

        while True:

            random_string = ''.join(random.choices(string.digits, k=6))

            name = "%s.%s" % (self._desktop_starter_custom_create_name, random_string)

            if not name in self._get_desktop_starter_names() and not name in self._unsaved_custom_starters:

                break

        self._unsaved_custom_starters.append(name)

        self._add_desktop_starter(name)

        parser = self._desktop_starter_parsers[name]

        text = parser.get_name()

        if not len(text):

            text = self._locale_manager.get("UNNAMED_APPLICATION_PLACEHOLDER_TEXT")

        self._send_interface_alert(self._locale_manager.get("STARTER_CREATE_MESSAGE_TEXT") % text)

        self._load_settings_page(name)

    def _reset_desktop_starter(self, name):

        path = self._get_desktop_starter_override_path(name)

        try:

            os.remove(path)

        except Exception as error:

            if self._debug_mode_enabled:

                raise error

            else:

                print("error 3:", error)

                self._send_interface_alert(self._locale_manager.get("STARTER_RESET_ERROR_TEXT"), error=True)

                return True

        parser = self._desktop_starter_parsers[name]

        text = parser.get_name()

        if not len(text):

            text = self._locale_manager.get("UNNAMED_APPLICATION_PLACEHOLDER_TEXT")

        self._send_interface_alert(self._locale_manager.get("STARTER_RESET_MESSAGE_TEXT") % text)

        self._remove_desktop_starter(name, skip_search_list=True)

        self._add_desktop_starter(name, skip_search_list=True)

        self._update_search_list_item(name)

        self._reload_settings_page()

    def _delete_desktop_starter(self, name):

        path = self._get_desktop_starter_override_path(name)

        if not name in self._unsaved_custom_starters:

            try:

                os.remove(path)

            except Exception as error:

                if self._debug_mode_enabled:

                    raise error

                else:

                    print("error 4:", error)

                    self._send_interface_alert(self._locale_manager.get("STARTER_DELETE_ERROR_TEXT"), error=True)

                    return True

        parser = self._desktop_starter_parsers[name]

        text = parser.get_name()

        if not len(text):

            text = self._locale_manager.get("UNNAMED_APPLICATION_PLACEHOLDER_TEXT")

        self._send_interface_alert(self._locale_manager.get("STARTER_DELETE_MESSAGE_TEXT") % text)

        self._remove_desktop_starter(name)

        if name == self._current_desktop_starter_name:

            self._hide_settings_page()

    def _add_search_list_item(self, name):

        if not self._config_manager.get("starters.show_disabled"):

            if self._desktop_starter_parsers[name].get_disabled():

                return True

        if not self._config_manager.get("starters.show_hidden"):

            if self._desktop_starter_parsers[name].get_hidden():

                return True

        text = self._desktop_starter_parsers[name].get_name()

        icon = self._desktop_starter_parsers[name].get_icon()

        search_data = self._desktop_starter_parsers[name].get_search_data()

        if not len(text):

            text = self._locale_manager.get("UNNAMED_APPLICATION_PLACEHOLDER_TEXT")

        self._search_list.add(name, text, icon, search_data)

    def _remove_search_list_item(self, name):

        self._search_list.remove(name)

    def _update_search_list_item(self, name):

        parser = self._desktop_starter_parsers[name]

        if parser.get_hidden() and not self._config_manager.get("starters.show_hidden"):

            if name in self._search_list.list():

                self._search_list.remove(name)

                if name == self._current_desktop_starter_name:

                    self._hide_settings_page()

        elif parser.get_disabled() and not self._config_manager.get("starters.show_disabled"):

            if name in self._search_list.list():

                self._search_list.remove(name)

                if name == self._current_desktop_starter_name:

                    self._hide_settings_page()

        else:

            text = parser.get_name()

            icon = parser.get_icon()

            search_data = parser.get_search_data()

            if not len(text):

                text = self._locale_manager.get("UNNAMED_APPLICATION_PLACEHOLDER_TEXT")

            self._search_list.update(self._current_desktop_starter_name, text, icon, search_data)

    def _add_desktop_starter(self, name, skip_search_list=False):

        if not name in self._desktop_starter_parsers:

            parser = self._parse_desktop_starter(name)

            self._desktop_starter_parsers[name] = parser

            if not skip_search_list:

                self._add_search_list_item(name)

        else:

            raise StarterAlreadyExistingError(name)

    def _remove_desktop_starter(self, name, skip_search_list=False):

        if self._current_desktop_starter_name in self._unsaved_custom_starters:

            self._unsaved_custom_starters.remove(self._current_desktop_starter_name)

        if name in self._desktop_starter_parsers:

            del self._desktop_starter_parsers[name]

            if not skip_search_list:

                self._remove_search_list_item(name)

        else:

            raise StarterNotFoundError(name)

    def _parse_desktop_starter(self, name):

        if name in self._unsaved_custom_starters:

            load_path = self._desktop_starter_template_path

        else:

            load_path = self._get_desktop_starter_override_path(name, include_host=True)

        save_path = self._get_desktop_starter_override_path(name)

        if not os.path.exists(load_path):

            default_path = self._get_desktop_starter_default_path(name, include_host=True)

            if os.path.exists(default_path):

                load_path = default_path

            else:

                raise StarterNotFoundError(name)

        parser = DesktopParser(load_path, save_path)

        return parser

    def _send_interface_alert(self, text, error=False):

        toast = Adw.Toast.new(text)

        if not error:

            toast.set_timeout(gui.Timeout.DEFAULT)

        self._toast_overlay.add_toast(toast)

    def reload_search_list_items(self):

        self._search_list.clear()

        for name in self._desktop_starter_parsers:

            self._add_search_list_item(name)

        if not self._current_desktop_starter_name in self._search_list.list():

            self._hide_settings_page()

    def load_desktop_starter_dirs(self):

        # exceptions = []

        for name in reversed(sorted(self._get_desktop_starter_names())):

            try:

                self._add_desktop_starter(name)

            except Exception as error:

                if self._debug_mode_enabled:

                    raise error

                else:

                    print("error 5:", error)

                    # exceptions.append(name)

        # if len(exceptions) > 1:

            # text = str(len(exceptions))

            # self._send_interface_alert(self._locale_manager.get("LOAD_MULTIPLE_ERROR_TEXT") % text, error=True)

        # elif len(exceptions) > 0:

            # text = exceptions[0]

            # self._send_interface_alert(self._locale_manager.get("LOAD_SINGLE_ERROR_TEXT") % text, error=True)


if __name__ == "__main__":

    project_dir = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))

    app = Application(project_dir, application_id="page.codeberg.libre_menu_editor.LibreMenuEditor")

    app.run()
