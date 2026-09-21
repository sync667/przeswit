"""Testy nie czytają lokalnego data/przeswit.env — konfiguracja wyłącznie z patchy w testach."""

import os

os.environ.setdefault('PRZESWIT_ENV', os.devnull)
