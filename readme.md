<img src="https://codeberg.org/libre-menu-editor/downloads/raw/branch/main/screenshots/9.png"/>

# One-Click installation

- through the software center on [many GNU+Linux distributions](https://flathub.org/setup)
- through the [Arch-User-Repository](https://aur.archlinux.org/packages/libre-menu-editor) on [ArchLinux](https://archlinux.org)-based systems
- through the [download-page](https://flathub.org/apps/page.codeberg.libre_menu_editor.LibreMenuEditor) on flathub

---

# Manual setup

### Dependencies:
 - python3
 - python3-gobject
 - libadwaita >= 1.4 *(for adaptive interface)*
 - libadwaita >= 1.2 *(for static interface)*
 - libgtk >= 4.8
 - xdg-utils

## First: Download the code
```
git clone https://codeberg.org/libre-menu-editor/libre-menu-editor
```
```
cd libre-menu-editor
```

## Option 1: Run without installation
```
libre-menu-editor/main.py
```

## Option 2: Install with flatpak-builder
```
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
```
```
flatpak install org.gnome.Platform/x86_64/46
```
```
flatpak-builder --user --install --force-clean .build-dir flatpak.yml
```

## Option 3: Install with make
```
sudo make install
```
```
sudo gtk-update-icon-cache -f /usr/share/icons/hicolor
```

---

# How to contribute

### 1. By reporting bugs and giving feedback

Bug reports, feedback, and feature requests can be made through the [issue tracker](https://codeberg.org/libre-menu-editor/libre-menu-editor/issues).

### 2. By making improvements to the code

If you have written bug fixes and want to merge them into the upstream project, feel free to make a [pull request](https://codeberg.org/libre-menu-editor/libre-menu-editor/pulls). If you want to contribute code that introduces new features, changes existing features or makes changes to the interface, please open an issue to first discuss your ideas with the project's maintainers.

### 3. By improving the translation

If you want to add or improve a translation, it is recommended to do so through the [weblate](https://hosted.weblate.org/projects/libre-menu-editor). Alternatively, you can edit the [translation files](libre-menu-editor/locales) directly and contribute your changes in a pull request.

<a href="https://hosted.weblate.org/engage/libre-menu-editor/">
<img src="https://hosted.weblate.org/widget/libre-menu-editor/horizontal-auto.svg" alt="Translation status" />
</a>

---

# Contributions

**2023-07-01 13:05:23**: albano.battistella <albano.battistella@noreply.codeberg.org>
 - added italian translations: [it.json](libre-menu-editor/locales/it.json)

**2024-01-07 19:32:30**: locness3 <locness3@e.email>
 - improved french translations: [fr.json](libre-menu-editor/locales/fr.json)

**2024-04-28 04:59:14**: Sabri Ünal <yakushabb@gmail.com>
 - added turkish translations: [tr.json](libre-menu-editor/locales/tr.json)
