
MMT Virtual Lab — Build & Ship Guide
====================================

What’s inside
-------------
- launcher/virtual_lab_launcher.py  -> Tkinter app (blue/white UI)
- experiments/*.grc                 -> 5 visualization-only flowgraphs
- installer/mmt_virtual_lab.iss     -> Inno Setup script (Windows)
- third_party/                      -> Put GNU Radio Windows installer here
- dist/                             -> Place built EXE here (after PyInstaller)


Step 1 — (Dev machine) Build the launcher EXE
---------------------------------------------
1) Install Python 3.11+
2) pip install pyinstaller
3) From the project root, run:
   pyinstaller --onefile --noconsole launcher/virtual_lab_launcher.py
4) Move the output from `dist/virtual_lab_launcher.exe` (already created by the command)
   If it builds in local temp, copy into this project's dist/ folder.


Step 2 — Place GNU Radio Windows installer (optional but recommended)
--------------------------------------------------------------------
Download the official Windows build (CASTLE distribution) e.g.
  GNURadio_3.10.12.0-0_win64_release.exe
and put it under:
  third_party/GNURadio_3.10.12.0-0_win64_release.exe

If you skip this, your installer will still build, but it won’t be able
to auto-install GNU Radio for students who don’t have it yet.


Step 3 — Build the Windows installer (Inno Setup)
-------------------------------------------------
1) Install Inno Setup
2) Open installer/mmt_virtual_lab.iss
3) Compile -> It outputs MMT-Virtual-Lab-Setup.exe

When students run the installer:
- It checks for gnuradio-companion
- If missing and you bundled the EXE in step 2, it installs GNU Radio
- It installs your launcher and the .grc files
- It adds Start Menu / Desktop shortcuts (optional)


Step 4 — Student usage
----------------------
- Launch "MMT Virtual Lab"
- Pick AM/FM/FSK/QPSK/16-QAM experiment
- GNU Radio Companion opens the corresponding .grc
- In GRC, click the Run (▶) button to visualize
- Use Time/Frequency/Constellation QT sinks to observe the signals


Extending
---------
- Add more experiments by dropping new .grc files into experiments/
  and mapping them inside EXPERIMENTS in the launcher.
- Brand the UI by adding a logo, customizing colors, or adding instructions.
- For Linux/macOS, provide shell scripts to check/install GNU Radio via
  package managers or Radioconda.
