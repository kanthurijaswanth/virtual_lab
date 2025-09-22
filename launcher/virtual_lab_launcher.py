# MMT Virtual Lab — Minimal Qt Launcher (PySide6)
# One launch method only (PowerShell Start-Process).
# Button 1: open selected .grc via:  pythonw.exe -m gnuradio.grc "<file>"
# Button 2: open blank GRC (no args) via the EXE or shortcut.

import os, sys, glob, json, string as _s, shlex, subprocess
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QComboBox, QPushButton,
    QVBoxLayout, QHBoxLayout, QFrame, QMessageBox, QSpacerItem, QSizePolicy,
    QStatusBar
)

APP_TITLE = "MMT Virtual Lab – GNU Radio"
APP_BRAND  = "MMT Virtual Lab"
PRIMARY = "#0A66C2"; SURFACE = "#FFFFFF"; TEXT = "#111111"; MUTED = "#6B7280"; ACCENT_BG = "#F3F6FB"

PREFERRED_LNK = r"C:\Users\Jaswanth Royal\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\GNU Radio 3.9.4\GNU Radio.lnk"

EXPERIMENTS = {
    "Experiment 1 (AM)":      "am_signal.grc",
    "Experiment 2 (FM)":      "fm_signal.grc",
    "Experiment 3 (2-FSK)":   "fsk_signal.grc",
    "Experiment 4 (QPSK)":    "psk_qpsk.grc",
    "Experiment 5 (16-QAM)":  "qam_16.grc",
}

QSS = f"""
* {{ font-family: 'Segoe UI', Arial; color: {TEXT}; }}
QMainWindow {{ background: {SURFACE}; }}
QFrame#Header {{ background: {PRIMARY}; border: none; }}
QLabel#Brand {{ color: white; font-size: 18px; font-weight: 700; }}
QLabel#Subtitle {{ color: white; font-size: 12px; }}
QFrame.Card {{ background: {ACCENT_BG}; border-radius: 12px; }}
QLabel.SectionTitle {{ font-size: 12px; color: {MUTED}; letter-spacing: 1px; }}
QComboBox {{ padding: 8px 12px; border: 1px solid #DFE3EA; border-radius: 10px; }}
QComboBox:hover {{ border-color: {PRIMARY}; }}
QPushButton.Primary {{ background: {PRIMARY}; color: white; padding: 10px 14px; border-radius: 10px; font-weight: 600; }}
QPushButton.Primary:hover {{ background: #0853a0; }}
"""

# --------------------- basics ---------------------
def app_base_dir() -> Path: return Path(os.path.abspath(sys.argv[0])).parent
def _ext(p: str) -> str:    return Path(p).suffix.lower()
def _cfg_dir() -> Path:
    base = Path(os.getenv("APPDATA") or app_base_dir())
    d = base / "MMT" / "VirtualLab"; d.mkdir(parents=True, exist_ok=True); return d
def _cfg_path() -> Path:         return _cfg_dir() / "config.json"
def _exp_cache_path() -> Path:   return _cfg_dir() / "experiments_dir.json"
def _load_json(p: Path) -> dict:
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return {}
def _save_json(p: Path, data: dict):
    try: p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception: pass

def _is_grc_launcher(path: str) -> bool:
    if not path or not os.path.exists(path): return False
    p = Path(path); name = p.name.lower()
    if any(k in name for k in ["setup","installer","release","win64","msi"]): return False
    if p.suffix.lower()==".lnk":
        b=p.stem.lower(); return ("gnu" in b and "radio" in b)
    if p.suffix.lower() in (".exe",".cmd",".bat"):
        return p.stem.lower().startswith("gnuradio-companion")
    return False

def _cache_get_grc() -> str | None:
    p=_cfg_path()
    if p.exists():
        val=_load_json(p).get("grc_path")
        if _is_grc_launcher(val): return val
    return None
def _cache_set_grc(path: str):
    if _is_grc_launcher(path): _save_json(_cfg_path(), {"grc_path": path})
def _cache_get_expdir() -> Path | None:
    p=_exp_cache_path()
    if p.exists():
        d=_load_json(p).get("dir")
        if d and Path(d).is_dir(): return Path(d)
    return None
def _cache_set_expdir(d: Path):
    if d and d.is_dir(): _save_json(_exp_cache_path(), {"dir": str(d)})
def _looks_like_experiments_dir(d: Path) -> bool:
    return bool(d and d.is_dir() and any(d.glob("*.grc")))
def _which(cmd: list[str]) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, shell=False)
        if r.returncode==0:
            out=(r.stdout or "").strip()
            return out.splitlines()[0] if out else None
    except Exception:
        pass
    return None

# --------------- .lnk resolver ---------------
def _resolve_shortcut(lnk_path: str):
    if not os.path.exists(lnk_path): return None, "", None
    lnk_ps = lnk_path.replace("\\", "/")
    ps = [
        "powershell","-NoProfile","-ExecutionPolicy","Bypass","-Command",
        ("$w=New-Object -ComObject WScript.Shell; "
         f"$s=$w.CreateShortcut('{lnk_ps}'); "
         "[Console]::Out.WriteLine($s.TargetPath); "
         "[Console]::Out.WriteLine($s.Arguments); "
         "[Console]::Out.WriteLine($s.WorkingDirectory)")
    ]
    try:
        out = subprocess.run(ps, capture_output=True, text=True)
        lines=(out.stdout or "").splitlines()
        tgt  =(lines[0] if len(lines)>0 else "").strip() or None
        args =(lines[1] if len(lines)>1 else "").strip() or ""
        wdir =(lines[2] if len(lines)>2 else "").strip() or None
        return tgt, args, wdir
    except Exception:
        return None, "", None

# --------------- experiments dir ---------------
def resolve_experiments_dir() -> Path | None:
    envd=os.getenv("MMT_EXPERIMENTS_DIR")
    if envd:
        d=Path(envd)
        if _looks_like_experiments_dir(d): _cache_set_expdir(d); return d
    d=_cache_get_expdir()
    if d and _looks_like_experiments_dir(d): return d
    d=app_base_dir()/ "experiments"
    if _looks_like_experiments_dir(d): _cache_set_expdir(d); return d
    for p in [Path.home()/ "Downloads/mmt-virtual-lab/experiments",
              Path.home()/ "mmt-virtual-lab/experiments"]:
        p=Path(p)
        if _looks_like_experiments_dir(p): _cache_set_expdir(p); return p
    return None

# --------------- find GRC (exe or .lnk) ---------------
def find_gnuradio_companion() -> str | None:
    try:
        if PREFERRED_LNK and _is_grc_launcher(PREFERRED_LNK):
            tgt,_,_= _resolve_shortcut(PREFERRED_LNK)
            _cache_set_grc(tgt or PREFERRED_LNK); return tgt or PREFERRED_LNK
    except Exception: pass
    override=os.getenv("MMT_GRC_PATH")
    if _is_grc_launcher(override): _cache_set_grc(override); return override
    cached=_cache_get_grc()
    if cached: return cached
    path = _which(["where","gnuradio-companion.cmd"]) or _which(["where","gnuradio-companion"]) or _which(["where","gnuradio-companion.exe"])
    if _is_grc_launcher(path): _cache_set_grc(path); return path
    for c in [
        r"C:\GNURadio-3.10\bin\gnuradio-companion.cmd",
        r"C:\GNURadio-3.10\bin\gnuradio-companion.exe",
        r"C:\GNURadio-3.9\bin\gnuradio-companion.cmd",
        r"C:\GNURadio-3.9\bin\gnuradio-companion.exe",
        r"C:\Program Files\GNURadio\bin\gnuradio-companion.exe",
        r"C:\Program Files\GNURadio\bin\gnuradio-companion.cmd",
    ]:
        if _is_grc_launcher(c): _cache_set_grc(c); return c
    return None

# --------------- PowerShell Start-Process ---------------
def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"

def _ps_start_process(file_path: str, args: list[str] | None = None, workdir: str | None = None) -> tuple[bool, str]:
    try:
        ps = "powershell"
        wd = workdir or str(Path(file_path).parent)
        if args:
            array_literal = "@(" + ",".join(_ps_quote(a) for a in args) + ")"
            cmd = (
                f"Start-Process -FilePath {_ps_quote(file_path)} "
                f"-ArgumentList {array_literal} "
                f"-WorkingDirectory {_ps_quote(wd)} -WindowStyle Normal"
            )
        else:
            cmd = (
                f"Start-Process -FilePath {_ps_quote(file_path)} "
                f"-WorkingDirectory {_ps_quote(wd)} -WindowStyle Normal"
            )
        subprocess.Popen([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd], shell=False)
        return True, f"Start-Process: {Path(file_path).name} (wd: {wd})"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

# --------------- choose best way to open WITH a .grc ---------------
def _pick_module_launch(grc_launcher: str) -> tuple[str, list[str], str]:
    """
    For opening a .grc, use pythonw/python to run: -m gnuradio.grc "<file>"
    Returns (file_path, base_args, working_dir)
    """
    # If the launcher is a .lnk, resolve to EXE and reuse its bin for python[w]
    if _ext(grc_launcher) == ".lnk":
        tgt, lnk_args, lnk_wd = _resolve_shortcut(grc_launcher)
        base = Path(tgt) if tgt else Path(grc_launcher)
        bin_dir = base.parent
    else:
        base = Path(grc_launcher)
        bin_dir = base.parent

    # Prefer pythonw.exe (no console), else python.exe
    pyw = bin_dir / "pythonw.exe"
    pye = bin_dir / "python.exe"
    if pyw.exists():
        return str(pyw), ["-m", "gnuradio.grc"], str(bin_dir)
    if pye.exists():
        return str(pye), ["-m", "gnuradio.grc"], str(bin_dir)

    # Fallback: use the original launcher (may ignore args on some builds)
    return str(base), [], str(bin_dir)

def _open_with_file_ps(grc_launcher: str, grc_file: str) -> tuple[bool, str]:
    prog, base_args, wd = _pick_module_launch(grc_launcher)
    args = base_args + [grc_file] if base_args else [grc_file]
    return _ps_start_process(prog, args, wd)

def _open_blank_ps(grc_launcher: str) -> tuple[bool, str]:
    # blank: launching the EXE/shortcut is fine
    if _ext(grc_launcher) == ".lnk":
        tgt, lnk_args, lnk_wd = _resolve_shortcut(grc_launcher)
        if tgt and os.path.exists(tgt):
            args = shlex.split(lnk_args) if lnk_args else []
            return _ps_start_process(tgt, args, lnk_wd or str(Path(tgt).parent))
        try:
            os.startfile(grc_launcher)  # Explorer fallback
            return True, "Opened .lnk via Explorer (blank)"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"
    return _ps_start_process(grc_launcher, [], str(Path(grc_launcher).parent))

# --------------------- UI ---------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(900, 500)
        self.setWindowIcon(QIcon())
        self.status = QStatusBar(); self.setStatusBar(self.status)
        self._build_ui()
        self.setStyleSheet(QSS)

    def _build_ui(self):
        root = QWidget(); self.setCentralWidget(root)
        outer = QVBoxLayout(root); outer.setContentsMargins(16,16,16,16); outer.setSpacing(14)

        header = QFrame(objectName="Header")
        hl = QHBoxLayout(header); hl.setContentsMargins(16,12,16,12)
        brand = QLabel(APP_BRAND, objectName="Brand")
        sub = QLabel("Signal Processing Experiments (AM, FM, FSK, QPSK, 16-QAM)", objectName="Subtitle")
        sub.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hl.addWidget(brand, 0, Qt.AlignLeft); hl.addStretch(1); hl.addWidget(sub, 0, Qt.AlignRight)
        outer.addWidget(header)

        card = QFrame(); card.setObjectName("Card"); card.setProperty("class", "Card")
        card_l = QVBoxLayout(card); card_l.setContentsMargins(16,16,16,16); card_l.setSpacing(10)

        section = QLabel("SELECT EXPERIMENT", objectName="SectionTitle"); section.setProperty("class","SectionTitle")
        card_l.addWidget(section)

        self.combo = QComboBox()
        for name in EXPERIMENTS:
            self.combo.addItem(name)
        card_l.addWidget(self.combo)

        self.btn_open = QPushButton("Open GNU Radio"); self.btn_open.setObjectName("Primary"); self.btn_open.setProperty("class","Primary")
        self.btn_open.clicked.connect(self.on_open)
        card_l.addWidget(self.btn_open)

        self.btn_open_blank = QPushButton("Open GNU Radio (blank)"); self.btn_open_blank.setObjectName("Primary"); self.btn_open_blank.setProperty("class","Primary")
        self.btn_open_blank.clicked.connect(self.on_open_blank)
        card_l.addWidget(self.btn_open_blank)

        hint = QLabel("Tip: After GRC opens, press ▶ to run. Use QT GUI sinks for Time/Freq/Constellation.")
        hint.setStyleSheet(f"color: {MUTED};"); card_l.addWidget(hint)

        outer.addWidget(card)
        footer = QHBoxLayout(); footer.addItem(QSpacerItem(20,20,QSizePolicy.Expanding,QSizePolicy.Minimum))
        foot = QLabel("© MakeMyTechnology"); foot.setStyleSheet(f"color: {MUTED};"); footer.addWidget(foot, 0, Qt.AlignRight)
        outer.addLayout(footer)

    # Button 1: open selected .grc using python[w] -m gnuradio.grc "<file>"
    def on_open(self):
        exp_dir = resolve_experiments_dir()
        if not exp_dir:
            self.status.showMessage("Experiments folder not found.", 6000)
            QMessageBox.critical(self, "Experiments not found", "Could not locate the 'experiments' folder.")
            return

        name = self.combo.currentText()
        file_abs = exp_dir / EXPERIMENTS[name]
        if not file_abs.exists():
            self.status.showMessage("Selected flowgraph missing.", 6000)
            QMessageBox.critical(self, "Flowgraph missing", f"Could not find:\n{file_abs}")
            return

        grc = find_gnuradio_companion()
        if not grc:
            QMessageBox.critical(self, "App not found", "GNU Radio Companion was not found on this system.")
            return

        ok, msg = _open_with_file_ps(grc, str(file_abs))
        self.status.showMessage(msg, 8000)
        if not ok:
            QMessageBox.critical(self, "Launch failed", f"{msg}")

    # Button 2: open blank GRC via Start-Process (no args)
    def on_open_blank(self):
        grc = find_gnuradio_companion()
        if not grc:
            QMessageBox.critical(self, "App not found", "GNU Radio Companion was not found on this system.")
            return
        ok, msg = _open_blank_ps(grc)
        self.status.showMessage(msg, 8000)
        if not ok:
            QMessageBox.critical(self, "Launch failed", f"{msg}")

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
