# setup.py dla cx_Freeze
import sys
from cx_Freeze import setup, Executable
import os

# Określenie ścieżki do plików
build_exe_options = {
    "packages": [
        "kivy", 
        "bleak", 
        "garminconnect", 
        "pandas", 
        "matplotlib",
        "asyncio",
        "configparser",
        "pathlib",
        "threading",
        "datetime",
        "requests",
        "json",
        "uuid"
    ],
    "excludes": [
        "tkinter",
        "unittest",
        "email",
        "xml",
        "pydoc",
        "doctest",
        "argparse",
        "difflib"
    ],
    "include_files": [
        ("assets/", "assets/"),
        ("config/", "config/"),
        ("data/", "data/"),
        "start_screen.py",
        "config_screen.py",
        "scan_screen.py",
        "weigh_screen.py",
        "dekodery.py",
        "ui_components.py"
    ],
    "optimize": 2,
    "build_exe": "../build/exe.win-amd64-3.8",
    # Dodane opcje dla bezpieczeństwa ścieżek
    "zip_include_packages": ["*"],
    "zip_exclude_packages": []
}

# Ustawienia dla Windows
base = None
if sys.platform == "win32":
    base = "Win32GUI"  # Ukrycie okna konsoli

# Konfiguracja executable
executables = [
    Executable(
        "main.py",
        base=base,
        target_name="FiToGar_EN.exe",  # EN version
        icon="assets/images/ico_mini.png" if os.path.exists("assets/images/ico_mini.png") else None,
        copyright="Copyright (C) 2025 pawel.eu",
        shortcut_name="FiToGar EN",  # EN version
        shortcut_dir="DesktopFolder",
    )
]

setup(
    name="FiToGar_EN",  # EN version
    version="1.0.0",
    description="Application for managing data from smart scales (EN version)",
    author="Pawel.eu",
    author_email="p@pawel.eu",
    url="https://github.com/Paweleu/FiToGar",
    options={"build_exe": build_exe_options},
    executables=executables
)
