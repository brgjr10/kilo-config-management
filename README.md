# Kilo Manager - Desktop GUI for managing Kilo configuration

A Python tkinter desktop application for managing Kilo's MCP servers, skills, and permissions.

## Features

- **MCP Servers** - Add, edit, and delete MCP servers (local stdio or remote HTTP)
- **Skills** - Browse available Kilo skills with enable/disable toggles
- **Permissions** - Edit bash command patterns and external directory permissions

## Installation

```bash
pip3 install --break-system-packages ttkbootstrap Pillow
```

## Usage

```bash
python3 kilo_manager.py
```

## Building

### Linux Executable (PyInstaller)

```bash
pip3 install --break-system-packages pyinstaller
pyinstaller --onefile --windowed kilo_manager.py
```

### Linux AppImage

```bash
pip3 install --break-system-packages appimage-builder
appimage-builder --generate
# Edit AppImageBuilder.yml as needed, then:
appimage-builder
```

## License

MIT