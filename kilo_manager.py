#!/usr/bin/env python3
"""
Kilo Manager - Desktop GUI for managing Kilo configuration
Built with Python tkinter and ttkbootstrap
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from tkinter import *
from tkinter import ttk, messagebox, filedialog, simpledialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox


def resolve_config_path(cli_path=None):
    if cli_path:
        return Path(cli_path).expanduser()
    env_path = os.environ.get("KILO_CONFIG_PATH")
    if env_path:
        return Path(env_path).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "kilo" / "kilo.jsonc"


def resolve_skills_dir():
    env_path = os.environ.get("KILO_SKILLS_DIR")
    if env_path:
        return Path(env_path).expanduser()
    return Path.home() / ".agents" / "skills"


CONFIG_PATH = resolve_config_path()
SKILLS_DIR = resolve_skills_dir()


class KiloManager:
    def __init__(self, root, config_path=None, skills_dir=None):
        self.root = root
        self.root.title("Kilo Manager")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)

        self.config_path = Path(config_path) if config_path else CONFIG_PATH
        self.skills_dir = Path(skills_dir) if skills_dir else SKILLS_DIR
        self._config_readonly = False
        self.undo_stack = []

        self.config = self.load_config()
        self.setup_ui()
        self.refresh_all()

    def snapshot_config(self):
        return json.loads(json.dumps(self.config))

    def push_undo(self, restore_fn):
        self.undo_stack.append(restore_fn)
        self.undo_stack = self.undo_stack[-1:]

    def _set_undo_enabled(self, enabled):
        if hasattr(self, "undo_menu_index") and hasattr(self, "edit_menu"):
            try:
                self.edit_menu.entryconfig(self.undo_menu_index, state=("normal" if enabled else "disabled"))
            except Exception:
                pass

    def undo_last(self):
        if not self.undo_stack:
            return False
        restore_fn = self.undo_stack.pop()
        restore_fn()
        self._set_undo_enabled(bool(self.undo_stack))
        return True

    def _push_config_undo(self, refresh_fn):
        snapshot = self.snapshot_config()

        def restore(s=snapshot, rf=refresh_fn):
            self.config = s
            if callable(rf):
                rf()

        self.push_undo(restore)
        self._set_undo_enabled(True)

    def load_config(self):
        default = {"mcp": {"servers": {}}, "permission": {"bash": {}, "external_directory": {}}}
        try:
            with open(self.config_path, 'r') as f:
                self._config_readonly = False
                return json.load(f)
        except FileNotFoundError:
            self._config_readonly = False
            return default
        except json.JSONDecodeError as e:
            self._config_readonly = True
            Messagebox.show_error(
                f"Config file is corrupt or invalid JSON and will not be overwritten:\n"
                f"{self.config_path}\n{e}",
                "Config Error",
            )
            return default
        except OSError as e:
            self._config_readonly = True
            Messagebox.show_error(
                f"Failed to read config file and will not be overwritten:\n"
                f"{self.config_path}\n{e}",
                "Config Error",
            )
            return default

    def save_config(self):
        if self._config_readonly:
            Messagebox.show_error(
                "Configuration is read-only because the existing config could not be loaded safely.",
                "Error",
            )
            return False
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self.config_path.parent),
                prefix=self.config_path.name + ".",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, 'w') as f:
                    json.dump(self.config, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, self.config_path)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
            Messagebox.show_info("Configuration saved successfully", "Success")
            return True
        except Exception as e:
            Messagebox.show_error(f"Failed to save config: {e}", "Error")
            return False
    
    def setup_ui(self):
        # Style
        style = tb.Style("darkly")

        # Menu
        menubar = Menu(self.root)
        self.edit_menu = Menu(menubar, tearoff=0)
        self.edit_menu.add_command(label="Undo", command=self.undo_last, accelerator="Ctrl+Z")
        self.undo_menu_index = 0
        self.edit_menu.entryconfig(self.undo_menu_index, state="disabled")
        menubar.add_cascade(label="Edit", menu=self.edit_menu)
        self.root.config(menu=menubar)
        self.root.bind("<Control-z>", lambda e: self.undo_last())
        self.root.bind("<Control-Z>", lambda e: self.undo_last())

        # Main container
        main_frame = tb.Frame(self.root)
        main_frame.pack(fill=BOTH, expand=True)

        # Sidebar
        self.sidebar = tb.Frame(main_frame, width=240, bootstyle="secondary")
        self.sidebar.pack(side=LEFT, fill=Y)
        self.sidebar.pack_propagate(False)
        
        # Sidebar header
        header = tb.Frame(self.sidebar, padding=20)
        header.pack(fill=X)
        tb.Label(header, text="Kilo Manager", font=("Helvetica", 18, "bold"), 
                 bootstyle="inverse-primary").pack(anchor=W)
        tb.Label(header, text="Configuration & Skills", font=("Helvetica", 10),
                 bootstyle="inverse-secondary").pack(anchor=W)
        
        # Navigation
        self.nav_buttons = {}
        nav_items = [
            ("mcp", "MCP Servers", "🔌"),
            ("skills", "Skills", "🧠"),
            ("permissions", "Permissions", "🔐"),
        ]
        
        for key, label, icon in nav_items:
            btn = tb.Button(self.sidebar, text=f"{icon}  {label}",
                          command=lambda k=key: self.switch_tab(k),
                          bootstyle="secondary-outline", width=25)
            btn.pack(fill=X, padx=10, pady=5)
            self.nav_buttons[key] = btn
        
        # Open config folder button
        tb.Separator(self.sidebar).pack(fill=X, padx=10, pady=10)
        tb.Button(self.sidebar, text="📁  Open Config Folder",
                  command=self.open_config_folder,
                  bootstyle="primary", width=25).pack(fill=X, padx=10, pady=5)
        
        # Content area
        self.content = tb.Frame(main_frame, padding=20)
        self.content.pack(side=LEFT, fill=BOTH, expand=True)
        
        # Tab panels
        self.panels = {}
        self.create_mcp_panel()
        self.create_skills_panel()
        self.create_permissions_panel()
        
        # Show first tab
        self.switch_tab("mcp")
    
    def switch_tab(self, tab_name):
        for key, btn in self.nav_buttons.items():
            if key == tab_name:
                btn.configure(bootstyle="primary")
            else:
                btn.configure(bootstyle="secondary-outline")
        
        for panel in self.panels.values():
            panel.pack_forget()
        self.panels[tab_name].pack(fill=BOTH, expand=True)
    
    def create_mcp_panel(self):
        panel = tb.Frame(self.content)
        self.panels["mcp"] = panel
        
        # Header
        header = tb.Frame(panel)
        header.pack(fill=X, pady=(0, 20))
        tb.Label(header, text="MCP Servers", font=("Helvetica", 24, "bold")).pack(side=LEFT)
        tb.Label(header, text="Manage Model Context Protocol servers", 
                 bootstyle="secondary").pack(side=LEFT, padx=10)
        tb.Button(header, text="➕ Add Server", command=self.add_mcp_server,
                  bootstyle="primary").pack(side=RIGHT)
        
        # Toolbar
        toolbar = tb.Frame(panel)
        toolbar.pack(fill=X, pady=(0, 10))
        tb.Button(toolbar, text="➕ Add Server", command=self.add_mcp_server,
                  bootstyle="primary-outline").pack(side=LEFT, padx=(0, 5))
        self.toggle_btn = tb.Button(toolbar, text="Toggle Enabled",
                                    command=self.toggle_selected_mcp,
                                    bootstyle="secondary-outline")
        self.toggle_btn.pack(side=LEFT, padx=(0, 5))
        tb.Label(toolbar, text="Click a server to select; double-click or use Toggle to enable/disable",
                 bootstyle="secondary").pack(side=LEFT, padx=10)

        # Server list
        list_frame = tb.Frame(panel)
        list_frame.pack(fill=BOTH, expand=True)
        self.mcp_tree = tb.Treeview(list_frame, columns=("type", "enabled", "details"), show="tree headings",
                                     bootstyle="secondary", height=15)
        self.mcp_tree.heading("#0", text="Name")
        self.mcp_tree.heading("type", text="Type")
        self.mcp_tree.heading("enabled", text="Enabled")
        self.mcp_tree.heading("details", text="Details")
        self.mcp_tree.column("#0", width=220)
        self.mcp_tree.column("type", width=110)
        self.mcp_tree.column("enabled", width=90, anchor=CENTER)
        self.mcp_tree.column("details", width=420)
        self.mcp_tree.pack(fill=BOTH, expand=True)

        self.mcp_empty_state = tb.Frame(list_frame)
        self.mcp_empty_state.pack_forget()
        tb.Label(self.mcp_empty_state, text="No MCP servers configured",
                 font=("Helvetica", 14), bootstyle="secondary").pack(pady=(40, 10))
        tb.Button(self.mcp_empty_state, text="➕ Add Server", command=self.add_mcp_server,
                  bootstyle="primary").pack()

        # Context menu
        self.mcp_menu = Menu(self.root, tearoff=0)
        self.mcp_menu.add_command(label="Edit", command=self.edit_mcp_server)
        self.mcp_menu.add_command(label="Toggle Enabled", command=self.toggle_selected_mcp)
        self.mcp_menu.add_separator()
        self.mcp_menu.add_command(label="Delete", command=self.delete_mcp_server)
        self.mcp_tree.bind("<Button-3>", self.show_mcp_menu)
        self.mcp_tree.bind("<Double-1>", lambda e: self.toggle_selected_mcp())
        self.mcp_tree.bind("<<TreeviewSelect>>", lambda e: self.update_toggle_btn())
    
    def create_skills_panel(self):
        panel = tb.Frame(self.content)
        self.panels["skills"] = panel
        
        header = tb.Frame(panel)
        header.pack(fill=X, pady=(0, 20))
        tb.Label(header, text="Skills", font=("Helvetica", 24, "bold")).pack(side=LEFT)
        tb.Label(header, text="Available Kilo skills from ~/.agents/skills",
                 bootstyle="secondary").pack(side=LEFT, padx=10)
        tb.Button(header, text="🔄 Refresh", command=self.refresh_skills,
                  bootstyle="secondary").pack(side=RIGHT)
        
        # Skills grid using canvas + scrollbar
        self.skills_canvas = tb.Canvas(panel)
        self.skills_scroll = tb.Scrollbar(panel, orient=VERTICAL, command=self.skills_canvas.yview)
        self.skills_frame = tb.Frame(self.skills_canvas)
        
        self.skills_frame.bind("<Configure>", 
            lambda e: self.skills_canvas.configure(scrollregion=self.skills_canvas.bbox("all")))
        self.skills_canvas.create_window((0, 0), window=self.skills_frame, anchor="nw")
        self.skills_canvas.configure(yscrollcommand=self.skills_scroll.set)
        
        self.skills_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.skills_scroll.pack(side=RIGHT, fill=Y)
    
    def create_permissions_panel(self):
        panel = tb.Frame(self.content)
        self.panels["permissions"] = panel
        
        header = tb.Frame(panel)
        header.pack(fill=X, pady=(0, 20))
        tb.Label(header, text="Permissions", font=("Helvetica", 24, "bold")).pack(side=LEFT)
        tb.Label(header, text="Configure bash and external directory permissions",
                 bootstyle="secondary").pack(side=LEFT, padx=10)
        
        # Bash permissions
        bash_frame = tb.LabelFrame(panel, text="Bash Commands", padding=15)
        bash_frame.pack(fill=BOTH, expand=True, pady=(0, 10))
        
        bash_header = tb.Frame(bash_frame)
        bash_header.pack(fill=X, pady=(0, 10))
        tb.Label(bash_header, text="Bash Permissions", font=("Helvetica", 14, "bold")).pack(side=LEFT)
        tb.Button(bash_header, text="➕ Add", command=self.add_bash_permission,
                  bootstyle="primary-outline").pack(side=RIGHT)

        bash_list = tb.Frame(bash_frame)
        bash_list.pack(fill=BOTH, expand=True)
        self.bash_tree = tb.Treeview(bash_list, columns=("action",), show="tree headings",
                                      bootstyle="secondary", height=8)
        self.bash_tree.heading("#0", text="Command Pattern")
        self.bash_tree.heading("action", text="Action")
        self.bash_tree.column("#0", width=500)
        self.bash_tree.column("action", width=100)
        self.bash_tree.pack(fill=BOTH, expand=True)
        self.bash_empty_state = tb.Frame(bash_list)
        self.bash_empty_state.pack_forget()
        tb.Label(self.bash_empty_state, text="No bash permissions configured",
                 font=("Helvetica", 12), bootstyle="secondary").pack(pady=(20, 8))
        tb.Button(self.bash_empty_state, text="➕ Add", command=self.add_bash_permission,
                  bootstyle="primary-outline").pack()

        self.bash_menu = Menu(self.root, tearoff=0)
        self.bash_menu.add_command(label="Edit", command=self.edit_bash_permission)
        self.bash_menu.add_command(label="Delete", command=self.delete_bash_permission)
        self.bash_tree.bind("<Button-3>", self.show_bash_menu)

        # External directories
        ext_frame = tb.LabelFrame(panel, text="External Directories", padding=15)
        ext_frame.pack(fill=BOTH, expand=True)

        ext_header = tb.Frame(ext_frame)
        ext_header.pack(fill=X, pady=(0, 10))
        tb.Label(ext_header, text="External Directory Permissions", font=("Helvetica", 14, "bold")).pack(side=LEFT)
        tb.Button(ext_header, text="➕ Add", command=self.add_external_permission,
                  bootstyle="primary-outline").pack(side=RIGHT)

        ext_list = tb.Frame(ext_frame)
        ext_list.pack(fill=BOTH, expand=True)
        self.ext_tree = tb.Treeview(ext_list, columns=("action",), show="tree headings",
                                     bootstyle="secondary", height=8)
        self.ext_tree.heading("#0", text="Directory Path")
        self.ext_tree.heading("action", text="Action")
        self.ext_tree.column("#0", width=500)
        self.ext_tree.column("action", width=100)
        self.ext_tree.pack(fill=BOTH, expand=True)
        self.ext_empty_state = tb.Frame(ext_list)
        self.ext_empty_state.pack_forget()
        tb.Label(self.ext_empty_state, text="No external directory permissions configured",
                 font=("Helvetica", 12), bootstyle="secondary").pack(pady=(20, 8))
        tb.Button(self.ext_empty_state, text="➕ Add", command=self.add_external_permission,
                  bootstyle="primary-outline").pack()

        self.ext_menu = Menu(self.root, tearoff=0)
        self.ext_menu.add_command(label="Edit", command=self.edit_external_permission)
        self.ext_menu.add_command(label="Delete", command=self.delete_external_permission)
        self.ext_tree.bind("<Button-3>", self.show_ext_menu)
    
    def refresh_all(self):
        self.refresh_mcp_list()
        self.refresh_skills()
        self.refresh_permissions()
    
    def refresh_mcp_list(self):
        for item in self.mcp_tree.get_children():
            self.mcp_tree.delete(item)

        servers = self.config.get("mcp", {}).get("servers", {})
        for name, server in servers.items():
            if server.get("type") == "local":
                details = " ".join(server.get("command", []))
                if server.get("environment"):
                    details += " | Env: " + ", ".join(f"{k}={v}" for k, v in server["environment"].items())
                s_type = "Local (stdio)"
            else:
                details = server.get("url", "")
                if server.get("headers"):
                    details += " | Headers: " + ", ".join(f"{k}: {v}" for k, v in server["headers"].items())
                s_type = "Remote (HTTP)"

            enabled = server.get("enabled", True)
            enabled_text = "Enabled" if enabled else "Disabled"
            enabled_tag = "enabled" if enabled else "disabled"

            self.mcp_tree.insert("", END, text=name, values=(s_type, enabled_text, details),
                                 iid=name, tags=(enabled_tag,))

        self.mcp_tree.tag_configure("enabled", foreground="#4ade80")
        self.mcp_tree.tag_configure("disabled", foreground="#f87171")
        self.update_mcp_empty_state()

    def update_mcp_empty_state(self):
        if not hasattr(self, "mcp_empty_state"):
            return
        if self.mcp_tree.get_children():
            self.mcp_empty_state.pack_forget()
        else:
            self.mcp_empty_state.pack(expand=True)
    
    def refresh_skills(self):
        for widget in self.skills_frame.winfo_children():
            widget.destroy()
        
        skills = self.get_skills()
        
        if not skills:
            tb.Label(self.skills_frame, text="No skills found in ~/.agents/skills",
                     bootstyle="secondary").pack(pady=50)
            return
        
        # Create grid
        for i, skill in enumerate(skills):
            row = i // 3
            col = i % 3

            card = tb.Frame(self.skills_frame, bootstyle="secondary", padding=15)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            # Name and status
            top = tb.Frame(card)
            top.pack(fill=X)
            tb.Label(top, text=skill["name"].replace("skill-", ""),
                     font=("Helvetica", 14, "bold")).pack(side=LEFT)

            enabled = skill.get("enabled", False)
            status = "Detected (SKILL.md)" if enabled else "No SKILL.md"
            tb.Label(top, text=status, bootstyle="success" if enabled else "secondary").pack(side=RIGHT)

            # Description
            if skill.get("description"):
                tb.Label(card, text=skill["description"], wraplength=250,
                         bootstyle="secondary").pack(fill=X, pady=(10, 0))

            # Path
            tb.Label(card, text=skill["path"], font=("Helvetica", 9),
                     bootstyle="secondary").pack(fill=X, pady=(10, 0))

        # Configure grid weights
        for i in range(3):
            self.skills_frame.columnconfigure(i, weight=1)
    
    def get_skills(self):
        skills = []
        if self.skills_dir.exists():
            for entry in self.skills_dir.iterdir():
                if entry.is_dir():
                    skill_md = entry / "SKILL.md"
                    description = ""
                    enabled = False
                    if skill_md.exists():
                        content = skill_md.read_text()
                        # Extract description from first paragraph
                        lines = content.strip().split('\n')
                        for line in lines:
                            if line.startswith('#'):
                                continue
                            if line.strip():
                                description = line.strip()
                                break
                        enabled = True
                    skills.append({
                        "name": entry.name,
                        "description": description,
                        "enabled": enabled,
                        "path": str(entry)
                    })
        return skills
    
    def refresh_permissions(self):
        for item in self.bash_tree.get_children():
            self.bash_tree.delete(item)
        for item in self.ext_tree.get_children():
            self.ext_tree.delete(item)

        bash_perms = self.config.get("permission", {}).get("bash", {})
        for cmd, action in bash_perms.items():
            self.bash_tree.insert("", END, text=cmd, values=(action,), iid=cmd)

        ext_perms = self.config.get("permission", {}).get("external_directory", {})
        for path, action in ext_perms.items():
            self.ext_tree.insert("", END, text=path, values=(action,), iid=path)
        self.update_permissions_empty_states()

    def update_permissions_empty_states(self):
        if hasattr(self, "bash_empty_state"):
            if self.bash_tree.get_children():
                self.bash_empty_state.pack_forget()
            else:
                self.bash_empty_state.pack(expand=True)
        if hasattr(self, "ext_empty_state"):
            if self.ext_tree.get_children():
                self.ext_empty_state.pack_forget()
            else:
                self.ext_empty_state.pack(expand=True)
    
    # MCP Server methods
    def add_mcp_server(self):
        self.mcp_dialog()
    
    def edit_mcp_server(self):
        selection = self.mcp_tree.selection()
        if not selection:
            return
        name = selection[0]
        servers = self.config.get("mcp", {}).get("servers", {})
        self.mcp_dialog(servers.get(name), name)
    
    def mcp_dialog(self, server=None, edit_name=None):
        dialog = tb.Toplevel(self.root)
        dialog.title("Add MCP Server" if not server else "Edit MCP Server")
        dialog.geometry("500x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 250
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 250
        dialog.geometry(f"+{x}+{y}")
        
        # Form
        frame = tb.Frame(dialog, padding=20)
        frame.pack(fill=BOTH, expand=True)
        
        # Name
        tb.Label(frame, text="Server Name").pack(anchor=W)
        name_var = tb.StringVar(value=edit_name or "")
        name_entry = tb.Entry(frame, textvariable=name_var)
        name_entry.pack(fill=X, pady=(5, 15))
        
        # Enabled
        enabled_frame = tb.Frame(frame)
        enabled_frame.pack(fill=X, pady=(0, 15))
        enabled_var = tb.BooleanVar(value=server.get("enabled", True) if server else True)
        tb.Checkbutton(enabled_frame, text="Enabled (kilo will connect to this server)",
                       variable=enabled_var, bootstyle="round-toggle").pack(side=LEFT)
        
        # Type
        tb.Label(frame, text="Type").pack(anchor=W)
        type_var = tb.StringVar(value=server.get("type", "local") if server else "local")
        type_combo = tb.Combobox(frame, textvariable=type_var, values=["local", "remote"],
                                  state="readonly")
        type_combo.pack(fill=X, pady=(5, 15))
        
        # Dynamic fields container
        fields_frame = tb.Frame(frame)
        fields_frame.pack(fill=BOTH, expand=True)

        fields_frame.cmd_var = tb.StringVar()
        fields_frame.url_var = tb.StringVar()
        fields_frame.env_text = None
        fields_frame.headers_text = None

        def update_fields(*args):
            for widget in fields_frame.winfo_children():
                widget.destroy()
            fields_frame.env_text = None
            fields_frame.headers_text = None

            if type_var.get() == "local":
                tb.Label(fields_frame, text="Command (space-separated)").pack(anchor=W)
                fields_frame.cmd_var.set(" ".join(server.get("command", [])) if server else "")
                tb.Entry(fields_frame, textvariable=fields_frame.cmd_var).pack(fill=X, pady=(5, 15))

                tb.Label(fields_frame, text="Environment Variables (KEY=VALUE, one per line)").pack(anchor=W)
                env_text = tb.Text(fields_frame, height=6)
                env_text.pack(fill=X, pady=(5, 15))
                if server and server.get("environment"):
                    env_text.insert("1.0", "\n".join(f"{k}={v}" for k, v in server["environment"].items()))
                fields_frame.env_text = env_text
            else:
                tb.Label(fields_frame, text="URL").pack(anchor=W)
                fields_frame.url_var.set(server.get("url", "") if server else "")
                tb.Entry(fields_frame, textvariable=fields_frame.url_var).pack(fill=X, pady=(5, 15))

                tb.Label(fields_frame, text="Headers (KEY: VALUE, one per line)").pack(anchor=W)
                headers_text = tb.Text(fields_frame, height=6)
                headers_text.pack(fill=X, pady=(5, 15))
                if server and server.get("headers"):
                    headers_text.insert("1.0", "\n".join(f"{k}: {v}" for k, v in server["headers"].items()))
                fields_frame.headers_text = headers_text

        type_var.trace("w", update_fields)
        update_fields()
        
        # Buttons
        btn_frame = tb.Frame(frame)
        btn_frame.pack(fill=X, pady=(20, 0))

        def save():
            name = name_var.get().strip()
            s_type = type_var.get()
            cmd = fields_frame.cmd_var.get().strip() if hasattr(fields_frame, "cmd_var") else ""
            url = fields_frame.url_var.get().strip() if hasattr(fields_frame, "url_var") else ""
            servers = self.config.get("mcp", {}).get("servers", {})
            existing = {n for n in servers.keys() if n != edit_name}
            if not name:
                Messagebox.show_error(
                    "Server name is required — enter a unique name for this MCP server.",
                    "Error",
                )
                return
            if name in existing:
                Messagebox.show_error(
                    f"Server name '{name}' already exists — choose a different unique server name.",
                    "Error",
                )
                return
            if s_type == "local" and not cmd:
                Messagebox.show_error(
                    "Command is required for local servers — e.g. `npx @modelcontextprotocol/server-filesystem`",
                    "Error",
                )
                return
            if s_type == "remote" and not url:
                Messagebox.show_error(
                    "URL is required for remote servers — e.g. `https://...`",
                    "Error",
                )
                return

            if "mcp" not in self.config:
                self.config["mcp"] = {"servers": {}}
            if "servers" not in self.config["mcp"]:
                self.config["mcp"]["servers"] = {}
            servers = self.config["mcp"]["servers"]

            server_config = {"type": s_type, "enabled": enabled_var.get()}

            if s_type == "local":
                server_config["command"] = cmd.split()

                env_text = fields_frame.env_text.get("1.0", END).strip() if fields_frame.env_text else ""
                if env_text:
                    env = {}
                    for line in env_text.split('\n'):
                        if '=' in line:
                            k, v = line.split('=', 1)
                            env[k.strip()] = v.strip()
                    server_config["environment"] = env
            else:
                server_config["url"] = url

                headers_text = fields_frame.headers_text.get("1.0", END).strip() if fields_frame.headers_text else ""
                if headers_text:
                    headers = {}
                    for line in headers_text.split('\n'):
                        if ':' in line:
                            k, v = line.split(':', 1)
                            headers[k.strip()] = v.strip()
                    server_config["headers"] = headers

            if edit_name and edit_name != name and edit_name in servers:
                del servers[edit_name]
            servers[name] = server_config

            if not self.save_config():
                return
            self.refresh_mcp_list()
            dialog.destroy()

        tb.Button(btn_frame, text="Cancel", command=dialog.destroy,
                  bootstyle="secondary").pack(side=RIGHT, padx=5)
        tb.Button(btn_frame, text="Save", command=save,
                  bootstyle="primary").pack(side=RIGHT)
    
    def delete_mcp_server(self):
        selection = self.mcp_tree.selection()
        if not selection:
            return
        name = selection[0]
        if Messagebox.yesno(f"Delete MCP server '{name}'?", "Confirm Delete"):
            self._push_config_undo(self.refresh_mcp_list)
            del self.config["mcp"]["servers"][name]
            if not self.save_config():
                self.undo_last()
                self.refresh_mcp_list()
                return
            self.refresh_mcp_list()

    def update_toggle_btn(self):
        selection = self.mcp_tree.selection()
        if selection:
            name = selection[0]
            server = self.config.get("mcp", {}).get("servers", {}).get(name, {})
            enabled = server.get("enabled", True)
            self.toggle_btn.configure(text="Disable" if enabled else "Enable")
        else:
            self.toggle_btn.configure(text="Toggle Enabled")

    def toggle_selected_mcp(self):
        selection = self.mcp_tree.selection()
        if not selection:
            return
        name = selection[0]
        self._push_config_undo(self.refresh_mcp_list)
        servers = self.config.setdefault("mcp", {}).setdefault("servers", {})
        server = servers.get(name, {})
        server["enabled"] = not server.get("enabled", True)
        if not self.save_config():
            self.undo_last()
            self.refresh_mcp_list()
            return
        self.refresh_mcp_list()
        try:
            self.mcp_tree.selection_set(name)
            self.mcp_tree.focus(name)
        except Exception:
            pass
    
    def show_mcp_menu(self, event):
        item = self.mcp_tree.identify_row(event.y)
        if item:
            self.mcp_tree.selection_set(item)
            self.mcp_menu.post(event.x_root, event.y_root)
    
    # Skills methods
    def toggle_skill(self, skill):
        # Skills are managed by Kilo directly; UI shows detection status only.
        pass
    
    # Permissions methods
    def add_bash_permission(self):
        cmd = simpledialog.askstring("Add Bash Permission", "Command pattern (e.g., npm run *):")
        if not cmd:
            return
        action = simpledialog.askstring("Action", "allow/deny/ask:", initialvalue="allow")
        if action is None:
            return
        if action not in ("allow", "deny", "ask"):
            Messagebox.show_error(
                "Action must be one of: allow, deny, ask (expected value for bash command permission action).",
                "Error",
            )
            return
        self._push_config_undo(self.refresh_permissions)
        self.config.setdefault("permission", {}).setdefault("bash", {})[cmd] = action
        if not self.save_config():
            self.undo_last()
            self.refresh_permissions()
            return
        self.refresh_permissions()

    def edit_bash_permission(self):
        selection = self.bash_tree.selection()
        if not selection:
            return
        cmd = selection[0]
        action = simpledialog.askstring("Edit Action", f"Action for '{cmd}':",
                                         initialvalue=self.config["permission"]["bash"][cmd])
        if action is None:
            return
        if action not in ("allow", "deny", "ask"):
            Messagebox.show_error(
                "Action must be one of: allow, deny, ask (expected value for bash command permission action).",
                "Error",
            )
            return
        self._push_config_undo(self.refresh_permissions)
        self.config["permission"]["bash"][cmd] = action
        if not self.save_config():
            self.undo_last()
            self.refresh_permissions()
            return
        self.refresh_permissions()

    def delete_bash_permission(self):
        selection = self.bash_tree.selection()
        if not selection:
            return
        cmd = selection[0]
        if Messagebox.yesno(f"Delete bash permission for '{cmd}'?", "Confirm Delete"):
            self._push_config_undo(self.refresh_permissions)
            del self.config["permission"]["bash"][cmd]
            if not self.save_config():
                self.undo_last()
                self.refresh_permissions()
                return
            self.refresh_permissions()

    def show_bash_menu(self, event):
        item = self.bash_tree.identify_row(event.y)
        if item:
            self.bash_tree.selection_set(item)
            self.bash_menu.post(event.x_root, event.y_root)

    def add_external_permission(self):
        path = filedialog.askdirectory(title="Select Directory")
        if not path:
            return
        action = simpledialog.askstring("Action", "allow/deny:", initialvalue="allow")
        if action is None:
            return
        if action not in ("allow", "deny"):
            Messagebox.show_error(
                "Action must be one of: allow, deny (expected value for external directory permission action).",
                "Error",
            )
            return
        self._push_config_undo(self.refresh_permissions)
        self.config.setdefault("permission", {}).setdefault("external_directory", {})[path] = action
        if not self.save_config():
            self.undo_last()
            self.refresh_permissions()
            return
        self.refresh_permissions()

    def edit_external_permission(self):
        selection = self.ext_tree.selection()
        if not selection:
            return
        path = selection[0]
        action = simpledialog.askstring("Edit Action", f"Action for '{path}':",
                                         initialvalue=self.config["permission"]["external_directory"][path])
        if action is None:
            return
        if action not in ("allow", "deny"):
            Messagebox.show_error(
                "Action must be one of: allow, deny (expected value for external directory permission action).",
                "Error",
            )
            return
        self._push_config_undo(self.refresh_permissions)
        self.config["permission"]["external_directory"][path] = action
        if not self.save_config():
            self.undo_last()
            self.refresh_permissions()
            return
        self.refresh_permissions()

    def delete_external_permission(self):
        selection = self.ext_tree.selection()
        if not selection:
            return
        path = selection[0]
        if Messagebox.yesno(f"Delete external permission for '{path}'?", "Confirm Delete"):
            self._push_config_undo(self.refresh_permissions)
            del self.config["permission"]["external_directory"][path]
            if not self.save_config():
                self.undo_last()
                self.refresh_permissions()
                return
            self.refresh_permissions()
    
    def show_ext_menu(self, event):
        item = self.ext_tree.identify_row(event.y)
        if item:
            self.ext_tree.selection_set(item)
            self.ext_menu.post(event.x_root, event.y_root)
    
    def open_config_folder(self):
        subprocess.run(["xdg-open", str(self.config_path.parent)])


def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--config", help="Path to kilo config file (json/jsonc)")
    args = parser.parse_args()

    root = tb.Window(themename="darkly")
    app = KiloManager(root, config_path=resolve_config_path(args.config) if args.config else CONFIG_PATH)
    root.mainloop()


if __name__ == "__main__":
    main()