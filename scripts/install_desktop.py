#!/usr/bin/env python3
"""Install a per-user launcher for this checkout; does not touch the Brain store."""
from pathlib import Path
import os
import shutil

root = Path(__file__).resolve().parents[1]
applications = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'applications'
icons = applications.parent / 'icons/hicolor/scalable/apps'
applications.mkdir(parents=True, exist_ok=True)
icons.mkdir(parents=True, exist_ok=True)
launcher = applications / 'the-brain.desktop'
if launcher.exists():
    shutil.copy2(launcher, launcher.with_suffix('.desktop.previous'))
# Desktop Exec quoting differs from shell quoting, including literal percent escapes.
def quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'
launcher.write_text('[Desktop Entry]\nVersion=1.0\nType=Application\nName=The Brain\n'
    'GenericName=Project Knowledge\nComment=Browse project memory and retained evidence\n'
    f'Exec={quote(root / "scripts/launch_desktop.sh")}\n'
    'Icon=the-brain\nTerminal=false\nCategories=Office;\n'
    'Keywords=projects;knowledge;memory;evidence;\nStartupNotify=false\nStartupWMClass=The Brain\n')
launcher.chmod(0o755)
shutil.copy2(root / 'desktop/the-brain.svg', icons / 'the-brain.svg')
print(launcher)
