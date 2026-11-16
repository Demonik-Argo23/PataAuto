"""PataAuto v2 - juega tú, presiona F9 y el programa sigue tu ritmo.
pip install pynput psutil pygame vgamepad numpy windows-capture
"""

import os

os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import ctypes
import json
import math
import queue
import statistics
import sys
import threading
import time
import tkinter as tk
from collections import Counter, deque
from ctypes import wintypes
from pathlib import Path
from tkinter import ttk

import psutil
from pynput import keyboard as kb

try:
    import pygame
except Exception:
    pygame = None
try:
    import vgamepad as vg
except Exception:
    vg = None
try:
    import numpy as np
except Exception:
    np = None
try:
    # windows_capture importa OpenCV (>100 MB) solo para guardar imágenes, que no se usa
    sys.modules.setdefault("cv2", type(sys)("cv2"))
    from windows_capture import WindowsCapture
except Exception:
    WindowsCapture = None

# ================================================================ datos
if getattr(sys, "frozen", False):  # .exe instalado: config en %APPDATA%\PataAuto
    DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "PataAuto"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
else:
    DATA_DIR = Path(__file__).parent
CFG_PATH = DATA_DIR / "pataauto_v2.json"
LOG_PATH = DATA_DIR / "pataauto_deriva.log"
DRUMS = ["PATA", "PON", "CHAKA", "DON"]
SYMBOL = {"PATA": "□", "PON": "○", "CHAKA": "△", "DON": "✕"}
COLOR = {"PATA": "#e86fb4", "PON": "#e8423f", "CHAKA": "#3fbf7f", "DON": "#4f8ff0"}
COMMANDS = {
    "Avanzar": ["PATA", "PATA", "PATA", "PON"],
    "Ataque": ["PON", "PON", "PATA", "PON"],
    "Defensa": ["CHAKA", "CHAKA", "PATA", "PON"],
    "Retirada": ["PON", "PATA", "PON", "PATA"],
    "Carga": ["PON", "PON", "CHAKA", "CHAKA"],
    "Salto": ["DON", "DON", "CHAKA", "CHAKA"],
    "Fiesta": ["PATA", "PON", "DON", "CHAKA"],
}
BY_PATTERN = {tuple(v): k for k, v in COMMANDS.items()}
# índices SDL de DualSense: 0 ✕, 1 ○, 2 □, 3 △
DUALSENSE_BTN = {2: "PATA", 1: "PON", 3: "CHAKA", 0: "DON"}
OUTPUTS = ["keyboard", "xbox", "ds4"]
IGNORE_PROCS = {"python.exe", "pythonw.exe", "py.exe", "pataauto.exe", ""}

# ================================================================ idioma
CMD_EN = {
    "Avanzar": "March",
    "Ataque": "Attack",
    "Defensa": "Defend",
    "Retirada": "Retreat",
    "Carga": "Charge",
    "Salto": "Jump",
    "Fiesta": "Party",
}
STR = {
    "es": {
        "out_keyboard": "Teclado (juego enfocado)",
        "out_xbox": "Mando Xbox virtual (2º plano)",
        "out_ds4": "Mando PS4 virtual (2º plano)",
        "need_vgamepad": "Falta el driver del mando virtual (vgamepad / ViGEmBus)",
        "st_no_numpy": "falta numpy",
        "st_searching": "buscando juego…",
        "st_not_found": "juego no encontrado o minimizado",
        "st_not_visible": "juego no visible",
        "st_covered": "tapado: sigo con el último tempo",
        "st_reading": "✓ leyendo el marco",
        "st_no_flash": "sin parpadeo (¿menú o carga?)",
        "st_wgc_fail": "WGC falló: {e}",
        "pad_no_pygame": "pygame no instalado",
        "pad_search": "buscando…",
        "pad_none": "no detectado",
        "pad_lost": "desconectado",
        "seq_title": "SECUENCIA  (clic para quitar)",
        "add": "AGREGAR",
        "fine": "Ajuste fino (F7/F8)",
        "settings": "⚙ Ajustes",
        "output": "Salida",
        "keys": "Teclas",
        "lang": "Idioma",
        "seq_empty": "(vacía → Avanzar)",
        "tempo_fixed": "Tempo corregido: {p:.3f} ms/beat",
        "handback": "Control devuelto. Tú tocas.",
        "need_cmd": "Primero toca un comando completo en el juego, luego F9.",
        "no_game": "No detecté el juego. Toca un comando con el juego enfocado.",
        "late": "Llegaste tarde al compás: el combo pudo romperse.",
        "not_ready": "Marco no listo ({s}): arranco con tu ritmo y me engancho solo.",
        "unfocused": "⏸ El juego no está enfocado",
        "bot_playing": "🤖 Bot tocando: {c}",
        "stop_btn": "■ Retomar control (F9)",
        "unknown_cmd": "comando no reconocido",
        "you": "Tú: {c}  →  F9 y el bot sigue",
        "idle": "Toca 1–2 comandos en el juego y presiona F9",
        "go_btn": "▶ Que siga el bot (F9)",
        "last": "⏱ último: {t}",
        "mk_nosync": "sin corrección por marco",
        "mk_sync": "✓ corrigiendo con el marco",
        "mk_lost": "sin marco: tempo fijo",
        "mk_seen": "marco visto",
        "mk_none": "marco ✗",
        "sub": "{bpm:.1f} BPM · {mark} · salida: {out}",
        "info": "Juego detectado: {proc}\nMarco ({m}): {st} · {hz:.0f} Hz{jit} · tu sesgo {bias:+.0f} ms\n"
        "DualSense: {pad}",
        "screen": "pantalla",
    },
    "en": {
        "out_keyboard": "Keyboard (game focused)",
        "out_xbox": "Virtual Xbox pad (background)",
        "out_ds4": "Virtual PS4 pad (background)",
        "need_vgamepad": "Virtual pad driver missing (vgamepad / ViGEmBus)",
        "st_no_numpy": "numpy missing",
        "st_searching": "looking for the game…",
        "st_not_found": "game not found or minimized",
        "st_not_visible": "game not visible",
        "st_covered": "covered: keeping last tempo",
        "st_reading": "✓ reading the border",
        "st_no_flash": "no flashing (menu or loading?)",
        "st_wgc_fail": "WGC failed: {e}",
        "pad_no_pygame": "pygame not installed",
        "pad_search": "searching…",
        "pad_none": "not detected",
        "pad_lost": "disconnected",
        "seq_title": "SEQUENCE  (click to remove)",
        "add": "ADD",
        "fine": "Fine tune (F7/F8)",
        "settings": "⚙ Settings",
        "output": "Output",
        "keys": "Keys",
        "lang": "Language",
        "seq_empty": "(empty → March)",
        "tempo_fixed": "Tempo corrected: {p:.3f} ms/beat",
        "handback": "Control returned. Your turn.",
        "need_cmd": "Play a full command in the game first, then F9.",
        "no_game": "Game not detected. Play a command with the game focused.",
        "late": "Late for the measure: the combo may have broken.",
        "not_ready": "Border not ready ({s}): starting from your rhythm, will lock on by itself.",
        "unfocused": "⏸ The game is not focused",
        "bot_playing": "🤖 Bot playing: {c}",
        "stop_btn": "■ Take back control (F9)",
        "unknown_cmd": "unknown command",
        "you": "You: {c}  →  F9 and the bot takes over",
        "idle": "Play 1–2 commands in the game and press F9",
        "go_btn": "▶ Let the bot play (F9)",
        "last": "⏱ last: {t}",
        "mk_nosync": "no border sync",
        "mk_sync": "✓ synced to the border",
        "mk_lost": "no border: fixed tempo",
        "mk_seen": "border seen",
        "mk_none": "border ✗",
        "sub": "{bpm:.1f} BPM · {mark} · output: {out}",
        "info": "Detected game: {proc}\nBorder ({m}): {st} · {hz:.0f} Hz{jit} · your bias {bias:+.0f} ms\n"
        "DualSense: {pad}",
        "screen": "screen",
    },
}
LANG = "es"


def T(key, **kw):
    s = STR[LANG].get(key, STR["es"].get(key, key))
    return s.format(**kw) if kw else s


def CN(name):
    """Nombre del comando en el idioma actual (internamente se guardan en español)."""
    return name if LANG == "es" else CMD_EN.get(name, name)


def system_lang():
    try:
        return (
            "es"
            if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x0A
            else "en"
        )
    except Exception:
        return "en"


DEFAULT_CFG = {
    "lang": "",
    "output": "keyboard",
    "process": "",
    "keys": {"PATA": "a", "PON": "d", "CHAKA": "w", "DON": "s"},
    "offset_ms": 0,
    "press_ms": 45,
    "sequence": ["Ataque"],
    "period_ms": 500.0,
    "period_weight": 0.0,
    "sync_bias_ms": 0.0,  # tus golpes respecto al parpadeo del marco
    "sync_bias_n": 0,
}


def load_cfg():
    cfg = json.loads(json.dumps(DEFAULT_CFG))
    if CFG_PATH.exists():
        try:
            cfg.update(json.loads(CFG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    if cfg["lang"] not in STR:
        cfg["lang"] = system_lang()
    return cfg


def save_cfg(cfg):
    CFG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


# ================================================================ win32
user32 = ctypes.WinDLL("user32", use_last_error=True)
ctypes.WinDLL("winmm").timeBeginPeriod(1)
ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _U(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


gdi32 = ctypes.WinDLL("gdi32")
_H = ctypes.c_void_p
user32.GetDC.restype = _H
user32.GetDC.argtypes = [_H]
gdi32.CreateCompatibleDC.restype = _H
gdi32.CreateCompatibleDC.argtypes = [_H]
gdi32.CreateDIBSection.restype = _H
gdi32.CreateDIBSection.argtypes = [
    _H,
    ctypes.c_void_p,
    wintypes.UINT,
    ctypes.POINTER(ctypes.c_void_p),
    _H,
    wintypes.DWORD,
]
user32.WindowFromPoint.restype = _H
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.GetAncestor.restype = _H
user32.GetAncestor.argtypes = [_H, wintypes.UINT]
gdi32.SelectObject.restype = _H
gdi32.SelectObject.argtypes = [_H, _H]
gdi32.DeleteObject.argtypes = [_H]
gdi32.BitBlt.argtypes = [
    _H,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    _H,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.DWORD,
]


_names = {}


def window_proc(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value not in _names:
        try:
            _names[pid.value] = psutil.Process(pid.value).name()
        except Exception:
            return ""
    return _names[pid.value]


def foreground_proc():
    return window_proc(user32.GetForegroundWindow())


def wait_until(t, alive):
    while alive():
        d = t - time.perf_counter()
        if d <= 0:
            return True
        time.sleep(min(d - 0.0015, 0.05)) if d > 0.002 else None
    return False


# ================================================================ salidas
class KeyboardOut:
    background = False

    def __init__(self, cfg):
        def scan(ch):
            return user32.MapVirtualKeyW(user32.VkKeyScanW(ord(ch)) & 0xFF, 0)

        self.scan = {d: scan(cfg["keys"][d]) for d in DRUMS}

    def _send(self, d, up):
        flags = 0x8 | (0x2 if up else 0)  # SCANCODE | KEYUP
        inp = INPUT(type=1, u=_U(ki=KEYBDINPUT(0, self.scan[d], flags, 0, 0)))
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def down(self, d):
        self._send(d, False)

    def up(self, d):
        self._send(d, True)

    def close(self):
        pass


class XboxOut:
    background = True

    def __init__(self, cfg):
        if vg is None:
            raise RuntimeError(T("need_vgamepad"))
        B = vg.XUSB_BUTTON
        self.btn = {
            "PATA": B.XUSB_GAMEPAD_X,
            "PON": B.XUSB_GAMEPAD_B,
            "CHAKA": B.XUSB_GAMEPAD_Y,
            "DON": B.XUSB_GAMEPAD_A,
        }
        self.pad = vg.VX360Gamepad()

    def down(self, d):
        self.pad.press_button(self.btn[d])
        self.pad.update()

    def up(self, d):
        self.pad.release_button(self.btn[d])
        self.pad.update()

    def close(self):
        self.pad.reset()
        self.pad.update()


class DS4Out(XboxOut):
    def __init__(self, cfg):
        if vg is None:
            raise RuntimeError(T("need_vgamepad"))
        B = vg.DS4_BUTTONS
        self.btn = {
            "PATA": B.DS4_BUTTON_SQUARE,
            "PON": B.DS4_BUTTON_CIRCLE,
            "CHAKA": B.DS4_BUTTON_TRIANGLE,
            "DON": B.DS4_BUTTON_CROSS,
        }
        self.pad = vg.VDS4Gamepad()


OUT_CLASSES = {"keyboard": KeyboardOut, "xbox": XboxOut, "ds4": DS4Out}


# ================================================================ ritmo
def linfit(xs, ys):
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum(
        (x - mx) ** 2 for x in xs
    )
    return my - b * mx, b


def fit_beats(ts, p):
    ks = [0]
    a = ts[0]
    for _ in range(4):
        ks = [round((t - ts[0]) / p) for t in ts]
        if len(set(ks)) < 2:
            break
        a, p = linfit(ks, ts)
    return a, p, ks


class BorderSync:
    """Lee la franja inferior del marco del juego, que se enciende en cada beat,
    y guarda el instante de cada subida. Con windows-capture lee la ventana aunque esté tapada;
    si no, una BitBlt de pantalla por muestra (va al ritmo del monitor)."""

    BAND = (0.010, 0.032)  # franja del marco, en fracción del alto desde abajo

    def __init__(self, app):
        self.app = app
        self.onsets = deque(maxlen=600)  # (t, salto de brillo)
        self.lock = threading.Lock()
        self.hz = 0.0
        self._hist, self._jumps = deque(), deque(maxlen=16)
        self._last_on, self._n, self._t_hz = 0.0, 0, 0.0
        self.method = "WGC" if WindowsCapture is not None else "screen"
        self.err = ""
        self.state = "st_no_numpy" if np is None else "st_searching"
        if np is not None:
            loop = self._wgc_loop if WindowsCapture is not None else self._gdi_loop
            threading.Thread(target=loop, daemon=True).start()

    def since(self, t0):
        with self.lock:
            return [o[0] for o in self.onsets if o[0] >= t0]

    def text(self):
        return (
            T(self.state, e=self.err) if self.state == "st_wgc_fail" else T(self.state)
        )

    def alive(self, secs=2.0):
        with self.lock:
            return bool(self.onsets) and time.perf_counter() - self.onsets[-1][0] < secs

    def grid(self, avoid=(), secs=8.0):
        """(a, p) de los últimos `secs` s de parpadeos, sin los que caen junto a un golpe tuyo."""
        now = time.perf_counter()
        ts = [
            t for t in self.since(now - secs) if all(abs(t - h) > 0.08 for h in avoid)
        ]
        if len(ts) < 6:
            return None
        p0 = self.app.cfg["period_ms"] / 1000
        a, p, ks = fit_beats(ts, p0)
        good = [(k, t) for k, t in zip(ks, ts) if abs(t - a - k * p) < 0.1 * p]
        if len(good) < 6 or abs(p - p0) / p0 > 0.15:
            return None
        a, p = linfit(*zip(*good))
        return a, p

    def _find(self):
        want = self.app.cfg["process"].lower()
        found = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def cb(h, _):
            if user32.IsWindowVisible(h) and not user32.IsIconic(h):
                name = window_proc(h).lower()
                if name and (name == want or "patapon" in name):
                    r = wintypes.RECT()
                    user32.GetClientRect(h, ctypes.byref(r))
                    found.append((r.right * r.bottom, h, r.right, r.bottom))
            return True

        user32.EnumWindows(cb, 0)
        if not found:
            return None
        _, h, w, hh = max(found)
        pt = wintypes.POINT(0, 0)
        user32.ClientToScreen(h, ctypes.byref(pt))
        return pt.x, pt.y, w, hh, h

    @staticmethod
    def _visible(hwnd, geo):
        """La franja muestra el juego y no otra ventana encima."""
        x, y, w, hh = geo
        for i in range(7):
            p = wintypes.POINT(x + 2 + (w - 4) * i // 6, y + hh // 2)
            if user32.GetAncestor(user32.WindowFromPoint(p), 2) != hwnd:
                return False
        return True

    def _feed(self, t, v):
        """Una muestra de brillo de la franja. Detecta la subida del parpadeo."""
        hist, jumps = self._hist, self._jumps
        while hist and t - hist[0][0] > 0.35:
            hist.popleft()
        floor = min(h_[1] for h_ in hist) if hist else v
        k = max(8.0, 0.3 * statistics.median(jumps)) if len(jumps) >= 4 else 8.0
        if (
            hist
            and v - floor > k
            and hist[-1][1] - floor < k / 2
            and t - self._last_on > 0.3
        ):
            self._last_on = t
            jumps.append(v - floor)
            with self.lock:
                self.onsets.append((t, v - floor))
        hist.append((t, v))
        self._n += 1
        if self._n == 1:
            self._t_hz = t
        elif t - self._t_hz > 1:
            self.hz, self._n = self._n / (t - self._t_hz), 0
            self.state = "st_reading" if self.alive() else "st_no_flash"

    def _reset(self):
        self._hist.clear()
        self._n, self.hz = 0, 0.0

    def _band(self, h):
        a = int(h * self.BAND[0])
        return a, max(int(h * self.BAND[1]), a + 2)

    def _wgc_loop(self):
        """Windows Graphics Capture: lee la ventana del juego aunque esté tapada (no minimizada).
        Un frame por cada frame del juego, con marca de tiempo QPC (= perf_counter)."""
        user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
        while True:
            rect = self._find()
            if rect is None:
                self.state = "st_not_found"
                self._reset()
                time.sleep(1)
                continue
            x, y, w, h, hwnd = rect
            ext = wintypes.RECT()
            ctypes.WinDLL("dwmapi").DwmGetWindowAttribute(
                hwnd, 9, ctypes.byref(ext), ctypes.sizeof(ext)
            )
            pad = max(
                0, ext.bottom - (y + h)
            )  # borde de la ventana bajo el área cliente
            a, b = self._band(h)
            cap = WindowsCapture(
                cursor_capture=False,
                draw_border=False,
                window_hwnd=hwnd,
                minimum_update_interval=1,
            )

            @cap.event
            def on_frame_arrived(frame, ctl, pad=pad, a=a, b=b):
                fb = frame.frame_buffer
                bot = fb.shape[0] - pad
                self._feed(
                    frame.timespan * 1e-7, float(fb[bot - b : bot - a, :, :3].mean())
                )

            @cap.event
            def on_closed():
                pass

            try:
                ctl = cap.start_free_threaded()
            except Exception as e:
                self.state, self.err = "st_wgc_fail", str(e)
                time.sleep(2)
                continue
            while not ctl.is_finished():
                time.sleep(1)
                r = self._find()
                if r is None or r[4] != hwnd or r[2:4] != (w, h):
                    ctl.stop()
                    break
            self._reset()

    def _gdi_loop(self):
        user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
        sdc = user32.GetDC(None)
        mdc = gdi32.CreateCompatibleDC(sdc)
        bmp, arr, geo, rect = None, None, None, None
        last_find = 0.0
        while True:
            now = time.perf_counter()
            if now - last_find > 0.5:
                last_find = now
                rect = self._find()
                if rect is None:
                    self.state, self.hz = "st_not_visible", 0.0
                    time.sleep(0.5)
                    continue
                x, y, w, h, hwnd = rect
                a, b = self._band(h)
                if (w, b - a) != (geo and geo[2:]):
                    if bmp:
                        gdi32.DeleteObject(bmp)
                    bih = BITMAPINFOHEADER(
                        ctypes.sizeof(BITMAPINFOHEADER), w, -(b - a), 1, 32
                    )
                    bits = ctypes.c_void_p()
                    bmp = gdi32.CreateDIBSection(
                        mdc, ctypes.byref(bih), 0, ctypes.byref(bits), None, 0
                    )
                    gdi32.SelectObject(mdc, bmp)
                    arr = np.ctypeslib.as_array(
                        ctypes.cast(bits, ctypes.POINTER(ctypes.c_uint8)), (b - a, w, 4)
                    )
                geo = (x, y + h - b, w, b - a)
            if not self._visible(hwnd, geo):
                self._reset()  # al destaparse, el cambio de imagen no cuenta como parpadeo
                self.state = "st_covered"
                time.sleep(0.05)
                continue
            gdi32.BitBlt(mdc, 0, 0, geo[2], geo[3], sdc, geo[0], geo[1], 0x00CC0020)
            self._feed(time.perf_counter(), float(arr[:, :, :3].mean()))
            if self.hz > 400:  # sin vsync (BitBlt no bloquea): no quemar CPU
                time.sleep(0.001)


class Learner:
    """Escucha tus golpes (teclado o DualSense) y deduce tempo, fase y comando."""

    def __init__(self, app):
        self.app = app
        self.hits = deque(maxlen=300)  # (t, drum, proceso)
        self.lock = threading.Lock()
        self.cache = None

    def add(self, drum):
        t = time.perf_counter()
        proc = foreground_proc()
        with self.lock:
            if self.hits and t - self.hits[-1][0] < 0.1:
                return
            self.hits.append((t, drum, proc))
            self.cache = None

    def clear(self):
        with self.lock:
            self.hits.clear()
            self.cache = None

    def solve(self):
        with self.lock:
            if self.cache is not None:
                return self.cache
            p0 = self.app.cfg["period_ms"] / 1000
            seg = []
            for h in reversed(self.hits):
                if seg and seg[-1][0] - h[0] > 10 * p0:
                    break
                seg.append(h)
            seg.reverse()
            if len(seg) < 4:
                return None
            ts = [h[0] for h in seg]
            span = ts[-1] - ts[0]
            if len(seg) >= 8 and span > 3:
                a, p, ks = fit_beats(ts, p0)
                if abs(p - p0) / p0 > 0.15:
                    p, w = p0, 0.0
                else:
                    w = span**2
            else:
                ks = [round((t - ts[0]) / p0) for t in ts]
                p, w = p0, 0.0
                a = statistics.fmean(t - k * p for t, k in zip(ts, ks))
            # último bloque de golpes en beats consecutivos = último comando
            i = len(ks) - 1
            while i > 0 and ks[i] - ks[i - 1] == 1 and len(ks) - i < 4:
                i -= 1
            drums = [h[1] for h in seg[i:]]
            procs = Counter(h[2] for h in seg if h[2].lower() not in IGNORE_PROCS)
            self.cache = {
                "cycle_start": a + ks[i] * p,
                "p": p,
                "weight": w,
                "ts": ts,
                "drums": drums,
                "cmd": BY_PATTERN.get(tuple(drums)),
                "process": procs.most_common(1)[0][0] if procs else "",
            }
            return self.cache


class Engine:
    def __init__(self, app):
        self.app = app
        self.running = False
        self.out = None
        self.cycle = 0.0
        self.p = 0.5
        self.cmd = None
        self.seq_i = 0
        self.unfocused = False
        self.adj = 0.0  # desplazamiento de fase de esta sesión (s)
        self.total = 0.0  # suma de correcciones F7/F8 de esta sesión (s)
        self.pts = []  # (beat, total) una por tanda de correcciones
        self.base = self.p0 = self.t0 = 0.0
        self.bias = None  # None: sin marco. Si no, golpe = parpadeo + bias
        self.locked = False
        self.jitter = 0.0

    def start(self, first_cycle, p, bias=None):
        self.out = self.app.out
        if self.out is None:
            raise RuntimeError(self.app.out_err or "salida no lista")
        self.cycle, self.p, self.seq_i = first_cycle, p, 0
        self.base, self.p0 = first_cycle, p
        self.cmd = None
        self.bias, self.locked = bias, bias is not None
        self.adj = self.total = 0.0
        self.t0 = time.perf_counter()
        self.pts = [(self.beat(), 0.0)]
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False

    def _alive(self):
        return self.running

    def beat(self):
        return (time.perf_counter() - self.base) / self.p0

    def rebase(self):
        """Nuevo origen de medición (tras ajustar offset_ms)."""
        self.pts = [(self.beat(), self.total)]

    def correct(self, d):
        """F7/F8 a mitad de sesión. Cada tanda (pulsaciones a <40 beats entre sí)
        es un punto (beat, corrección acumulada); la pendiente de la regresión
        sobre toda la sesión es el error de tempo. La fase queda donde la dejó el usuario."""
        n = self.beat()
        self.total += d
        if n - self.pts[-1][0] < 40:
            self.pts[-1] = (n, self.total)
        else:
            self.pts.append((n, self.total))
        b = 0.0
        if len(self.pts) >= 2:
            xs, ys = zip(*self.pts)
            mx, my = statistics.fmean(xs), statistics.fmean(ys)
            b = sum((x - mx) * (y - my) for x, y in self.pts) / sum(
                (x - mx) ** 2 for x in xs
            )
        self.adj = self.total - b * n
        self.p = self.p0 + b
        return n

    def resync(self):
        """Realinea la rejilla con los parpadeos del marco. Solo usa los beats de respuesta
        (sin golpes del bot), así no se persigue a sí mismo. Periodo: últimos ~160 beats;
        fase: últimos 8 puntos, para absorber rápido un frame perdido."""
        if self.bias is None:
            return
        pts = []
        for t in self.app.sync.since(self.t0 - 4):
            x = (t + self.bias - self.base - self.adj) / self.p
            n = round(x)  # beat más cercano: corrige cualquier desfase < medio beat
            if n % 8 >= 4:
                pts.append((n, t, abs(x - n) < 0.2))
        self.locked = bool(pts) and time.perf_counter() - pts[-1][1] < 4
        pts = [q for q in pts if q[0] > pts[-1][0] - 160] if pts else []
        if len(pts) < 8:
            return
        good = [(n, t) for n, t, ok in pts if ok]
        p = self.p
        if len(good) >= 8 and good[-1][0] - good[0][0] >= 32:
            p = linfit(*zip(*good))[1]
        res = [t - p * n for n, t, _ in pts[-8:]]
        a = statistics.median(res)
        self.jitter = statistics.pstdev(res)
        self.p = p
        self.adj = a + self.bias - self.base

    def _allowed(self):
        cfg = self.app.cfg
        if self.out.background:
            self.unfocused = False
            return True
        self.unfocused = foreground_proc().lower() != cfg["process"].lower()
        return not self.unfocused

    def _loop(self):
        cfg = self.app.cfg
        k = 0
        try:
            while self.running:
                self.resync()
                seq = cfg["sequence"] or ["Avanzar"]
                name = seq[self.seq_i % len(seq)]
                self.seq_i += 1
                if not wait_until(
                    self.base
                    + 8 * k * self.p
                    + cfg["offset_ms"] / 1000
                    + self.adj
                    - 0.03,
                    self._alive,
                ):
                    return
                self.cycle, self.cmd = self.base + 8 * k * self.p + self.adj, name
                for i, drum in enumerate(COMMANDS[name]):
                    t = (
                        self.base
                        + (8 * k + i) * self.p
                        + cfg["offset_ms"] / 1000
                        + self.adj
                    )
                    if not wait_until(t, self._alive):
                        return
                    if self._allowed():
                        self.out.down(drum)
                        wait_until(t + cfg["press_ms"] / 1000, lambda: True)
                        self.out.up(drum)
                k += 1
        finally:
            self.out.close()
            self.running = False


# ================================================================ entradas
class Inputs:
    def __init__(self, app):
        self.app = app
        self.pressed = set()
        self.pad_name = "pad_no_pygame" if pygame is None else "pad_search"
        kb.Listener(on_press=self._kdown, on_release=self._kup, daemon=True).start()
        if pygame is not None:
            threading.Thread(target=self._pad_loop, daemon=True).start()

    @staticmethod
    def _name(key):
        ch = getattr(key, "char", None)
        if ch:
            return ch.lower()
        vk = getattr(key, "vk", None)
        return chr(vk).lower() if vk and 65 <= vk <= 90 else None

    def _kdown(self, key):
        if key == kb.Key.f9:
            self.app.ui(self.app.toggle)
            return
        if key == kb.Key.f7:
            self.app.ui(lambda: self.app.nudge(-5))
            return
        if key == kb.Key.f8:
            self.app.ui(lambda: self.app.nudge(5))
            return
        n = self._name(key)
        if not n or n in self.pressed:
            return
        self.pressed.add(n)
        if self.app.engine.running:
            return
        for d, k in self.app.cfg["keys"].items():
            if k.lower() == n:
                self.app.learner.add(d)

    def _kup(self, key):
        self.pressed.discard(self._name(key))

    def _pad_loop(self):
        pygame.init()
        pygame.joystick.init()
        joy, prev, last_scan = None, {}, 0.0
        while True:
            try:
                pygame.event.pump()
                if joy is None and time.perf_counter() - last_scan > 1:
                    last_scan = time.perf_counter()
                    pygame.joystick.quit()
                    pygame.joystick.init()
                    for i in range(pygame.joystick.get_count()):
                        j = pygame.joystick.Joystick(i)
                        nm = j.get_name()
                        if "dualsense" in nm.lower() or "ps5" in nm.lower():
                            joy, prev = j, {}
                            self.pad_name = nm
                            break
                    else:
                        self.pad_name = "pad_none"
                if joy is not None:
                    for idx, drum in DUALSENSE_BTN.items():
                        b = joy.get_button(idx)
                        if b and not prev.get(idx) and not self.app.engine.running:
                            self.app.learner.add(drum)
                        prev[idx] = b
            except Exception:
                joy = None
                self.pad_name = "pad_lost"
            time.sleep(0.001)


# ================================================================ UI
class App:
    BG, FG, DIM = "#1b1b22", "#f2f2f2", "#55556a"

    def __init__(self):
        global LANG
        self.cfg = load_cfg()
        LANG = self.cfg["lang"]
        self.q = queue.Queue()
        self.learner = Learner(self)
        self.engine = Engine(self)
        self.sync = BorderSync(self)
        self.msg = ""
        self.msg_until = 0.0
        self.last_run = None  # duración (s) del último farmeo

        r = self.root = tk.Tk()
        r.title("PataAuto")
        r.configure(bg=self.BG)
        r.attributes("-topmost", True)
        r.resizable(False, False)
        self._build()
        self.out, self.out_err = None, ""
        self._make_out()
        self.inputs = Inputs(self)
        r.protocol("WM_DELETE_WINDOW", self._close)
        r.after(15, self._tick)

    def _make_out(self):
        """La salida (mando virtual) se conecta al abrir la app, no al pulsar F9:
        conectar el mando hace que el juego dé un tirón."""
        self.out = (
            None  # suelta el mando anterior (vgamepad lo desconecta al destruirlo)
        )
        try:
            self.out, self.out_err = OUT_CLASSES[self.cfg["output"]](self.cfg), ""
        except Exception as e:
            self.out_err = str(e)

    def ui(self, fn):
        self.q.put(fn)

    def flash(self, text, secs=3):
        self.msg, self.msg_until = text, time.perf_counter() + secs

    # ------------------------------------------------ layout
    def _lbl(self, parent, **kw):
        kw.setdefault("bg", self.BG)
        kw.setdefault("fg", self.FG)
        return tk.Label(parent, **kw)

    def _btn(self, parent, text, cmd, **kw):
        kw.setdefault("bg", "#2c2c38")
        kw.setdefault("fg", self.FG)
        return tk.Button(
            parent,
            text=text,
            command=cmd,
            relief="flat",
            activebackground="#3a3a4a",
            activeforeground=self.FG,
            cursor="hand2",
            **kw,
        )

    def _build(self):
        r = self.root
        self.v_status = tk.StringVar()
        self._lbl(
            r,
            textvariable=self.v_status,
            font=("Segoe UI", 13, "bold"),
            wraplength=460,
            justify="center",
        ).pack(padx=14, pady=(12, 4))
        self.v_sub = tk.StringVar()
        self._lbl(r, textvariable=self.v_sub, fg="#a0a0b8", font=("Segoe UI", 9)).pack()
        self.v_timer = tk.StringVar()
        self._lbl(r, textvariable=self.v_timer, font=("Consolas", 11)).pack(pady=(2, 0))

        self.cv = tk.Canvas(r, width=460, height=70, bg=self.BG, highlightthickness=0)
        self.cv.pack(padx=14, pady=8)

        self._lbl(
            r, text=T("seq_title"), fg="#a0a0b8", font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", padx=14)
        self.seq_box = tk.Frame(r, bg=self.BG)
        self.seq_box.pack(fill="x", padx=14, pady=(2, 8))

        self._lbl(r, text=T("add"), fg="#a0a0b8", font=("Segoe UI", 8, "bold")).pack(
            anchor="w", padx=14
        )
        add = tk.Frame(r, bg=self.BG)
        add.pack(padx=14, pady=(2, 8))
        for i, (name, drums) in enumerate(COMMANDS.items()):
            txt = f"{CN(name)}\n{''.join(SYMBOL[d] for d in drums)}"
            self._btn(
                add,
                txt,
                lambda n=name: self._seq_add(n),
                width=10,
                font=("Segoe UI", 9),
            ).grid(row=i // 4, column=i % 4, padx=2, pady=2)

        bar = tk.Frame(r, bg=self.BG)
        bar.pack(fill="x", padx=14, pady=(4, 6))
        self.b_go = self._btn(
            bar, "", self.toggle, font=("Segoe UI", 11, "bold"), width=22, height=2
        )
        self.b_go.pack(side="left")
        off = tk.Frame(bar, bg=self.BG)
        off.pack(side="right")
        self._lbl(off, text=T("fine"), fg="#a0a0b8", font=("Segoe UI", 8)).grid(
            row=0, column=0, columnspan=3
        )
        self._btn(off, "−5", lambda: self.nudge(-5), width=3).grid(row=1, column=0)
        self.v_off = tk.StringVar()
        self._lbl(off, textvariable=self.v_off, width=7).grid(row=1, column=1)
        self._btn(off, "+5", lambda: self.nudge(5), width=3).grid(row=1, column=2)

        self.b_set = self._btn(
            r, T("settings") + " ▾", self._toggle_settings, bg=self.BG, fg="#a0a0b8"
        )
        self.b_set.pack(anchor="w", padx=10)
        self.settings = tk.Frame(r, bg="#23232c")
        self._build_settings(self.settings)
        self._seq_refresh()

    def _build_settings(self, f):
        s = {"bg": "#23232c"}
        self._lbl(f, text=T("output"), **s).grid(
            row=0, column=0, sticky="w", padx=8, pady=4
        )
        self.v_out = tk.StringVar(value=self.cfg["output"])
        for i, k in enumerate(OUTPUTS):
            tk.Radiobutton(
                f,
                text=T("out_" + k),
                value=k,
                variable=self.v_out,
                command=self._apply,
                bg="#23232c",
                fg=self.FG,
                selectcolor="#23232c",
                activebackground="#23232c",
            ).grid(row=i, column=1, columnspan=4, sticky="w")
        self._lbl(f, text=T("keys"), **s).grid(
            row=3, column=0, sticky="w", padx=8, pady=4
        )
        self.v_keys = {}
        for i, d in enumerate(DRUMS):
            cell = tk.Frame(f, **s)
            cell.grid(row=3, column=1 + i, padx=3)
            self._lbl(cell, text=f"{d} {SYMBOL[d]}", fg=COLOR[d], **s).pack()
            v = self.v_keys[d] = tk.StringVar(value=self.cfg["keys"][d].upper())
            e = tk.Entry(
                cell,
                textvariable=v,
                width=3,
                justify="center",
                bg="#2c2c38",
                fg=self.FG,
                insertbackground=self.FG,
                relief="flat",
            )
            e.pack()
            v.trace_add("write", lambda *_: self._apply())
        self._lbl(f, text=T("lang"), **s).grid(
            row=4, column=0, sticky="w", padx=8, pady=4
        )
        self.v_lang = tk.StringVar(value=self.cfg["lang"])
        for i, (k, label) in enumerate((("es", "Español"), ("en", "English"))):
            tk.Radiobutton(
                f,
                text=label,
                value=k,
                variable=self.v_lang,
                command=self._set_lang,
                bg="#23232c",
                fg=self.FG,
                selectcolor="#23232c",
                activebackground="#23232c",
            ).grid(row=4, column=1 + 2 * i, columnspan=2, sticky="w")
        self.v_info = tk.StringVar()
        self._lbl(
            f,
            textvariable=self.v_info,
            fg="#a0a0b8",
            justify="left",
            font=("Segoe UI", 8),
            **s,
        ).grid(row=5, column=0, columnspan=5, sticky="w", padx=8, pady=6)

    def _toggle_settings(self):
        if self.settings.winfo_ismapped():
            self.settings.pack_forget()
            self.b_set.config(text=T("settings") + " ▾")
        else:
            self.settings.pack(fill="x", padx=14, pady=(0, 12))
            self.b_set.config(text=T("settings") + " ▴")

    def _set_lang(self):
        global LANG
        LANG = self.cfg["lang"] = self.v_lang.get()
        save_cfg(self.cfg)
        for w in self.root.winfo_children():
            w.destroy()
        self._build()
        self._toggle_settings()

    # ------------------------------------------------ secuencia
    def _seq_refresh(self):
        for w in self.seq_box.winfo_children():
            w.destroy()
        if not self.cfg["sequence"]:
            self._lbl(self.seq_box, text=T("seq_empty"), fg=self.DIM).pack(side="left")
        for i, name in enumerate(self.cfg["sequence"]):
            self._btn(
                self.seq_box,
                f"{i + 1}. {CN(name)}  ✕",
                lambda i=i: self._seq_del(i),
                bg="#34344a",
            ).pack(side="left", padx=2)
        save_cfg(self.cfg)

    def _seq_add(self, name):
        self.cfg["sequence"] = self.cfg["sequence"] + [name]
        self._seq_refresh()

    def _seq_del(self, i):
        seq = list(self.cfg["sequence"])
        del seq[i]
        self.cfg["sequence"] = seq
        self._seq_refresh()

    # ------------------------------------------------ acciones
    def _apply(self):
        changed = self.cfg["output"] != self.v_out.get()
        self.cfg["output"] = self.v_out.get()
        for d, v in self.v_keys.items():
            k = v.get().strip().lower()[:1]
            if k:
                self.cfg["keys"][d] = k
        save_cfg(self.cfg)
        if changed or self.cfg["output"] == "keyboard":
            self._make_out()

    def nudge(self, ms):
        eng = self.engine
        if eng.running and eng.bias is None and time.perf_counter() - eng.t0 > 20:
            n = eng.correct(ms / 1000)
            if len(eng.pts) >= 2:
                self.cfg["period_ms"] = eng.p * 1000
                self.cfg["period_weight"] = 2e4
                self.flash(T("tempo_fixed", p=eng.p * 1000))
            with LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(
                    f"{time.strftime('%H:%M:%S')}  beat={n:6.0f}  {ms:+d}  "
                    f"total={eng.total * 1000:+5.0f}ms  p={eng.p * 1000:.3f}  tandas={len(eng.pts) - 1}\n"
                )
        else:
            self.cfg["offset_ms"] += ms
            if eng.running:
                eng.rebase()
        save_cfg(self.cfg)

    def toggle(self):
        if self.engine.running:
            eng = self.engine
            eng.stop()
            self.last_run = time.perf_counter() - eng.t0
            if eng.bias is not None and time.perf_counter() - eng.t0 > 60:
                self.cfg["period_ms"], self.cfg["period_weight"] = eng.p * 1000, 2e4
                save_cfg(self.cfg)
                with LOG_PATH.open("a", encoding="utf-8") as f:
                    f.write(
                        f"{time.strftime('%H:%M:%S')}  marco: {time.perf_counter() - eng.t0:5.0f}s  "
                        f"p={eng.p * 1000:.3f}  ±{eng.jitter * 1000:.1f}ms  "
                        f"sesgo={eng.bias * 1000:+.0f}ms  offset={self.cfg['offset_ms']:+d}\n"
                    )
            self.learner.clear()
            self.flash(T("handback"))
            return
        sol = self.learner.solve()
        if not sol or len(sol["drums"]) < 4:
            self.flash(T("need_cmd"))
            return
        if self.cfg["output"] == "keyboard" and not sol["process"]:
            self.flash(T("no_game"))
            return
        if sol["process"]:
            self.cfg["process"] = sol["process"]
        g = self.sync.grid(avoid=sol["ts"])
        bias = None
        if g:
            # rejilla del marco; tus golpes solo eligen el compás y miden tu sesgo
            a, p = g
            res = statistics.median((t - a + p / 2) % p - p / 2 for t in sol["ts"])
            n = min(self.cfg["sync_bias_n"], 19)
            self.cfg["sync_bias_ms"] = (self.cfg["sync_bias_ms"] * n + res * 1000) / (
                n + 1
            )
            self.cfg["sync_bias_n"] = n + 1
            self.cfg["period_ms"], self.cfg["period_weight"] = p * 1000, 2e4
            bias = self.cfg["sync_bias_ms"] / 1000
            cycle = a + round((sol["cycle_start"] - res - a) / p) * p + bias
        else:
            if sol["weight"] > 0:
                w0 = min(self.cfg["period_weight"], 2e4)
                p_ms = sol["p"] * 1000
                self.cfg["period_ms"] = (
                    self.cfg["period_ms"] * w0 + p_ms * sol["weight"]
                ) / (w0 + sol["weight"])
                self.cfg["period_weight"] = w0 + sol["weight"]
            p = self.cfg["period_ms"] / 1000
            cycle = sol["cycle_start"]
            if (
                np is not None
            ):  # arranca con tu ritmo y se engancha al marco en cuanto lo vea
                bias = self.cfg["sync_bias_ms"] / 1000
        nxt = cycle + 8 * p
        late = False
        while nxt < time.perf_counter() + 0.05:
            nxt += 8 * p
            late = True
        try:
            self.engine.start(nxt, p, bias)
        except Exception as e:
            self.flash(f"Error: {e}", 6)
            return
        save_cfg(self.cfg)
        self.learner.clear()
        if late:
            self.flash(T("late"), 4)
        elif not g:
            self.flash(T("not_ready", s=self.sync.text()), 5)

    # ------------------------------------------------ dibujo
    def _draw(self, cmd_drums, beat, active):
        cv = self.cv
        cv.delete("all")
        for i in range(8):
            x = 30 + i * 57
            on = active and i == beat
            if i < 4:
                d = cmd_drums[i] if i < len(cmd_drums) else None
                col = COLOR[d] if d else self.DIM
                r = 25 if on else 19
                cv.create_oval(
                    x - r,
                    35 - r,
                    x + r,
                    35 + r,
                    fill=col if on else self.BG,
                    outline=col,
                    width=3,
                )
                if d:
                    cv.create_text(
                        x,
                        35,
                        text=SYMBOL[d],
                        fill=self.FG if on else col,
                        font=("Segoe UI", 16, "bold"),
                    )
            else:
                r = 9 if on else 6
                cv.create_oval(
                    x - r,
                    35 - r,
                    x + r,
                    35 + r,
                    fill="#8a8aa0" if on else self.DIM,
                    outline="",
                )

    def _tick(self):
        while not self.q.empty():
            self.q.get()()
        now = time.perf_counter()
        eng, cfg = self.engine, self.cfg
        bpm = 60000 / cfg["period_ms"]

        if eng.running:
            name = eng.cmd or (cfg["sequence"] or ["Avanzar"])[0]
            beat = int(math.floor((now - eng.cycle) / eng.p)) % 8 if eng.cmd else -1
            self._draw(COMMANDS[name], beat, eng.cmd is not None)
            st = T("unfocused") if eng.unfocused else T("bot_playing", c=CN(name))
            self.v_status.set(st)
            self.b_go.config(text=T("stop_btn"), bg="#8a2b2b")
        else:
            sol = self.learner.solve()
            if sol:
                p = sol["p"]
                beat = int(math.floor((now - sol["cycle_start"]) / p)) % 8
                fresh = now - sol["cycle_start"] < 16 * p
                self._draw(sol["drums"], beat, fresh)
                who = CN(sol["cmd"]) if sol["cmd"] else T("unknown_cmd")
                self.v_status.set(T("you", c=who))
            else:
                self._draw([], -1, False)
                self.v_status.set(T("idle"))
            self.b_go.config(text=T("go_btn"), bg="#2b6a3f")

        def hms(s):
            s = int(s)
            return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"

        if eng.running:
            self.v_timer.set(f"⏱ {hms(now - eng.t0)}")
        else:
            self.v_timer.set(
                T("last", t=hms(self.last_run)) if self.last_run is not None else ""
            )

        if now < self.msg_until:
            self.v_sub.set(self.msg)
        else:
            if eng.running:
                if eng.bias is None:
                    mark = T("mk_nosync")
                else:
                    mark = T("mk_sync") if eng.locked else T("mk_lost")
            else:
                mark = T("mk_seen") if self.sync.alive() else T("mk_none")
            self.v_sub.set(T("sub", bpm=bpm, mark=mark, out=T("out_" + cfg["output"])))
        self.v_off.set(f"{cfg['offset_ms']:+d} ms")
        jit = (
            f" · ±{eng.jitter * 1000:.1f} ms"
            if eng.running and eng.bias is not None
            else ""
        )
        pad = self.inputs.pad_name if hasattr(self, "inputs") else "…"
        self.v_info.set(
            T(
                "info",
                proc=cfg["process"] or "—",
                m=T(self.sync.method),
                st=self.sync.text(),
                hz=self.sync.hz,
                jit=jit,
                bias=cfg["sync_bias_ms"],
                pad=T(pad),
            )
        )
        self.root.after(15, self._tick)

    def _close(self):
        self.engine.stop()
        save_cfg(self.cfg)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
