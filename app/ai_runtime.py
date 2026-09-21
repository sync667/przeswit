"""App-owned Ollama runtime, two slots and conservative resource admission."""

import ctypes
import json
import os
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

from . import storage as store

URL = 'http://127.0.0.1:11435'
CAPACITY = 2
CACHED = {}
CACHE_LOCK = threading.Lock()


def probe():
    try:
        with urllib.request.urlopen(URL + '/api/tags', timeout=2) as r:
            json.load(r)
        return True
    except Exception:
        return False


def ensure():
    if probe():
        return
    store.DATA.mkdir(parents=True, exist_ok=True)
    # Domyślnie katalog modeli standardowej instalacji Ollamy (~/.ollama/models); inny wskaż przez PRZESWIT_MODELS.
    model_path = os.getenv('PRZESWIT_MODELS') or os.getenv('OLLAMA_MODELS') or str(Path.home() / '.ollama' / 'models')
    if not (Path(model_path) / 'manifests').exists():
        raise RuntimeError('Nie znaleziono katalogu modeli. Ustaw PRZESWIT_MODELS.')
    env = dict(
        os.environ,
        OLLAMA_MODELS=model_path,
        OLLAMA_NOPRUNE='true',
        OLLAMA_NO_CLOUD='true',
        OLLAMA_HOST='127.0.0.1:11435',
        OLLAMA_NUM_PARALLEL=str(CAPACITY),
        OLLAMA_MAX_LOADED_MODELS='1',
        OLLAMA_MAX_QUEUE='8',
    )
    with (store.DATA / 'ollama-runtime.log').open('ab') as log:
        proc = subprocess.Popen(
            ['ollama', 'serve'],
            env=env,
            stdout=log,
            stderr=log,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
    (store.DATA / 'ai-runtime.pid').write_text(str(proc.pid))
    for _ in range(40):
        if probe():
            return
        time.sleep(0.25)
    raise RuntimeError('Nie udało się uruchomić lokalnego AI. Sprawdź data/ollama-runtime.log.')


def resources():
    with CACHE_LOCK:
        if time.time() - CACHED.get('at', 0) < 10:
            return dict(CACHED)
        result = {'at': time.time(), 'gpu_free_mb': None, 'gpu_total_mb': None, 'ram_free_mb': None}
        try:
            raw = subprocess.check_output(
                ['nvidia-smi', '--query-gpu=memory.total,memory.free', '--format=csv,noheader,nounits'],
                timeout=3,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                stderr=subprocess.DEVNULL,
            ).decode()
            values = [tuple(int(x.strip()) for x in row.split(',')) for row in raw.strip().splitlines()]
            result['gpu_total_mb'], result['gpu_free_mb'] = max(values)
        except Exception:
            pass
        if os.name == 'nt':

            class Memory(ctypes.Structure):
                _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
                    (n, ctypes.c_ulonglong)
                    for n in (
                        'total',
                        'available',
                        'page_total',
                        'page_available',
                        'virtual_total',
                        'virtual_available',
                        'extended',
                    )
                ]

            m = Memory()
            m.length = ctypes.sizeof(m)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                result['ram_free_mb'] = m.available // 1048576
        else:
            try:  # Linux: /proc/meminfo; macOS bez telemetrii RAM (limit 1 zadania przez brak GPU)
                with open('/proc/meminfo', encoding='ascii') as f:
                    for line in f:
                        if line.startswith('MemAvailable:'):
                            result['ram_free_mb'] = int(line.split()[1]) // 1024
            except OSError:
                pass
        CACHED.clear()
        CACHED.update(result)
        return dict(result)


def admission(requested='auto', metrics=None):
    r = resources() if metrics is None else metrics
    if r.get('ram_free_mb') is not None and r['ram_free_mb'] < 4096:
        return 0
    free = r.get('gpu_free_mb')
    total = r.get('gpu_total_mb')
    if free is not None and free < 1536:
        return 0
    cap = 2 if total and total >= 18000 and free is not None and free >= 3072 else 1
    return min(cap, CAPACITY, 2 if requested == 'auto' else int(requested))
