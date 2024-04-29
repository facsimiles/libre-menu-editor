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
flatpak install org.gnome.Platform/x86_64/46
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
