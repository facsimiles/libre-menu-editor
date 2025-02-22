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


import os, sys, json, threading, time, fcntl


class PathInspector():

    def __init__(self):

        self._paths = {}

        self._delay = 0.5

        self._active = False

        self._stopped = False

        self._events = EventManager()

        self._events.add("changed", str, float)

        self._events.add("created", str, float)

        self._events.add("deleted", str, float)

        self._thread = threading.Thread(target=self._thread_target)

    def _thread_target(self):

        while not self._stopped:

            time.sleep(self._delay)

            for path in self._paths:

                old_timestamp = self._paths[path]["timestamp"]

                try:

                    new_timestamp = os.path.getmtime(path)

                    if new_timestamp > old_timestamp:

                        self._paths[path]["timestamp"] = new_timestamp

                        if old_timestamp:

                            self._events.trigger("changed", path, float(new_timestamp))

                        else:

                            self._events.trigger("created", path, float(new_timestamp))

                except FileNotFoundError:

                    if old_timestamp:

                        self._paths[path]["timestamp"] = 0

                        self._events.trigger("deleted", path, float(old_timestamp))

    def add(self, path):

        if not path in self._paths:

            if os.path.exists(path):

                self._paths[path] = {

                    "timestamp": os.path.getmtime(path)

                    }

            else:

                self._paths[path] = {

                    "timestamp": 0

                    }

            if not self.get_active():

                self.set_active(True)

    def remove(self, path):

        if path in self._paths:

            del self._paths[path]

            if not len(self._paths):

                self.set_active(False)

    def get_paths(self):

        return list(self._paths.keys())

    def get_active(self):

        return self._active

    def set_active(self, value):

        if value and not self._active:

            self._active = True

            self._thread.start()

        elif not value and self._active and not self._stopped:

            self._stopped = True

            self._thread.join()

            self._stopped = False

            self._active = False

    def hook(self, event, callback):

        return self._events.hook(event, callback)

    def release(self, id):

        self._events.release(id)


class ProcessManager():

    def __init__(self, lock_path, argv_path, exit=True):

        os.makedirs(os.path.dirname(lock_path), exist_ok=True)

        os.makedirs(os.path.dirname(argv_path), exist_ok=True)

        try:

            self._lock_file = open(lock_path, "w+")

            fcntl.lockf(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)

        except IOError as error:

            with open(argv_path, "a") as file:

                file.writelines("\n{}".format("\n".join(sys.argv[1:])))

            if exit:

                sys.exit(int(exit))

            else:

                raise error

        else:

            self._lock_path = lock_path

            self._argv_path = argv_path

            self._events = EventManager()

            self._events.add("activate", list)

            self._path_inspector = PathInspector()

            self._path_inspector.hook("created", self._on_path_inspector_created)

            self._path_inspector.hook("changed", self._on_path_inspector_changed)

            self._initial_args = sys.argv[1:]

    def _on_path_inspector_created(self, event, path, timestamp):

        self._parse_argv_file(path)

    def _on_path_inspector_changed(self, event, path, timestamp):

        self._parse_argv_file(path)

    def _parse_argv_file(self, path):

        if os.path.exists(path):

            with open(path, "r") as file:

                args = file.read().splitlines()

                os.remove(path)

            self._trigger_argv_event(args)

        else:

            self._trigger_argv_event([])

    def _trigger_argv_event(self, args):

        args =  list(filter(None, args))

        self._events.trigger("activate", args)

    def get_active(self):

        return self._path_inspector.get_active()

    def set_active(self, value):

        if value:

            if len(self._initial_args):

                self._trigger_argv_event(self._initial_args)

                self._initial_args.clear()

            if not self._argv_path in self._path_inspector.get_paths():

                self._path_inspector.add(self._argv_path)

                return

        self._path_inspector.set_active(value)

    def hook(self, event, callback):

        return self._events.hook(event, callback)

    def release(self, id):

        self._events.release(id)


class EventAlreadyExistingError(Exception):

    pass


class EventNotFoundError(Exception):

    pass


class EventCallbackInvalidError(Exception):

    pass


class EventHookInvalidError(Exception):

    pass


class EventInvalidArgumentsError(Exception):

    pass


class EventUnexpectedArgumentsError(Exception):

    pass


class EventMissingArgumentsError(Exception):

    pass


class EventManager():

    def __init__(self):

        self._events = {}

        self._hooks = {}

        self._count = 0

    def get_events(self):

        return self._events.keys()

    def get_hooks(self):

        return self._hooks.keys()

    def add(self, event, *argtypes):

        if not event in self._events:

            for argtype in argtypes:

                if not isinstance(type, type(argtype)):

                    raise EventInvalidArgumentsError(argtypes)

            else:

                self._events[event] = {

                    "argtypes": argtypes,

                    "hooks": []

                    }

        else:

            raise EventAlreadyExistingError(event)

    def remove(self, event):

        if event in self._events:

            for id in self._events[event]["hooks"]:

                self.release(id)

            del self._events[event]

        else:

            raise EventNotFoundError(event)

    def hook(self, event, callback, *args):

        if event in self._events:

            if callable(callback):

                self._count += 1

                id = str(self._count)

                self._hooks[id] = {

                    "callback": callback,

                    "args": args,

                    "event": event

                    }

                self._events[event]["hooks"].append(id)

                return id

            else:

                raise EventCallbackInvalidError(callback)

        else:

            raise EventNotFoundError(event)

    def release(self, id):

        if id in self._hooks:

            event = self._hooks[id]["event"]

            self._events[event]["hooks"].remove(id)

            del self._hooks[id]

        else:

            raise EventHookInvalidError(id)

    def trigger(self, event, *args):

        responses = []

        if event in self._events:

            if len(self._events[event]["argtypes"]) == len(args):

                for n, arg in enumerate(args):

                    if not isinstance(arg, self._events[event]["argtypes"][n]):

                        raise EventInvalidArgumentsError(arg)

                else:

                    for id in self._events[event]["hooks"]:

                        callback = self._hooks[id]["callback"]

                        args += self._hooks[id]["args"]

                        responses.append(bool(callback(event, *args)))

            elif len(self._events[event]["argtypes"]) > len(args):

                value = len(self._events[event]["argtypes"]) - len(args)

                raise EventMissingArgumentsError(value)

            elif len(args) > len(self._events[event]["argtypes"]):

                value = len(args) - len(self._events[event]["argtypes"])

                raise EventUnexpectedArgumentsError(value)

        else:

            raise EventNotFoundError(event)

        return True in responses


class SettingNotFoundError(Exception):

    pass


class ValueWrongTypeError(Exception):

    pass


class ConfigManager():

    def __init__(self, default_path, modified_path):

        self._events = EventManager()

        self._default_data = {}

        self._modified_data = {}

        self.set_default_path(default_path)

        self.set_modified_path(modified_path)

        if os.access(modified_path, os.W_OK):

            self.load()

    def _read_json_data(self, path):

        with open(path, mode="r") as file:

            data = json.loads(file.read())

        return data

    def _write_json_data(self, path, data):

        with open(path, mode="w") as file:

            file.write(json.dumps(data, indent=2))

    def get_default_path(self):

        return self._default_path

    def set_default_path(self, path):

        if os.access(path, os.R_OK):

            self._default_path = path

            data = self._read_json_data(path)

            for key in self._default_data:

                if not key in data:

                    del self._default_data[key]

                    del self._modified_data[key]

                    self._events.remove(key)

            for key in data:

                if not key in self._default_data:

                    self._events.add(key)

                    self._default_data[key] = data[key]

                    self._modified_data[key] = data[key]

        else:

            raise PathNotAccessibleError(path)

    def get_mofidied_path(self):

        return self._modified_path

    def set_modified_path(self, path):

        parent_dir = os.path.dirname(path)

        if os.access(parent_dir, os.W_OK) or not os.path.exists(parent_dir):

            self._modified_path = path

        else:

            raise PathNotAccessibleError(path)

    def get_default_data(self):

        return self._default_data.copy()

    def get_modified_data(self):

        return self._modified_data.copy()

    def hook(self, key, callback, *args):

        self._events.hook(key, callback, *args)

    def release(self, id):

        self._events.release(id)

    def get(self, key):

        if key in self._modified_data:

            return self._modified_data[key]

        else:

            raise SettingNotFoundError(key)

    def set(self, key, value):

        if key in self._modified_data:

            if type(value) == type(self._modified_data[key]):

                if not value == self._modified_data[key]:

                    self._modified_data[key] = value

                    self._events.trigger(key)

            else:

                raise ValueWrongTypeError(value)

        else:

            raise SettingNotFoundError(key)

    def load(self):

        data = self._read_json_data(self._modified_path)

        for key in data:

            try:

                self.set(key, data[key])

            except SettingNotFoundError:

                pass

            except ValueWrongTypeError:

                pass

    def save(self):

        data = {}

        for key in self._modified_data:

            if not self._modified_data[key] == self._default_data[key]:

                data[key] = self._modified_data[key]

        if not os.path.exists(self._modified_path):

            os.makedirs(os.path.dirname(self._modified_path), exist_ok=True)

        elif not os.access(self._modified_path, os.W_OK):

            os.remove(self._modified_path)

        self._write_json_data(self._modified_path, data)


class LocaleNotFoundError(Exception):

    pass


class TranslationNotFoundError(Exception):

    pass


class LocaleManager():

    def __init__(self, directory, override=None, fallback="en"):

        self.set_directory(directory)

        self.set_override(override)

        self.set_fallback(fallback)

        self.load()

    def get_directory(self):

        self._directory

    def set_directory(self, path):

        if os.access(path, os.R_OK):

            self._directory = path

        else:

            raise PathNotAccessibleError(path)

    def get_override(self):

        return self._override

    def set_override(self, locale):

        if not locale == None:

            if locale in self.get_locales():

                self._override = locale

            else:

                raise LocaleNotFoundError(locale)

        else:

            self._override = None

    def get_fallback(self):

        return self._fallback

    def set_fallback(self, locale):

        if locale in self.get_locales():

            self._fallback = locale

        else:

            raise LocaleNotFoundError(locale)

    def get_locales(self):

        locales = []

        for item in os.listdir(self._directory):

            path = os.path.join(self._directory, item)

            if os.path.isfile(path):

                locales.append(item.split(".")[0])

        return locales

    def get_path(self, locale):

        for item in os.listdir(self._directory):

            path = os.path.join(self._directory, item)

            if os.path.isfile(path) and item.split(".")[0] == locale:

                return path

    def get(self, key):

        if key in self._data:

            return self._data[key]

        else:

            raise TranslationNotFoundError(key)

    def load(self):

        if not self._override == None:

            default_path = self.get_path(self._override)

        else:

            system_lang = os.getenv("LANG").split(".")[0].split("_")[0]

            default_path = self.get_path(system_lang)

        if not default_path == None and os.access(default_path, os.R_OK):

            with open(default_path, mode="r") as file:

                self._data = json.loads(file.read())

        else:

            with open(self.get_path(self._fallback), mode="r") as file:

                self._data = json.loads(file.read())

class PathNotAccessibleError(Exception):

    pass
