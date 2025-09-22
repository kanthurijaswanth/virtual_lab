import os, sys, json, subprocess, time
from pathlib import Path
from typing import Optional, Tuple, List
from PySide6.QtCore import Qt, QTimer, QThread, QObject, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QComboBox, QPushButton,
    QVBoxLayout, QHBoxLayout, QFrame, QMessageBox, QSpacerItem, QSizePolicy,
    QStatusBar, QProgressDialog
)

APP_TITLE = "MMT Virtual Lab – GNU Radio"
APP_BRAND  = "MMT Virtual Lab"
PRIMARY = "#0A66C2"; SURFACE = "#FFFFFF"; TEXT = "#111111"; MUTED = "#6B7280"; ACCENT_BG = "#F3F6FB"

# ----- Tweak these -----
CLOSE_AFTER_SUCCESS_MS = 2000  # keep the "Opening..." dialog for this long after success
PREFERRED_LNK = r"C:\Users\Jaswanth Royal\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\GNU Radio 3.9.4\GNU Radio.lnk"

EXPERIMENTS = {
    "Experiment 1 (AM)":      "am_signal.grc",
    "Experiment 2 (FM)":      "fm_signal.grc",
    "Experiment 3 (2-FSK)":   "fsk_signal.grc",
    "Experiment 4 (QPSK)":    "psk_qpsk.grc",
    "Experiment 5 (16-QAM)":  "qam_16.grc",
    "Experiment 6 (FR)":      "fm_recever.grc"
}

QSS = f"""
* {{ font-family: 'Segoe UI', Arial; color: {TEXT}; }}
QMainWindow {{ background: {SURFACE}; }}
QFrame#Header {{ background: {PRIMARY}; border: none; }}
QLabel#Logo {{ margin: 6px 0; }}
QLabel#Brand {{ color: white; font-size: 18px; font-weight: 700; }}
QLabel#Subtitle {{ color: white; font-size: 12px; }}
QFrame.Card {{ background: {ACCENT_BG}; border-radius: 12px; }}
QLabel.SectionTitle {{ font-size: 12px; color: {MUTED}; letter-spacing: 1px; }}
QComboBox {{ padding: 8px 12px; border: 1px solid #DFE3EA; border-radius: 10px; }}
QComboBox:hover {{ border-color: {PRIMARY}; }}
QPushButton.Primary {{ background: {PRIMARY}; color: white; padding: 10px 14px; border-radius: 10px; font-weight: 600; }}
QPushButton.Primary:hover {{ background: #0853a0; }}
"""

# --------------------- basics & caches ---------------------
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

# Find logo file (assets/mmt_logo.png preferred)
def _logo_path() -> Optional[Path]:
    candidates = [
        app_base_dir() / "assets" / "mmt_logo.png",
        app_base_dir() / "mmt_logo.png",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None

# in-memory hot cache (fast)
_MEM = {
    "grc_path": None,       # str or None
    "exp_dir":  None        # Path or None
}

def _is_grc_launcher(path: str) -> bool:
    if not path or not os.path.exists(path): return False
    p = Path(path); name = p.name.lower()
    if any(k in name for k in ["setup","installer","release","win64","msi"]): return False
    if p.suffix.lower()==".lnk":
        b=p.stem.lower(); return ("gnu" in b and "radio" in b)
    if p.suffix.lower() in (".exe",".cmd",".bat"):
        return p.stem.lower().startswith("gnuradio-companion")
    return False

def _cache_get_grc_disk() -> str | None:
    p=_cfg_path()
    if p.exists():
        val=_load_json(p).get("grc_path")
        if _is_grc_launcher(val): return val
    return None
def _cache_set_grc_disk(path: str):
    if _is_grc_launcher(path): _save_json(_cfg_path(), {"grc_path": path})
def _cache_get_expdir_disk() -> Path | None:
    p=_exp_cache_path()
    if p.exists():
        d=_load_json(p).get("dir")
        if d and Path(d).is_dir(): return Path(d)
    return None
def _cache_set_expdir_disk(d: Path):
    if d and d.is_dir(): _save_json(_exp_cache_path(), {"dir": str(d)})

def _which(cmd: list[str]) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, shell=False)
        if r.returncode==0:
            out=(r.stdout or "").strip()
            return out.splitlines()[0] if out else None
    except Exception:
        pass
    return None

# --------------- find GRC (exe or .lnk) ---------------
def find_gnuradio_companion() -> str | None:
    if _MEM["grc_path"] and _is_grc_launcher(_MEM["grc_path"]):
        return _MEM["grc_path"]
    try:
        if PREFERRED_LNK and _is_grc_launcher(PREFERRED_LNK):
            tgt,_,_= _resolve_shortcut(PREFERRED_LNK)
            _MEM["grc_path"]=tgt or PREFERRED_LNK; _cache_set_grc_disk(_MEM["grc_path"]); return _MEM["grc_path"]
    except Exception: pass
    override=os.getenv("MMT_GRC_PATH")
    if _is_grc_launcher(override):
        _MEM["grc_path"]=override; _cache_set_grc_disk(override); return override
    cached=_cache_get_grc_disk()
    if cached:
        _MEM["grc_path"]=cached; return cached
    path = _which(["where","gnuradio-companion.cmd"]) or _which(["where","gnuradio-companion"]) or _which(["where","gnuradio-companion.exe"])
    if _is_grc_launcher(path):
        _MEM["grc_path"]=path; _cache_set_grc_disk(path); return path
    return None

# --------------- subprocess execution helper ---------------
def _start_process_native(file_path: str, args: list[str] | None = None, workdir: str | None = None) -> tuple[bool, str]:
    try:
        argv = [file_path] + (args or [])
        creationflags = 0
        if os.name == "nt":
            creationflags = 0x08000000  # CREATE_NO_WINDOW (hide console if python.exe)
        subprocess.Popen(
            argv,
            cwd=(workdir or str(Path(file_path).parent)),
            shell=False,
            creationflags=creationflags
        )
        return True, f"Spawn: {Path(file_path).name} {' '.join(args or [])} (wd: {workdir or Path(file_path).parent})"
    except FileNotFoundError as e:
        return False, f"FileNotFoundError: {e}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

# --------------- choose best way to open WITH/without a .grc ---------------
def _pick_module_launch(grc_launcher: str) -> tuple[str, list[str], str]:
    """
    Prefer pythonw/python to run: -m gnuradio.grc [<file>]
    Returns (file_path, base_args, working_dir)
    """
    if _ext(grc_launcher) == ".lnk":
        tgt, _, _ = _resolve_shortcut(grc_launcher)
        base = Path(tgt) if tgt else Path(grc_launcher)
        bin_dir = base.parent
    else:
        base = Path(grc_launcher)
        bin_dir = base.parent

    pyw = bin_dir / "pythonw.exe"
    pye = bin_dir / "python.exe"
    if pyw.exists():
        return str(pyw), ["-m", "gnuradio.grc"], str(bin_dir)
    if pye.exists():
        return str(pye), ["-m", "gnuradio.grc"], str(bin_dir)

    # Fallback: original launcher (args may be ignored on some builds)
    return str(base), [], str(bin_dir)

def _open_with_file_fast(grc_launcher: str, grc_file: str) -> tuple[bool, str]:
    prog, base_args, wd = _pick_module_launch(grc_launcher)
    args = base_args + [grc_file] if base_args else [grc_file]
    return _start_process_native(prog, args, wd)

def _open_blank_fast(grc_launcher: str) -> tuple[bool, str]:
    prog, base_args, wd = _pick_module_launch(grc_launcher)
    return _start_process_native(prog, base_args, wd)

def resolve_experiments_dir() -> Path | None:
    """Resolve and return the experiments directory"""
    if _MEM["exp_dir"] and _MEM["exp_dir"].is_dir():
        return _MEM["exp_dir"]
    
    # Check environment variable for experiments directory
    envd = os.getenv("MMT_EXPERIMENTS_DIR")
    if envd:
        d = Path(envd)
        if d.is_dir() and any(d.glob("*.grc")):
            _MEM["exp_dir"] = d
            _cache_set_expdir_disk(d)
            return d

    # Check cached experiments directory
    d = _cache_get_expdir_disk()
    if d and d.is_dir() and any(d.glob("*.grc")):
        _MEM["exp_dir"] = d
        return d

    # Default directory in the application base path
    d = app_base_dir() / "experiments"
    if d.is_dir() and any(d.glob("*.grc")):
        _MEM["exp_dir"] = d
        _cache_set_expdir_disk(d)
        return d

    # Check common locations in the home directory
    for p in [Path.home() / "Downloads/mmt-virtual-lab/experiments",
              Path.home() / "mmt-virtual-lab/experiments"]:
        p = Path(p)
        if p.is_dir() and any(p.glob("*.grc")):
            _MEM["exp_dir"] = p
            _cache_set_expdir_disk(p)
            return p

    return None


# --------------------- threaded launcher ---------------------
class LaunchWorker(QObject):
    finished = Signal(bool, str)   # ok, msg

    def __init__(self, mode: str, exp_name: Optional[str] = None):
        super().__init__()
        self.mode = mode          # "blank" or "file"
        self.exp_name = exp_name

    def run(self):
        try:
            # Resolve GRC path (may be slow once; cached thereafter)
            grc = find_gnuradio_companion()
            if not grc:
                self.finished.emit(False, "GNU Radio Companion was not found on this system.")
                return

            if self.mode == "file":
                d = resolve_experiments_dir()
                if not d:
                    self.finished.emit(False, "Experiments folder not found.")
                    return
                file_abs = d / EXPERIMENTS[self.exp_name]
                if not file_abs.exists():
                    self.finished.emit(False, f"Flowgraph not found: {file_abs}")
                    return
                ok, msg = _open_with_file_fast(grc, str(file_abs))
                self.finished.emit(ok, msg)
                return

            # blank
            ok, msg = _open_blank_fast(grc)
            self.finished.emit(ok, msg)

        except Exception as e:
            # Guarantee we always signal the UI to close the spinner
            self.finished.emit(False, f"Unexpected error: {type(e).__name__}: {e}")

# --------------------- UI ---------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(900, 500)
        self.setWindowIcon(QIcon())
        self.status = QStatusBar(); self.setStatusBar(self.status)
        self._active_dlg = None  # track any active buffering dialog
        self._build_ui()
        self.setStyleSheet(QSS)
        # Pre-warm (runs on UI thread but very quick thanks to caching)
        self._prewarm()

    def _build_ui(self):
        root = QWidget(); self.setCentralWidget(root)
        outer = QVBoxLayout(root); outer.setContentsMargins(16,16,16,16); outer.setSpacing(14)

        # ---------- Header with LOGO above text ----------
        # ---------- Header with LOGO above text (LEFT aligned) ----------
        header = QFrame(objectName="Header")
        hl = QVBoxLayout(header)  # vertical: logo -> brand -> subtitle
        hl.setContentsMargins(16, 12, 16, 12)
        hl.setSpacing(6)
        # Align the whole column to the LEFT
        hl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        logo_lbl = QLabel(objectName="Logo")
        # LEFT align the image
        logo_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lp = _logo_path()
        if lp:
            pm = QPixmap(str(lp))
            if not pm.isNull():
                pm = pm.scaledToHeight(120, Qt.SmoothTransformation)  # tweak height if needed
                logo_lbl.setPixmap(pm)
        else:
            logo_lbl.setText("")

        brand = QLabel(APP_BRAND, objectName="Brand")
        brand.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        sub = QLabel("Signal Processing Experiments (AM, FM, FSK, QPSK, 16-QAM)", objectName="Subtitle")
        sub.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        hl.addWidget(logo_lbl)
        hl.addWidget(brand)
        hl.addWidget(sub)
        outer.addWidget(header)


        # ---------- Card ----------
        card = QFrame(); card.setObjectName("Card"); card.setProperty("class", "Card")
        card_l = QVBoxLayout(card); card_l.setContentsMargins(16,16,16,16); card_l.setSpacing(10)

        section = QLabel("SELECT EXPERIMENT", objectName="SectionTitle"); section.setProperty("class","SectionTitle")
        card_l.addWidget(section)

        self.combo = QComboBox()
        for name in EXPERIMENTS: self.combo.addItem(name)
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

        # ---------- Footer ----------
        footer = QHBoxLayout(); footer.addItem(QSpacerItem(20,20,QSizePolicy.Expanding,QSizePolicy.Minimum))
        foot = QLabel(" MakeMyTechnology"); foot.setStyleSheet(f"color: {MUTED};"); footer.addWidget(foot, 0, Qt.AlignRight)
        outer.addLayout(footer)

    def _prewarm(self):
        try: _MEM["grc_path"] = find_gnuradio_companion()
        except Exception: pass
        try: _MEM["exp_dir"]  = resolve_experiments_dir()
        except Exception: pass

    # ---------- buffering dialog helpers ----------
    def _show_buffering(self, text: str = "Opening GNU Radio…") -> tuple[QProgressDialog, float]:
        dlg = QProgressDialog(text, None, 0, 0, self)
        dlg.setWindowTitle("Please wait")
        dlg.setCancelButton(None)
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)     # show immediately
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.show()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        return dlg, time.monotonic()

    def _close_buffering_after(self, dlg: QProgressDialog, delay_ms: int):
        def _finish():
            try:
                if dlg and dlg.isVisible():
                    dlg.close()
            except Exception:
                pass
            QApplication.restoreOverrideCursor()
            self._active_dlg = None
        QTimer.singleShot(delay_ms, _finish)

    # ---------- thread orchestration ----------
    def _launch_in_thread(self, mode: str, exp_name: Optional[str] = None):
        # Close any previously stuck dialog (paranoia)
        if self._active_dlg is not None:
            try: self._active_dlg.close()
            except Exception: pass
            QApplication.restoreOverrideCursor()
            self._active_dlg = None

        # 1) Show buffering immediately (GUI thread)
        dlg, _ = self._show_buffering("Opening GNU Radio…")
        self._active_dlg = dlg  # keep a handle for safety

        # 2) Prepare worker + thread
        self._thr = QThread(self)
        self._wrk = LaunchWorker(mode=mode, exp_name=exp_name)
        self._wrk.moveToThread(self._thr)

        self._thr.started.connect(self._wrk.run)

        def on_finished(ok: bool, msg: str):
            # Runs on GUI thread (QueuedConnection)
            self._post_to_gui(lambda: self.status.showMessage(msg, 8000))
            if not ok:
                # Close immediately on failure
                try:
                    if dlg and dlg.isVisible():
                        dlg.close()
                except Exception:
                    pass
                QApplication.restoreOverrideCursor()
                self._active_dlg = None
                QMessageBox.critical(self, "Launch failed", msg)
            else:
                # Close after the fixed 2s buffer on success
                self._close_buffering_after(dlg, CLOSE_AFTER_SUCCESS_MS)
            self._thr.quit()

        # Force queued delivery of the finish signal
        self._wrk.finished.connect(on_finished, type=Qt.QueuedConnection)

        # SAFETY NET: if the thread finishes for any reason and dialog is still up, close it.
        def _safety_close():
            try:
                if dlg and dlg.isVisible():
                    dlg.close()
                QApplication.restoreOverrideCursor()
            except Exception:
                pass
            self._active_dlg = None

        self._thr.finished.connect(self._wrk.deleteLater, type=Qt.QueuedConnection)
        self._thr.finished.connect(self._thr.deleteLater, type=Qt.QueuedConnection)
        self._thr.finished.connect(_safety_close, type=Qt.QueuedConnection)

        self._thr.start()

    # Button 1: open selected .grc (threaded)
    def on_open(self):
        name = self.combo.currentText()

        # Resolve the experiment directory to get the full path of the .grc file
        d = resolve_experiments_dir()
        if not d:
            self.status.showMessage("Experiments folder not found.", 8000)
            return

        # Get the absolute path of the selected experiment file
        file_abs = d / EXPERIMENTS[name]
        if not file_abs.exists():
            self.status.showMessage(f"Flowgraph not found: {file_abs}", 8000)
            return

        # Debugging: Print the file path
        print(f"Opening GNU Radio with file: {file_abs}")

        # Show buffering FIRST, then worker will validate exp path & launch
        self._launch_in_thread("file", exp_name=name)

        # Ensure we're calling the correct executable to launch the file
        grc_path = find_gnuradio_companion()  # Get the path of the GNU Radio Companion executable
        if not grc_path:
            self.status.showMessage("GNU Radio Companion was not found.", 8000)
            return

        # Debugging: Print the executable path
        print(f"Launching GNU Radio from: {grc_path}")

        try:
            # Launch GNU Radio Companion with the full path to the .grc file using Python
            result = subprocess.run(
                [grc_path, "-m", "gnuradio.grc", str(file_abs)],
                cwd=str(Path(grc_path).parent),
                capture_output=True,
                text=True
            )
    
            if result.returncode != 0:
                print(f"Error: {result.stderr}")  # Error message from stderr
                print(f"Output: {result.stdout}")  # Output from stdout
            else:
                print(f"Success: {result.stdout}")
    
            # Debugging: Check the output from the command
            print("GNU Radio Companion output:")
            print(result.stdout)  # stdout output
            print(result.stderr)  # stderr output
    
            self.status.showMessage(f"Opening {file_abs}", 8000)
    
        except subprocess.CalledProcessError as e:
            # Capture and display the error
            self.status.showMessage(f"Failed to open GRC file: {e}", 8000)
            print(f"Error: {e}")
            print(f"Stdout: {e.stdout}")
            print(f"Stderr: {e.stderr}")




    # Button 2: open blank (threaded)
    def on_open_blank(self):
        self._launch_in_thread("blank")

    def _post_to_gui(self, fn):
        QTimer.singleShot(0, fn)

    # Ensure cursor/dialog are cleaned up if window is closed mid-launch
    def closeEvent(self, event):
        try:
            if self._active_dlg is not None:
                self._active_dlg.close()
            QApplication.restoreOverrideCursor()
        except Exception:
            pass
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
