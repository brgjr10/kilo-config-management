# Kilo Manager — Structure & QA Guide

This document describes the code structure of `kilo-manager` so you can run QA against it.

## Overview

`kilo-manager` is a single-file Python desktop GUI (`kilo_manager.py`, 640 lines) built with tkinter + ttkbootstrap that manages Kilo configuration stored in `/home/brgjr10/.config/kilo/kilo.jsonc`.

The running Kilo binary watches `kilo.jsonc` via inotify ("File Watcher"), so config changes made here take effect in real time.

## Runtime entry point

```
python3 kilo_manager.py
```

- `main()` (line 633) creates a `tb.Window(themename="darkly")`, instantiates `KiloManager`, and starts `root.mainloop()`.
- `KiloManager.__init__` (line 24): loads config, builds UI, calls `refresh_all()`.

## Data model

Config is read/written wholesale to `CONFIG_PATH` (`/home/brgjr10/.config/kilo/kilo.jsonc`). Stored in `self.config` as a plain dict:

```json
{
  "mcp": { "servers": { "<name>": { "type": "local"|"remote", "enabled": bool, ... } } },
  "permission": {
    "bash": { "<cmd pattern>": "allow|deny|ask" },
    "external_directory": { "<path>": "allow|deny" }
  }
}
```

No schema validation; missing keys default gracefully via `.get()` with fallbacks.

## Class: KiloManager

### UI setup

| Method | Lines | Responsibility |
|--------|-------|----------------|
| `setup_ui` | 50–103 | Top-level layout: sidebar (nav + config folder), content area with three panels, shows MCP tab first |
| `switch_tab` | 105–114 | Swaps visible panel; updates nav button styles (primary vs secondary-outline) |
| `create_mcp_panel` | 116–162 | MCP Servers tab: header, toolbar, Treeview list (columns: Name/Type/Enabled/Details), context menu, bindings |
| `create_skills_panel` | 164–187 | Skills tab: header, refresh button, scrollable 3-column grid of skill cards |
| `create_permissions_panel` | 189–243 | Permissions tab: Bash commands + External directories Treeviews, each with Add/Edit/Delete context menus |

### Refresh (read) methods

| Method | Lines | Source | Output |
|--------|-------|--------|--------|
| `refresh_all` | 245–248 | — | Calls all three refresh methods |
| `refresh_mcp_list` | 250–275 | `self.config["mcp"]["servers"]` | Populates `self.mcp_tree`; tags rows `enabled` (green) / `disabled` (red) |
| `refresh_skills` | 277–320 | `get_skills()` → `~/.agents/skills/*/` | Clears and rebuilds skill card grid |
| `refresh_permissions` | 349–361 | `self.config["permission"]` | Populates `self.bash_tree` and `self.ext_tree` |

### MCP server lifecycle

| Method | Lines | Trigger | Behavior |
|--------|-------|---------|----------|
| `add_mcp_server` | 364–365 | Toolbar/header "Add Server" | Opens `mcp_dialog()` (add mode) |
| `edit_mcp_server` | 367–373 | Context menu "Edit" | Opens `mcp_dialog(server, name)` (edit mode) |
| `mcp_dialog` | 375–508 | Add/Edit | Modal `Toplevel` form: Name, Enabled toggle, Type (local/remote), dynamic fields (command/env or url/headers), Save/Cancel |
| `delete_mcp_server` | 510–518 | Context menu "Delete" | Confirms, removes from config, saves, refreshes |
| `toggle_selected_mcp` | 530–541 | Toolbar button, double-click, context menu | Flips `enabled` on selected server, saves, refreshes, re-selects row |
| `update_toggle_btn` | 520–528 | Treeview select event | Updates toolbar button text to Enable/Disable |

### Skills

| Method | Lines | Notes |
|--------|-------|-------|
| `get_skills` | 322–347 | Scans `SKILLS_DIR`; a skill is "enabled" if `SKILL.md` exists; description = first non-heading line |
| `toggle_skill` | 550–552 | No-op (skills managed by Kilo directly); toggle UI exists but does nothing |

### Permissions lifecycle

| Method | Lines | Scope |
|--------|-------|-------|
| `add_bash_permission` / `edit_bash_permission` / `delete_bash_permission` | 555–590 | Bash command patterns (allow/deny/ask) |
| `add_external_permission` / `edit_external_permission` / `delete_external_permission` | 592–621 | External directory paths (allow/deny) |
| `show_bash_menu` / `show_ext_menu` | 586–590 / 623–627 | Right-click context menus |
| `open_config_folder` | 629–630 | `xdg-open` on config dir |

### Config persistence

| Method | Lines | Behavior |
|--------|-------|----------|
| `load_config` | 34–40 | Reads `kilo.jsonc`; on failure returns default skeleton and shows error dialog |
| `save_config` | 42–48 | Writes `self.config` to `kilo.jsonc` (indent=2); shows success/error dialog |

## Key UI widgets

- `self.mcp_tree` — Treeview, iid = server name, columns `(type, enabled, details)`
- `self.bash_tree` / `self.ext_tree` — Treeviews, iid = command pattern / directory path
- `self.toggle_btn` — Toolbar button whose text flips between "Enable"/"Disable" based on selection
- `self.mcp_menu` / `self.bash_menu` / `self.ext_menu` — Right-click context menus (`tearoff=0`)
- `self.skills_canvas` / `self.skills_frame` — Scrollable canvas grid for skill cards

## Event bindings

| Widget | Event | Handler |
|--------|-------|---------|
| `mcp_tree` | `<Button-3>` (right-click) | `show_mcp_menu` |
| `mcp_tree` | `<Double-1>` | `toggle_selected_mcp` |
| `mcp_tree` | `<<TreeviewSelect>>` | `update_toggle_btn` |
| `bash_tree` / `ext_tree` | `<Button-3>` | `show_bash_menu` / `show_ext_menu` |

## External dependencies

- Python 3 standard library: `json`, `os`, `subprocess`, `sys`, `pathlib`, `tkinter`
- `ttkbootstrap` (theme + `Messagebox`)
- `xdg-open` (open config folder)
- Kilo binary with inotify file watcher on `kilo.jsonc` (real-time reload)

## QA focus areas

1. **Config round-trip**: add → edit → delete → toggle an MCP server; verify `kilo.jsonc` reflects changes and Kilo picks them up (inotify).
2. **Type switching**: in `mcp_dialog`, switching local↔remote swaps fields (command/env → url/headers).
3. **Validation**: empty name, empty command (local), empty url (remote) show error dialogs and abort save.
4. **Rename server**: editing name deletes old key before writing new one.
5. **Empty states**: missing `kilo.jsonc`, empty skills dir, empty permission lists.
6. **Tab switching**: nav buttons style correctly; only one panel visible at a time.
7. **Permissions actions**: allow/deny/ask for bash; allow/deny for external dirs.

## Project files

| File | Purpose |
|------|---------|
| `kilo_manager.py` | Application source (single file) |
| `README.md` | User documentation |
| `kilo-manager.desktop` | Desktop entry for AppImage |
| `AppRun` | AppImage entrypoint shell script |
| `AppImageBuilder.yml` | AppImage build config |
| `.gitignore` | Python/build artifact ignores |
| `test-appdir/` | Staged AppDir for AppImage builds |
