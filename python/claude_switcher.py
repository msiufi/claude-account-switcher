#!/usr/bin/env python3
"""
Claude Switcher — cambia de cuenta en Claude Desktop sin volver a iniciar sesión.

Cómo funciona:
  Claude Desktop guarda tu sesión (cookies, tokens, preferencias) en su carpeta
  de datos. Esta app guarda una copia de esa carpeta por cada cuenta ("perfil")
  y, al cambiar, cierra Claude, intercambia las carpetas y lo vuelve a abrir.
  Cada cuenta inicia sesión una sola vez; después el cambio es instantáneo.

Uso:
  python3 claude_switcher.py            -> abre la ventana
  python3 claude_switcher.py list       -> lista perfiles
  python3 claude_switcher.py save NOMBRE  -> guarda la sesión actual como NOMBRE
  python3 claude_switcher.py switch NOMBRE
  python3 claude_switcher.py new NOMBRE   -> cuenta nueva (Claude se abre limpio para iniciar sesión)
  python3 claude_switcher.py rename VIEJO NUEVO
  python3 claude_switcher.py delete NOMBRE

Solo usa la biblioteca estándar de Python 3.8+ (tkinter para la ventana).
"""

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

SYSTEM = platform.system()  # "Darwin", "Windows", "Linux"
HOME = Path.home()

# Archivos que se comparten entre todas las cuentas (no se intercambian).
# claude_desktop_config.json contiene tus servidores MCP / extensiones.
SHARED_FILES = ["claude_desktop_config.json"]


# --------------------------------------------------------------------------- #
# Rutas
# --------------------------------------------------------------------------- #
def _candidate_data_dirs():
    if SYSTEM == "Darwin":
        return [HOME / "Library" / "Application Support" / "Claude"]
    if SYSTEM == "Windows":
        appdata = Path(os.environ.get("APPDATA", HOME / "AppData" / "Roaming"))
        local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData" / "Local"))
        cands = [appdata / "Claude"]
        # Instalación MSIX / Microsoft Store
        pkgs = local / "Packages"
        if pkgs.exists():
            for p in pkgs.glob("Claude_*"):
                cands.append(p / "LocalCache" / "Roaming" / "Claude")
        return cands
    return [HOME / ".config" / "Claude"]


def switcher_home():
    if SYSTEM == "Darwin":
        base = HOME / "Library" / "Application Support" / "Claude-Switcher"
    elif SYSTEM == "Windows":
        base = Path(os.environ.get("APPDATA", HOME / "AppData" / "Roaming")) / "Claude-Switcher"
    else:
        base = HOME / ".config" / "Claude-Switcher"
    base.mkdir(parents=True, exist_ok=True)
    (base / "profiles").mkdir(exist_ok=True)
    return base


STATE_FILE = switcher_home() / "state.json"
PROFILES_DIR = switcher_home() / "profiles"


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"active": None, "data_dir": None, "launch_cmd": None, "order": []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def claude_data_dir(state):
    if state.get("data_dir"):
        return Path(state["data_dir"])
    cands = _candidate_data_dirs()
    for c in cands:
        if c.exists():
            return c
    return cands[0]


# --------------------------------------------------------------------------- #
# Proceso de Claude
# --------------------------------------------------------------------------- #
def claude_running():
    try:
        if SYSTEM == "Darwin":
            r = subprocess.run(["pgrep", "-x", "Claude"], capture_output=True)
            return r.returncode == 0
        if SYSTEM == "Windows":
            r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq claude.exe", "/NH"],
                               capture_output=True, text=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return "claude.exe" in r.stdout.lower()
        r = subprocess.run(["pgrep", "-f", "-i", "claude-desktop|/Claude"], capture_output=True)
        return r.returncode == 0
    except Exception:
        return False


def quit_claude(timeout=20):
    if not claude_running():
        return True
    if SYSTEM == "Darwin":
        subprocess.run(["osascript", "-e", 'tell application "Claude" to quit'], capture_output=True)
    elif SYSTEM == "Windows":
        subprocess.run(["taskkill", "/IM", "claude.exe"], capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        subprocess.run(["pkill", "-f", "-i", "claude-desktop"], capture_output=True)

    deadline = time.time() + timeout
    while time.time() < deadline:
        if not claude_running():
            time.sleep(1.0)  # deja que suelte los archivos
            return True
        time.sleep(0.5)

    # Forzar si no cerró solo
    if SYSTEM == "Darwin":
        subprocess.run(["pkill", "-x", "Claude"], capture_output=True)
    elif SYSTEM == "Windows":
        subprocess.run(["taskkill", "/F", "/IM", "claude.exe"], capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        subprocess.run(["pkill", "-9", "-f", "-i", "claude-desktop"], capture_output=True)
    time.sleep(1.5)
    return not claude_running()


def launch_claude(state):
    cmd = state.get("launch_cmd")
    try:
        if cmd:
            subprocess.Popen(cmd, shell=True)
            return
        if SYSTEM == "Darwin":
            subprocess.Popen(["open", "-a", "Claude"])
        elif SYSTEM == "Windows":
            local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData" / "Local"))
            exe = local / "AnthropicClaude" / "claude.exe"
            if exe.exists():
                subprocess.Popen([str(exe)])
            else:
                # Instalación MSIX / Store: buscar su AppID en el menú Inicio
                ps = ("$a=(Get-StartApps | Where-Object {$_.Name -eq 'Claude'} | "
                      "Select-Object -First 1).AppID; if($a){Start-Process "
                      "\"shell:AppsFolder\\$a\"}")
                subprocess.Popen(["powershell", "-NoProfile", "-Command", ps],
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            subprocess.Popen(["claude-desktop"])
    except Exception as e:
        raise RuntimeError(f"No pude abrir Claude automáticamente ({e}). Ábrelo a mano.")


# --------------------------------------------------------------------------- #
# Perfiles
# --------------------------------------------------------------------------- #
def _valid(name):
    name = name.strip()
    if not name or not re.fullmatch(r"[\w .@+\-]{1,60}", name) or name in (".", ".."):
        raise ValueError("Nombre inválido. Usa letras, números, espacios, . @ + - _")
    return name


def list_profiles(state):
    names = {p.name for p in PROFILES_DIR.iterdir() if p.is_dir()}
    if state.get("active"):
        names.add(state["active"])
    order = [n for n in state.get("order", []) if n in names]
    order += sorted(names - set(order))
    return order


def _shared_snapshot(data_dir):
    snap = {}
    for f in SHARED_FILES:
        p = data_dir / f
        if p.exists():
            snap[f] = p.read_bytes()
    return snap


def _restore_shared(data_dir, snap):
    data_dir.mkdir(parents=True, exist_ok=True)
    for f, content in snap.items():
        (data_dir / f).write_bytes(content)


def save_current_as(state, name):
    """Registra la sesión que está abierta ahora mismo como el perfil `name`."""
    name = _valid(name)
    if state.get("active") and state["active"] != name:
        raise ValueError(f"La sesión actual ya está registrada como '{state['active']}'. "
                         f"Usa 'renombrar' si quieres cambiarle el nombre.")
    state["active"] = name
    state.setdefault("order", [])
    if name not in state["order"]:
        state["order"].append(name)
    save_state(state)


def _stash_active(state, data_dir):
    """Mueve la carpeta de datos actual al almacén del perfil activo."""
    active = state.get("active")
    if not data_dir.exists():
        return
    if not active:
        # Sesión sin registrar: no la perdemos, se guarda como respaldo.
        active = "sin-nombre-" + time.strftime("%Y%m%d-%H%M%S")
        state["active"] = active
        state.setdefault("order", []).append(active)
    dest = PROFILES_DIR / active
    if dest.exists():
        shutil.rmtree(dest)
    shutil.move(str(data_dir), str(dest))


def switch_to(state, name, fresh=False):
    """Cambia a `name`. Si fresh=True crea una cuenta nueva (Claude abre limpio)."""
    name = _valid(name)
    data_dir = claude_data_dir(state)
    target = PROFILES_DIR / name

    if not fresh and name == state.get("active"):
        if not claude_running():
            launch_claude(state)
        return
    if fresh and (target.exists() or name == state.get("active")):
        raise ValueError(f"Ya existe un perfil llamado '{name}'.")
    if not fresh and not target.exists():
        raise ValueError(f"No existe el perfil '{name}'.")

    if not quit_claude():
        raise RuntimeError("Claude no se cerró. Ciérralo manualmente y reintenta.")

    shared = _shared_snapshot(data_dir) if data_dir.exists() else {}
    _stash_active(state, data_dir)

    if fresh:
        data_dir.mkdir(parents=True, exist_ok=True)
    else:
        shutil.move(str(target), str(data_dir))
    _restore_shared(data_dir, shared)

    state["active"] = name
    state.setdefault("order", [])
    if name not in state["order"]:
        state["order"].append(name)
    save_state(state)
    launch_claude(state)


def rename_profile(state, old, new):
    old, new = _valid(old), _valid(new)
    if new in list_profiles(state):
        raise ValueError(f"Ya existe '{new}'.")
    if state.get("active") == old:
        state["active"] = new
    elif (PROFILES_DIR / old).exists():
        (PROFILES_DIR / old).rename(PROFILES_DIR / new)
    else:
        raise ValueError(f"No existe '{old}'.")
    state["order"] = [new if n == old else n for n in state.get("order", [])]
    save_state(state)


def delete_profile(state, name):
    name = _valid(name)
    if state.get("active") == name:
        raise ValueError("No puedes borrar la cuenta activa. Cambia a otra primero.")
    p = PROFILES_DIR / name
    if p.exists():
        shutil.rmtree(p)
    state["order"] = [n for n in state.get("order", []) if n != name]
    save_state(state)


# --------------------------------------------------------------------------- #
# Interfaz gráfica
# --------------------------------------------------------------------------- #
def run_gui():
    import tkinter as tk
    from tkinter import messagebox, simpledialog

    BG, CARD, FG, MUTED, ACCENT = "#1f1e1d", "#2b2a27", "#f5f4ef", "#a8a69e", "#d97757"

    root = tk.Tk()
    root.title("Claude Switcher")
    root.configure(bg=BG)
    root.geometry("360x480")
    root.minsize(320, 380)

    header = tk.Frame(root, bg=BG)
    header.pack(fill="x", padx=18, pady=(18, 6))
    tk.Label(header, text="Cuentas de Claude", bg=BG, fg=FG,
             font=("Helvetica", 16, "bold")).pack(anchor="w")
    status = tk.Label(header, text="", bg=BG, fg=MUTED, font=("Helvetica", 10))
    status.pack(anchor="w", pady=(2, 0))

    list_frame = tk.Frame(root, bg=BG)
    list_frame.pack(fill="both", expand=True, padx=12, pady=6)

    def busy(msg):
        status.config(text=msg)
        root.config(cursor="watch")
        root.update()

    def done():
        root.config(cursor="")
        refresh()

    def do(fn, msg):
        busy(msg)
        try:
            fn()
        except Exception as e:
            messagebox.showerror("Claude Switcher", str(e))
        finally:
            done()

    def ask_name(title, prompt, initial=""):
        return simpledialog.askstring(title, prompt, initialvalue=initial, parent=root)

    def on_switch(name):
        st = load_state()
        do(lambda: switch_to(st, name), f"Cambiando a {name}…")

    def on_menu(event, name):
        m = tk.Menu(root, tearoff=0)
        m.add_command(label="Renombrar…", command=lambda: on_rename(name))
        m.add_command(label="Eliminar", command=lambda: on_delete(name))
        m.tk_popup(event.x_root, event.y_root)

    def on_rename(name):
        new = ask_name("Renombrar", f"Nuevo nombre para '{name}':", name)
        if new and new != name:
            st = load_state()
            do(lambda: rename_profile(st, name, new), "Renombrando…")

    def on_delete(name):
        if messagebox.askyesno("Eliminar", f"¿Eliminar la sesión guardada de '{name}'?\n"
                               "Tendrás que volver a iniciar sesión en esa cuenta."):
            st = load_state()
            do(lambda: delete_profile(st, name), "Eliminando…")

    def on_new():
        st = load_state()
        if not st.get("active") and claude_data_dir(st).exists():
            cur = ask_name("Guardar cuenta actual",
                           "Primero, ¿cómo se llama la cuenta con la que estás ahora?\n"
                           "(ej. personal, trabajo, tu email)")
            if not cur:
                return
            try:
                save_current_as(st, cur)
            except Exception as e:
                messagebox.showerror("Claude Switcher", str(e)); return
        name = ask_name("Nueva cuenta", "Nombre para la nueva cuenta:")
        if name:
            st = load_state()
            do(lambda: switch_to(st, name, fresh=True), "Abriendo Claude limpio para iniciar sesión…")

    def refresh():
        for w in list_frame.winfo_children():
            w.destroy()
        st = load_state()
        names = list_profiles(st)
        running = claude_running()
        status.config(text=("Claude abierto" if running else "Claude cerrado")
                      + (f" · activa: {st['active']}" if st.get("active") else ""))

        if not names:
            box = tk.Frame(list_frame, bg=CARD, padx=14, pady=14)
            box.pack(fill="x", pady=4)
            tk.Label(box, text="Aún no hay cuentas registradas.", bg=CARD, fg=FG,
                     font=("Helvetica", 11, "bold")).pack(anchor="w")
            tk.Label(box, text="Guarda la sesión con la que estás ahora en Claude\n"
                               "y luego añade las demás.", bg=CARD, fg=MUTED,
                     justify="left", font=("Helvetica", 10)).pack(anchor="w", pady=(4, 8))

            def first():
                n = ask_name("Guardar cuenta actual", "¿Cómo se llama la cuenta abierta ahora?")
                if n:
                    s = load_state()
                    do(lambda: save_current_as(s, n), "Guardando…")
            tk.Button(box, text="Guardar cuenta actual", command=first,
                      bg=ACCENT, fg="white", relief="flat", padx=10, pady=4,
                      activebackground=ACCENT, highlightthickness=0).pack(anchor="w")
            return

        for i, n in enumerate(names):
            active = (n == st.get("active"))
            row = tk.Frame(list_frame, bg=CARD, padx=12, pady=10, cursor="hand2")
            row.pack(fill="x", pady=3)
            dot = tk.Label(row, text="●", bg=CARD, fg=ACCENT if active else "#55534e",
                           font=("Helvetica", 12))
            dot.pack(side="left")
            lbl = tk.Label(row, text=n, bg=CARD, fg=FG, font=("Helvetica", 12,
                           "bold" if active else "normal"))
            lbl.pack(side="left", padx=8)
            key = f"⌘{i+1}" if SYSTEM == "Darwin" else f"Ctrl+{i+1}"
            hint_text = "activa" if active else (key if i < 9 else "")
            hint = tk.Label(row, text=hint_text, bg=CARD, fg=MUTED, font=("Helvetica", 9))
            hint.pack(side="right")
            for w in (row, dot, lbl, hint):
                w.bind("<Button-1>", lambda e, n=n: on_switch(n))
                w.bind("<Button-3>", lambda e, n=n: on_menu(e, n))
                w.bind("<Button-2>", lambda e, n=n: on_menu(e, n))
                w.bind("<Control-Button-1>", lambda e, n=n: on_menu(e, n))

    footer = tk.Frame(root, bg=BG)
    footer.pack(fill="x", padx=12, pady=(4, 14))
    tk.Button(footer, text="＋  Añadir cuenta", command=on_new, bg=ACCENT, fg="white",
              relief="flat", padx=12, pady=6, activebackground=ACCENT,
              highlightthickness=0, font=("Helvetica", 11, "bold")).pack(fill="x")
    tk.Label(footer, text="Clic = cambiar · clic derecho = renombrar / eliminar",
             bg=BG, fg=MUTED, font=("Helvetica", 9)).pack(pady=(6, 0))

    mod = "Command" if SYSTEM == "Darwin" else "Control"
    for k in range(1, 10):
        def hk(e, k=k):
            names = list_profiles(load_state())
            if k <= len(names):
                on_switch(names[k - 1])
        root.bind(f"<{mod}-Key-{k}>", hk)

    def tick():
        refresh()
        root.after(4000, tick)
    tick()
    root.mainloop()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv):
    if not argv:
        return run_gui()
    st = load_state()
    cmd, args = argv[0], argv[1:]
    try:
        if cmd == "list":
            for n in list_profiles(st):
                print(("* " if n == st.get("active") else "  ") + n)
            print(f"\nCarpeta de Claude: {claude_data_dir(st)}")
        elif cmd == "save" and len(args) == 1:
            save_current_as(st, args[0]); print(f"Sesión actual guardada como '{args[0]}'.")
        elif cmd == "switch" and len(args) == 1:
            switch_to(st, args[0]); print(f"Cambiado a '{args[0]}'.")
        elif cmd == "new" and len(args) == 1:
            switch_to(st, args[0], fresh=True)
            print(f"Claude abierto limpio. Inicia sesión: quedará guardado como '{args[0]}'.")
        elif cmd == "rename" and len(args) == 2:
            rename_profile(st, *args); print("Renombrado.")
        elif cmd == "delete" and len(args) == 1:
            delete_profile(st, args[0]); print("Eliminado.")
        else:
            print(__doc__); return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
