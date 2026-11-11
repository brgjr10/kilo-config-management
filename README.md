# Kilo Manager

Desktop GUI for managing [Kilo](https://kilo.ai) configuration — MCP servers, skills, and permissions. Built with Python, tkinter, and [ttkbootstrap](https://ttkbootstrap.readthedocs.io/).

## Features

| Tab | What you can do |
|-----|-----------------|
| **MCP Servers** | Add, edit, delete, and toggle Model Context Protocol servers on/off. Each server shows its type (Local stdio / Remote HTTP), enabled state, and connection details. |
| **Skills** | Browse installed skills from `~/.agents/skills` and enable/disable them. |
| **Permissions** | Manage bash command patterns and external directory allow/deny rules. |

### MCP server toggling

Every MCP server has an `enabled` flag persisted to `kilo.jsonc`:

- **Toolbar** — select a server, then click **Enable** / **Disable**
- **Right-click** — context menu on any server row
- **Double-click** — toggles the selected server's enabled state

The running Kilo app watches `kilo.jsonc` via inotify, so enabling/disabling a server takes effect in real time — no Kilo restart required.

## Config file

Kilo Manager reads and writes:

```
/home/brgjr10/.config/kilo/kilo.jsonc
```

MCP servers are stored under `mcp.servers`, e.g.:

```json
{
  "mcp": {
    "servers": {
      "second-brain": {
        "type": "local",
        "command": ["/home/brgjr10/.local/bin/uv", "run", "--project", "/home/brgjr10/MCP Database/brain-mcp", "python", "-m", "second_brain_mcp"],
        "environment": {
          "SECOND_BRAIN_MCP_TRANSPORT": "sse"
        },
        "enabled": true
      }
    }
  }
}
```

## Requirements

- Python 3
- `ttkbootstrap` (`pip install ttkbootstrap`)
- Running Kilo instance (optional, for real-time config reload)

## Usage

```bash
# From the project directory
python3 kilo_manager.py
```

Or run the packaged AppImage:

```bash
chmod +x kilo_manager-x86_64.AppImage
./kilo_manager-x86_64.AppImage
```

## Building the AppImage

```bash
pip3 install --break-system-packages pyinstaller appimage-builder

# 1. Build the PyInstaller executable
pyinstaller --onefile --windowed kilo_manager.py

# 2. Assemble the AppDir
mkdir -p AppDir/usr/bin
cp dist/kilo_manager AppDir/usr/bin/
cp kilo-manager.desktop AppDir/
cp AppRun AppDir/
chmod +x AppDir/usr/bin/kilo_manager AppDir/AppRun

# 3. Generate and build the AppImage
appimage-builder --generate
appimage-builder
```

The resulting `kilo_manager-x86_64.AppImage` is a self-contained, distribution-independent bundle.

## Project structure

```
kilo-manager/
├── kilo_manager.py      # Main application (tkinter + ttkbootstrap)
├── kilo-manager.desktop # Desktop entry for the AppImage
├── AppRun               # AppImage entrypoint script
├── AppImageBuilder.yml  # AppImage build configuration
├── README.md            # This file
└── .gitignore           # Python/build artifact ignores
```

## License

MIT — use freely, modify as needed.