# Libre Menu Editor

<img src="https://codeberg.org/libre-menu-editor/downloads/raw/branch/main/screenshots/1.png" height=360/>

## One-Click installation

1. through the software center on [many linux distributions](https://flathub.org/setup)

2. through the [Arch-User-Repository](https://aur.archlinux.org/packages/libre-menu-editor) on [ArchLinux](https://archlinux.org)-based systems

3. through the [download-page](https://flathub.org/apps/page.codeberg.libre_menu_editor.LibreMenuEditor) on flathub

---

## Download the code

```
git clone https://codeberg.org/libre-menu-editor/libre-menu-editor
```
```
cd libre-menu-editor
```

## Install latest flatpak

```
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
```
```
flatpak install org.gnome.Platform/x86_64/44
```
```
flatpak-builder --user --install --force-clean .build-dir flatpak.yml
```

## Run without installation

```
libre-menu-editor/main.py
```

## Install with makefile

```
sudo make install
```
```
sudo gtk-update-icon-cache -f /usr/share/icons/hicolor
```

## Contribute translations

1. Check if the translation exists in the [locales](https://codeberg.org/libre-menu-editor/libre-menu-editor/src/branch/main/libre-menu-editor/locales) directory

2. Check if there are [issues](https://codeberg.org/libre-menu-editor/libre-menu-editor/issues) about the translation

3. Download and translate the [en.json](https://codeberg.org/libre-menu-editor/libre-menu-editor/raw/branch/main/libre-menu-editor/locales/en.json) file

4. Download and translate the [page.codeberg.libre_menu_editor.LibreMenuEditor.appdata.xml](https://codeberg.org/libre-menu-editor/libre-menu-editor/raw/branch/main/export/share/metainfo/page.codeberg.libre_menu_editor.LibreMenuEditor.appdata.xml) file

5. Download and translate the [page.codeberg.libre_menu_editor.LibreMenuEditor.desktop](https://codeberg.org/libre-menu-editor/libre-menu-editor/raw/branch/main/export/share/applications/page.codeberg.libre_menu_editor.LibreMenuEditor.desktop) file

6. Open a [new issue](https://codeberg.org/libre-menu-editor/libre-menu-editor/issues/new) and upload the translated files

## Translation contributions

- albano.battistella contributed to [italian](https://codeberg.org/libre-menu-editor/libre-menu-editor/raw/branch/main/libre-menu-editor/it.json) translations

- jacekpoz contributed to [polish](https://codeberg.org/libre-menu-editor/libre-menu-editor/raw/branch/main/libre-menu-editor/pl.json) translations
