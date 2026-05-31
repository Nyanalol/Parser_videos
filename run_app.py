"""Punto de entrada para empaquetar con PyInstaller.

Equivale a `python -m parser_videos`, pero como script suelto que PyInstaller
puede tomar como objetivo.
"""

from parser_videos.gui import run

if __name__ == "__main__":
    run()
