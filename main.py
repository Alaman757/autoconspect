import io
import json
import mimetypes
import os
import uuid
import zipfile
import xml.etree.ElementTree as ET
import random
import ssl
import threading
import time
import urllib.error
import urllib.request

try:
    import requests
except Exception:
    requests = None

try:
    import certifi
except Exception:
    certifi = None

from kivy.app import App
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle, StencilPush, StencilPop, StencilUse, StencilUnUse
from kivy.metrics import dp, sp
from kivy.properties import ListProperty, NumericProperty, StringProperty, BooleanProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex, platform as kivy_platform

try:
    from plyer import filechooser
except Exception:
    filechooser = None

try:
    import secret_config
    GEMINI_API_KEY = getattr(secret_config, "GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", "")).strip()
    GROQ_API_KEY = getattr(secret_config, "GROQ_API_KEY", os.environ.get("GROQ_API_KEY", "")).strip()
except Exception:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MAX_AUDIO_BYTES = 25 * 1024 * 1024

MODEL_OPTIONS = [
    {
        "label": "Gemini 2.5 Flash Lite",
        "short": "2.5 Lite",
        "provider": "gemini",
        "code": "gemini-2.5-flash-lite",
        "api_version": "v1beta",
        "hint": "Быстрая и стабильная. Основная модель по умолчанию.",
    },
    {
        "label": "Groq Llama 3.1 8B",
        "short": "Groq 8B",
        "provider": "groq",
        "code": "llama-3.1-8b-instant",
        "hint": "Очень быстрый. Хорош для коротких конспектов.",
    },
    {
        "label": "Groq Llama 3.3 70B",
        "short": "Groq 70B",
        "provider": "groq",
        "code": "llama-3.3-70b-versatile",
        "hint": "Более сильная модель. Лучше качество, чуть медленнее.",
    },
    {
        "label": "Groq Qwen3 32B",
        "short": "Groq Qwen",
        "provider": "groq",
        "code": "qwen/qwen3-32b",
        "hint": "Альтернативная Groq-модель. Хорошо держит структуру.",
    },
]

DETAIL_OPTIONS = {
    "short": {"label": "Кратко", "tokens": 600, "desc": "120-180 слов"},
    "normal": {"label": "Стандарт", "tokens": 1500, "desc": "400-650 слов"},
    "full": {"label": "Подробно", "tokens": 3600, "desc": "900-1400 слов"},
}

PRIMARY_MODEL = "gemini-2.5-flash-lite"
FALLBACK_MODEL = "llama-3.1-8b-instant"
MAX_ATTEMPTS = 3
TIMEOUT_SEC = 180

SYSTEM_PROMPT = """Ты профессиональный составитель учебных конспектов. Пиши на русском языке.

Задача: превращать тему, кусок текста или описание в понятный структурированный конспект.

Правила:
- не пиши вводные фразы вроде "Конечно" или "Вот конспект";
- не выдумывай факты, если тема слишком общая;
- пиши ясно, без воды;
- используй заголовки, списки и короткие абзацы;
- ключевые понятия объясняй простыми словами;
- в конце добавляй блок "Главное запомнить".

Формат:
НАЗВАНИЕ ТЕМЫ

Краткая суть:
2-4 предложения.

Основные пункты:
- пункт
- пункт
- пункт

Ключевые понятия:
- термин: объяснение

Главное запомнить:
1. мысль
2. мысль
3. мысль
"""

# ─── Palette ───────────────────────────────────────────────────────────────────
BG          = "#0B0D10"
BG2         = "#10141A"
BG3         = "#151B23"
CARD        = "#161D26"
CARD2       = "#1D2632"
BORDER      = "#2B3645"
BORDER2     = "#3B485C"
CYAN        = "#42D7C4"
CYAN_DIM    = "#2FAEA2"
PURPLE      = "#E66A86"
PURPLE_DIM  = "#A9415A"
TEXT        = "#F4F7FB"
TEXT2       = "#B9C3D0"
TEXT3       = "#778292"
GREEN       = "#48C78E"
AMBER       = "#F2B84B"
RED         = "#FF6B6B"


def c(h):
    return get_color_from_hex(h)


def ca(h, alpha):
    rgba = list(get_color_from_hex(h))
    rgba[3] = alpha
    return rgba


def make_ssl_context():
    try:
        if certifi:
            return ssl.create_default_context(cafile=certifi.where())
        return ssl.create_default_context()
    except Exception:
        return None


SSL_CONTEXT = make_ssl_context()


# ─── Base Widgets ───────────────────────────────────────────────────────────────

class HistoryCard(ButtonBehavior, BoxLayout):
    """BoxLayout with button tap behaviour — for history list items."""
    pass


class UploadZone(ButtonBehavior, BoxLayout):
    """Tap anywhere in the upload card to pick a file."""
    pass


class GlassCard(FloatLayout):
    """Card with glass-like background: solid dark fill + subtle border."""
    def __init__(self, bg=CARD, border=BORDER, radius=dp(20), **kw):
        super().__init__(**kw)
        self._bg = bg
        self._border = border
        self._radius = radius
        with self.canvas.before:
            self._bg_col = Color(*c(bg))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            self._bdr_col = Color(*ca(border, 0.8))
            self._bdr = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, radius), width=1.2)
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *a):
        self._bg_col.rgba = c(self._bg)
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._rect.radius = [self._radius]
        self._bdr_col.rgba = ca(self._border, 0.8)
        self._bdr.rounded_rectangle = (self.x, self.y, self.width, self.height, self._radius)


class NeonDot(Widget):
    """Small accent dot."""
    def __init__(self, color_hex=CYAN, size_dp=6, **kw):
        super().__init__(size_hint=(None, None), size=(dp(size_dp), dp(size_dp)), **kw)
        with self.canvas:
            Color(*c(color_hex))
            self._e = Ellipse(pos=self.pos, size=self.size)
        self.bind(pos=lambda *a: setattr(self._e, 'pos', self.pos))



class AppBackground(FloatLayout):
    """Flat minimal background."""
    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(*c(BG))
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size


# ─── Reusable label factory ─────────────────────────────────────────────────────

def lbl(text, size=14, color_hex=TEXT, bold=False, halign="left", fixed_h=None, markup=False):
    l = Label(
        text=text,
        font_size=sp(size),
        color=c(color_hex),
        bold=bold,
        halign=halign,
        valign="middle",
        markup=markup,
        size_hint_y=None,
    )
    l.bind(width=lambda inst, v: setattr(inst, "text_size", (v, None)))
    if fixed_h:
        l.height = dp(fixed_h)
    else:
        l.bind(texture_size=lambda inst, v: setattr(inst, "height", v[1] + dp(6)))
    return l



class DrawIcon(Widget):
    """Canvas icons. Android-safe: no emoji/unicode squares."""
    def __init__(self, kind="home", color_hex=TEXT3, **kw):
        super().__init__(**kw)
        self.kind = kind
        self.color_hex = color_hex
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def set_color(self, color_hex):
        self.color_hex = color_hex
        self._redraw()

    def _redraw(self, *a):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
        x, y = self.pos
        w, h = self.size
        cx, cy = x + w / 2, y + h / 2
        s = min(w, h)
        with self.canvas:
            Color(*c(self.color_hex))
            if self.kind == "home":
                Line(points=[cx-s*.36, cy-s*.03, cx, cy+s*.32, cx+s*.36, cy-s*.03], width=1.25)
                Line(points=[cx-s*.25, cy-s*.02, cx-s*.25, cy-s*.32, cx-s*.08, cy-s*.32, cx-s*.08, cy-s*.15, cx+s*.08, cy-s*.15, cx+s*.08, cy-s*.32, cx+s*.25, cy-s*.32, cx+s*.25, cy-s*.02], width=1.25)
            elif self.kind == "history":
                Line(circle=(cx, cy, s*.32), width=1.3)
                Line(points=[cx, cy, cx, cy+s*.16, cx+s*.15, cy+s*.03], width=1.3)
            elif self.kind == "mic":
                Line(rounded_rectangle=(cx-s*.15, cy-s*.03, s*.30, s*.40, s*.15), width=1.45)
                Line(points=[cx-s*.30, cy, cx-s*.30, cy-s*.12, cx-s*.22, cy-s*.26, cx-s*.10, cy-s*.33, cx, cy-s*.35, cx+s*.10, cy-s*.33, cx+s*.22, cy-s*.26, cx+s*.30, cy-s*.12, cx+s*.30, cy], width=1.25)
                Line(points=[cx, cy-s*.35, cx, cy-s*.50], width=1.25)
                Line(points=[cx-s*.18, cy-s*.50, cx+s*.18, cy-s*.50], width=1.25)
            elif self.kind == "upload":
                # cloud outline
                Line(points=[
                    cx-s*.34, cy-s*.05,
                    cx-s*.28, cy+s*.08,
                    cx-s*.14, cy+s*.11,
                    cx-s*.06, cy+s*.24,
                    cx+s*.10, cy+s*.24,
                    cx+s*.20, cy+s*.10,
                    cx+s*.34, cy+s*.06,
                    cx+s*.38, cy-s*.05,
                ], width=1.45)
                # upload arrow
                Line(points=[cx, cy-s*.24, cx, cy+s*.12], width=1.55)
                Line(points=[cx-s*.15, cy-s*.02, cx, cy+s*.13, cx+s*.15, cy-s*.02], width=1.55)
            elif self.kind == "spark":
                Line(points=[cx, cy+s*.36, cx-s*.11, cy+s*.07, cx-s*.35, cy, cx-s*.10, cy-s*.07, cx, cy-s*.36, cx+s*.10, cy-s*.07, cx+s*.35, cy, cx+s*.10, cy+s*.07, cx, cy+s*.36], width=1.2)
            elif self.kind == "search":
                Line(circle=(cx-s*.04, cy+s*.04, s*.23), width=1.25)
                Line(points=[cx+s*.13, cy-s*.13, cx+s*.34, cy-s*.34], width=1.25)
            elif self.kind == "file":
                Line(points=[cx-s*.22, cy+s*.32, cx+s*.10, cy+s*.32, cx+s*.25, cy+s*.17, cx+s*.25, cy-s*.32, cx-s*.22, cy-s*.32, cx-s*.22, cy+s*.32], width=1.2)
                Line(points=[cx+s*.10, cy+s*.32, cx+s*.10, cy+s*.17, cx+s*.25, cy+s*.17], width=1.2)
            else:
                Line(circle=(cx, cy, s*.25), width=1.2)


class GradientLogo(FloatLayout):
    """Minimal logo tile."""
    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(*c(PURPLE))
            self._base = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
            Color(*ca("#FFFFFF", 0.20))
            self._line = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(10)), width=1)
        self.icon = DrawIcon(kind="spark", color_hex="#FFFFFF", size_hint=(None, None), size=(dp(20), dp(20)))
        self.add_widget(self.icon)
        self.bind(pos=self._upd, size=self._upd)
        self._upd()

    def _upd(self, *a):
        self._base.pos = self.pos
        self._base.size = self.size
        self._base.radius = [dp(10)]
        self._line.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(10))
        self.icon.pos = (self.center_x - self.icon.width / 2, self.center_y - self.icon.height / 2)


# ─── Pill / Chip button ─────────────────────────────────────────────────────────

class PillBtn(Button):
    def __init__(self, text, bg=CARD2, fg=TEXT, h=dp(48), **kw):
        self._fill_hex = bg
        self._fill_alpha = 1.0
        self._border_hex = BORDER
        super().__init__(
            text=text,
            size_hint_y=None,
            height=h,
            background_normal="",
            background_down="",
            background_color=(0, 0, 0, 0),
            color=c(fg),
            bold=False,
            font_size=sp(13),
            **kw
        )
        with self.canvas.before:
            self._pill_fill_col = Color(*ca(bg, self._fill_alpha))
            self._pill_fill = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
            self._pill_bc = Color(*ca(BORDER, 0.45))
            self._pill_bl = Line(rounded_rectangle=(0, 0, 10, 10, dp(10)), width=1)
        self.bind(pos=self._upd_canvas, size=self._upd_canvas)
        self._upd_canvas()

    def _upd_canvas(self, *a):
        self._pill_fill_col.rgba = ca(self._fill_hex, self._fill_alpha)
        self._pill_fill.pos = self.pos
        self._pill_fill.size = self.size
        self._pill_fill.radius = [dp(10)]
        self._pill_bc.rgba = ca(self._border_hex, 0.55)
        self._pill_bl.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(10))

    def set_style(self, bg, fg, border=None, alpha=1.0):
        self._fill_hex = bg
        self._fill_alpha = alpha
        self._border_hex = border or BORDER
        self.color = c(fg)
        self.bold = (fg == BG)
        self._upd_canvas()

    def set_active(self, active):
        if active:
            self.set_style(CYAN, BG, CYAN, 1.0)
        else:
            self.set_style(BG, TEXT2, BORDER, 0.0)


class AccentBtn(Button):
    """Primary CTA button."""
    def __init__(self, text, **kw):
        self._fill_hex = CYAN
        super().__init__(
            text=text,
            size_hint_y=None,
            height=dp(50),
            background_normal="",
            background_down="",
            background_color=(0, 0, 0, 0),
            color=c(BG),
            bold=True,
            font_size=sp(15),
            **kw
        )
        with self.canvas.before:
            self._accent_col = Color(*c(self._fill_hex))
            self._accent_bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])
        self.bind(pos=self._upd_canvas, size=self._upd_canvas)
        self._upd_canvas()

    def _upd_canvas(self, *a):
        self._accent_col.rgba = c(self._fill_hex)
        self._accent_bg.pos = self.pos
        self._accent_bg.size = self.size
        self._accent_bg.radius = [dp(12)]

    def set_fill(self, color_hex, fg=BG):
        self._fill_hex = color_hex
        self.color = c(fg)
        self._upd_canvas()


class GhostBtn(Button):
    def __init__(self, text, fg=TEXT2, **kw):
        self._fill_hex = CARD2
        self._fill_alpha = 0.0
        super().__init__(
            text=text,
            size_hint_y=None,
            height=dp(48),
            background_normal="",
            background_down="",
            background_color=(0, 0, 0, 0),
            color=c(fg),
            bold=False,
            font_size=sp(13),
            **kw
        )
        with self.canvas.before:
            self._ghost_col = Color(*ca(self._fill_hex, self._fill_alpha))
            self._ghost_bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
            self._ghost_bc = Color(*ca(BORDER, 0.50))
            self._ghost_bl = Line(rounded_rectangle=(0, 0, 10, 10, dp(10)), width=1)
        self.bind(pos=self._upd_canvas, size=self._upd_canvas)
        self._upd_canvas()

    def _upd_canvas(self, *a):
        self._ghost_col.rgba = ca(self._fill_hex, self._fill_alpha)
        self._ghost_bg.pos = self.pos
        self._ghost_bg.size = self.size
        self._ghost_bg.radius = [dp(10)]
        self._ghost_bc.rgba = ca(BORDER, 0.50)
        self._ghost_bl.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(10))


# ─── Nav bar ────────────────────────────────────────────────────────────────────


class NavBar(FloatLayout):
    def __init__(self, on_generator, on_history, on_mic, **kw):
        super().__init__(size_hint_y=None, height=dp(72), **kw)
        self.on_generator = on_generator
        self.on_history = on_history
        self.on_mic = on_mic

        with self.canvas.before:
            Color(*c(BG2))
            self._bg = Rectangle(pos=self.pos, size=self.size)
            Color(*ca(BORDER, 0.55))
            self._top_line = Line(points=[], width=1)

        self.gen_btn, self.gen_icon, self.gen_name = self._tab("Генератор", "home", True, on_generator)
        self.hist_btn, self.hist_icon, self.hist_name = self._tab("История", "history", False, on_history)
        self.add_widget(self.gen_btn)
        self.add_widget(self.hist_btn)

        self.mic_btn = Button(
            size_hint=(None, None),
            size=(dp(52), dp(52)),
            background_normal="",
            background_down="",
            background_color=(0, 0, 0, 0),
        )
        with self.mic_btn.canvas.before:
            Color(*ca(PURPLE, 0.74))
            self._mic_outer = Ellipse(pos=self.mic_btn.pos, size=(dp(62), dp(62)))
            Color(*c(CYAN))
            self._mic_inner = Ellipse(pos=self.mic_btn.pos, size=self.mic_btn.size)
        self.mic_icon = DrawIcon(kind="mic", color_hex=BG, size_hint=(None, None), size=(dp(26), dp(26)))
        self.mic_btn.add_widget(self.mic_icon)
        self.mic_btn.bind(on_release=on_mic)
        self.add_widget(self.mic_btn)

        self.bind(pos=self._upd, size=self._upd)
        Clock.schedule_once(lambda dt: self._upd(), 0)

    def _tab(self, name, kind, active, callback):
        btn = Button(
            size_hint=(None, None),
            background_normal="",
            background_down="",
            background_color=(0, 0, 0, 0),
        )
        icon = DrawIcon(kind=kind, color_hex=CYAN if active else TEXT3, size_hint=(None, None), size=(dp(22), dp(22)))
        label = Label(
            text=name,
            font_size=sp(10),
            bold=False,
            color=c(CYAN if active else TEXT3),
            halign="center",
            valign="middle",
            size_hint=(None, None),
        )
        label.bind(size=lambda inst, v: setattr(inst, "text_size", v))
        btn.add_widget(icon)
        btn.add_widget(label)
        btn._icon = icon
        btn._name = label
        btn.bind(on_release=callback)
        return btn, icon, label

    def set_active(self, tab):
        active_gen = tab == "gen"
        self.gen_icon.set_color(CYAN if active_gen else TEXT3)
        self.gen_name.color = c(CYAN if active_gen else TEXT3)
        self.hist_icon.set_color(CYAN if not active_gen else TEXT3)
        self.hist_name.color = c(CYAN if not active_gen else TEXT3)

    def _place_tab(self, btn, icon, label):
        icon.pos = (btn.center_x - dp(11), btn.y + dp(30))
        label.pos = (btn.x, btn.y + dp(10))
        label.size = (btn.width, dp(16))

    def _upd(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._top_line.points = [self.x, self.top, self.right, self.top]

        tab_w = max(dp(112), (self.width - dp(88)) / 2)
        self.gen_btn.pos = (self.x, self.y)
        self.gen_btn.size = (tab_w, self.height)
        self.hist_btn.pos = (self.right - tab_w, self.y)
        self.hist_btn.size = (tab_w, self.height)

        self._place_tab(self.gen_btn, self.gen_icon, self.gen_name)
        self._place_tab(self.hist_btn, self.hist_icon, self.hist_name)

        self.mic_btn.pos = (self.center_x - dp(26), self.y + dp(10))
        self._mic_outer.pos = (self.center_x - dp(31), self.y + dp(5))
        self._mic_outer.size = (dp(62), dp(62))
        self._mic_inner.pos = self.mic_btn.pos
        self._mic_inner.size = self.mic_btn.size
        self.mic_icon.pos = (self.mic_btn.center_x - dp(13), self.mic_btn.center_y - dp(13))


# ─── Status chip ────────────────────────────────────────────────────────────────

class StatusChip(BoxLayout):
    def __init__(self, **kw):
        super().__init__(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(32),
            spacing=dp(8),
            padding=[dp(12), 0, dp(12), 0],
            **kw
        )
        with self.canvas.before:
            self._col = Color(*c(CARD))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
            self._bdr = Color(*ca(BORDER, 0.45))
            self._line = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(8)), width=1)
        self.bind(pos=self._upd, size=self._upd)

        self._dot_widget = Widget(size_hint=(None, 1), width=dp(6))
        with self._dot_widget.canvas:
            self._dot_col2 = Color(*c(GREEN))
            self._dot_e = Ellipse(size=(dp(6), dp(6)))
        self._dot_widget.bind(pos=self._upd_dot, size=self._upd_dot)

        self._title_lbl = Label(font_size=sp(12), bold=True, color=c(GREEN),
                                size_hint_x=None, width=dp(110), halign="left", valign="middle",
                                shorten=True, shorten_from="right")
        self._title_lbl.bind(size=lambda inst, v: setattr(inst, "text_size", v))

        self._text_lbl = Label(font_size=sp(11), color=c(TEXT3), halign="left",
                               valign="middle", shorten=True, shorten_from="right")
        self._text_lbl.bind(size=lambda inst, v: setattr(inst, "text_size", v))

        self.add_widget(self._dot_widget)
        self.add_widget(self._title_lbl)
        self.add_widget(self._text_lbl)
        Clock.schedule_once(lambda dt: self._upd_dot(), 0)

    def update(self, title, text, color_hex=GREEN):
        self._title_lbl.text = title
        self._title_lbl.color = c(color_hex)
        self._dot_col2.rgba = c(color_hex)
        self._text_lbl.text = text

    def _upd(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._rect.radius = [dp(8)]
        self._line.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(8))
        self._upd_dot()

    def _upd_dot(self, *a):
        self._dot_e.pos = (
            self._dot_widget.center_x - dp(3),
            self._dot_widget.center_y - dp(3),
        )
        self._dot_e.size = (dp(6), dp(6))


# ─── Screen: Generator ──────────────────────────────────────────────────────────


class GeneratorScreen(ScrollView):
    def __init__(self, app, **kw):
        super().__init__(
            size_hint=(1, 1),
            bar_width=dp(2),
            bar_color=ca(BORDER2, 0.6),
            bar_inactive_color=ca(BORDER, 0.2),
            scroll_type=["bars", "content"],
            **kw
        )
        self.app = app
        self.content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=[dp(20), dp(8), dp(20), dp(16)],
            spacing=dp(6),
        )
        self.content.bind(minimum_height=self.content.setter("height"))
        self.add_widget(self.content)
        self._build()

    def _glass(self, widget, bg=CARD, border=BORDER, radius=12, alpha=1.0, border_alpha=0.45, dashed=False):
        with widget.canvas.before:
            bgc = Color(*ca(bg, alpha))
            rr = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[dp(radius)])
            bc = Color(*ca(border, border_alpha))
            ln = Line(rounded_rectangle=(widget.x, widget.y, widget.width, widget.height, dp(radius)), width=1)
        def upd(*a):
            bgc.rgba = ca(bg, alpha)
            rr.pos = widget.pos
            rr.size = widget.size
            rr.radius = [dp(radius)]
            bc.rgba = ca(border, border_alpha)
            ln.rounded_rectangle = (widget.x, widget.y, widget.width, widget.height, dp(radius))
        widget.bind(pos=upd, size=upd)
        upd()

    def _build(self):
        c_ = self.content
        app = self.app

        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(12))
        logo = GradientLogo(size_hint=(None, None), size=(dp(36), dp(36)))
        header.add_widget(logo)

        title_box = BoxLayout(orientation="vertical", spacing=dp(2))
        title_box.add_widget(lbl("Автоконспект", 18, TEXT, True, fixed_h=24))
        title_box.add_widget(lbl("Конспекты из текста и файлов", 11, TEXT3, fixed_h=16))
        header.add_widget(title_box)

        app.model_btn = Button(
            text="Модель",
            size_hint=(None, None),
            size=(dp(80), dp(34)),
            background_normal="",
            background_down="",
            background_color=(0, 0, 0, 0),
            color=c(TEXT2),
            bold=False,
            font_size=sp(11),
        )
        with app.model_btn.canvas.before:
            _mb_fill = Color(*ca(CARD, 1.0))
            _mb_rect = RoundedRectangle(pos=app.model_btn.pos, size=app.model_btn.size, radius=[dp(8)])
            _mb_col = Color(*ca(BORDER, 0.55))
            _mb_line = Line(rounded_rectangle=(0, 0, dp(80), dp(34), dp(8)), width=1)
        def _upd_mb(*a):
            _mb_fill.rgba = ca(CARD, 1.0)
            _mb_rect.pos = app.model_btn.pos
            _mb_rect.size = app.model_btn.size
            _mb_rect.radius = [dp(8)]
            _mb_col.rgba = ca(BORDER, 0.55)
            _mb_line.rounded_rectangle = (app.model_btn.x, app.model_btn.y, app.model_btn.width, app.model_btn.height, dp(8))
        app.model_btn.bind(pos=_upd_mb, size=_upd_mb)
        app.model_btn.bind(on_release=app.open_model_modal)
        header.add_widget(app.model_btn)
        c_.add_widget(header)

        stat_wrap = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(16))
        app.stat_label = lbl("Сегодня обработано: 0 файлов", 10, TEXT3, fixed_h=16)
        stat_wrap.add_widget(app.stat_label)
        stat_wrap.add_widget(Widget())
        c_.add_widget(stat_wrap)

        upload = UploadZone(orientation="vertical", size_hint_y=None, height=dp(92),
                           padding=[dp(16), dp(10), dp(16), dp(10)], spacing=dp(4))
        self._glass(upload, bg=CARD, border=BORDER, radius=12, alpha=1.0, border_alpha=0.45)
        upload.bind(on_release=app.pick_file)

        up_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(22), spacing=dp(8))
        up_icon = DrawIcon(kind="upload", color_hex=TEXT3, size_hint=(None, None), size=(dp(18), dp(18)))
        up_row.add_widget(up_icon)
        t = Label(text="Добавьте файл или аудио", font_size=sp(13), color=c(TEXT2), bold=False,
                  halign="left", valign="middle", size_hint_y=None, height=dp(22))
        t.bind(size=lambda inst, v: setattr(inst, "text_size", v))
        up_row.add_widget(t)
        upload.add_widget(up_row)

        file_btn = GhostBtn("Выбрать материал", fg=TEXT2)
        file_btn.height = dp(32)
        file_btn.size_hint_x = 1
        file_btn.bind(on_release=app.pick_file)
        upload.add_widget(file_btn)
        c_.add_widget(upload)

        input_wrap = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(72), padding=[dp(14), dp(8), dp(14), dp(8)])
        self._glass(input_wrap, bg=CARD, border=BORDER, radius=12, alpha=1.0, border_alpha=0.45)
        app.topic_input = TextInput(
            hint_text="Вставь тему, текст или ссылку для конспекта...",
            font_size=sp(14),
            background_normal="",
            background_active="",
            background_color=(0, 0, 0, 0),
            foreground_color=c(TEXT),
            hint_text_color=c(TEXT3),
            cursor_color=c(CYAN),
            multiline=True,
            padding=[0, dp(6), 0, 0],
        )
        input_wrap.add_widget(app.topic_input)
        c_.add_widget(input_wrap)

        app.file_label = Label(
            text="Файл не добавлен: TXT · DOCX · PDF · MP3 · M4A · WAV",
            font_size=sp(10),
            color=c(TEXT3),
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(18),
        )
        app.file_label.bind(size=lambda inst, v: setattr(inst, "text_size", v))
        c_.add_widget(app.file_label)

        chip_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(32), spacing=dp(8))
        app.detail_buttons = {}
        for key, info in DETAIL_OPTIONS.items():
            btn = PillBtn(info["label"], h=dp(32))
            btn.bind(on_release=lambda inst, mode=key: app.set_detail_mode(mode))
            chip_row.add_widget(btn)
            app.detail_buttons[key] = btn
        c_.add_widget(chip_row)

        app.status_chip = StatusChip()
        c_.add_widget(app.status_chip)

        action_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
        app.generate_btn = AccentBtn("Создать конспект")
        app.generate_btn.height = dp(40)
        app.generate_btn.bind(on_release=app.on_generate)
        clear_btn = GhostBtn("Очистить", fg=TEXT2)
        clear_btn.height = dp(40)
        clear_btn.size_hint_x = 0.38
        clear_btn.bind(on_release=app.on_clear)
        action_row.add_widget(app.generate_btn)
        action_row.add_widget(clear_btn)
        c_.add_widget(action_row)

        out_card = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(12), padding=[dp(16), dp(14), dp(16), dp(14)])
        out_card.bind(minimum_height=out_card.setter("height"))
        self._glass(out_card, bg=CARD, border=BORDER, radius=12, alpha=1.0, border_alpha=0.45)

        out_top = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(2))
        app.output_title = lbl("Конспект", 15, TEXT, True, fixed_h=20)
        app.output_meta = lbl("Здесь появится готовый конспект", 11, TEXT3, fixed_h=16)
        out_top.add_widget(app.output_title)
        out_top.add_widget(app.output_meta)
        out_card.add_widget(out_top)

        result_bg = BoxLayout(orientation="vertical", size_hint_y=None, padding=[dp(12), dp(10), dp(12), dp(10)])
        result_bg.bind(minimum_height=result_bg.setter("height"))
        self._glass(result_bg, bg=BG2, border=BORDER, radius=10, alpha=1.0, border_alpha=0.35)

        app.output_label = Label(
            text="Пока пусто. Введи тему или добавь файл и нажми «Создать конспект».",
            font_size=sp(13),
            color=c(TEXT3),
            halign="left",
            valign="top",
            markup=False,
            size_hint_y=None,
        )
        app.output_label.bind(width=lambda inst, v: setattr(inst, "text_size", (v, None)))
        app.output_label.bind(texture_size=lambda inst, v: setattr(inst, "height", max(v[1] + dp(10), dp(90))))
        result_bg.add_widget(app.output_label)
        out_card.add_widget(result_bg)

        copy_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(8))
        copy_btn = GhostBtn("Копировать", fg=TEXT2)
        copy_btn.height = dp(40)
        copy_btn.bind(on_release=app.copy_result)
        remove_file_btn = GhostBtn("Убрать файл", fg=TEXT3)
        remove_file_btn.height = dp(40)
        remove_file_btn.bind(on_release=app.clear_loaded_file)
        copy_row.add_widget(copy_btn)
        copy_row.add_widget(remove_file_btn)
        out_card.add_widget(copy_row)

        c_.add_widget(out_card)

        app.set_detail_mode("normal")

    def _upd_upload(self, *a):
        pass

    def _upd_out(self, *a):
        pass


# ─── Screen: History ────────────────────────────────────────────────────────────



class HistoryScreen(BoxLayout):
    def __init__(self, app, **kw):
        super().__init__(
            orientation="vertical",
            size_hint=(1, 1),
            padding=[dp(20), dp(16), dp(20), dp(20)],
            spacing=dp(12),
            **kw
        )
        self.app = app
        self.filter_mode = "today"
        self._build()

    def _paint_card(self, widget, bg=CARD, border=BORDER, radius=16, alpha=1.0, border_alpha=0.65):
        with widget.canvas.before:
            bgc = Color(*ca(bg, alpha))
            rect = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[dp(radius)])
            bc = Color(*ca(border, border_alpha))
            line = Line(rounded_rectangle=(widget.x, widget.y, widget.width, widget.height, dp(radius)), width=1)
        def upd(*a):
            bgc.rgba = ca(bg, alpha)
            rect.pos = widget.pos
            rect.size = widget.size
            rect.radius = [dp(radius)]
            bc.rgba = ca(border, border_alpha)
            line.rounded_rectangle = (widget.x, widget.y, widget.width, widget.height, dp(radius))
        widget.bind(pos=upd, size=upd)
        upd()

    def _build(self):
        head = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(48), spacing=dp(2))
        head.add_widget(lbl("История", 20, TEXT, True, fixed_h=28))
        head.add_widget(lbl("Сохранённые конспекты", 11, TEXT3, fixed_h=16))
        self.add_widget(head)

        search_box = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(8), padding=[dp(12), 0, dp(12), 0])
        self._paint_card(search_box, bg=CARD, border=BORDER, radius=10, alpha=1.0, border_alpha=0.45)
        search_box.add_widget(DrawIcon(kind="search", color_hex=TEXT3, size_hint=(None, None), size=(dp(20), dp(44))))
        self.search_input = TextInput(
            text="",
            hint_text="Найти конспект...",
            multiline=False,
            font_size=sp(15),
            background_normal="",
            background_active="",
            background_color=(0, 0, 0, 0),
            foreground_color=c(TEXT),
            hint_text_color=c(TEXT3),
            cursor_color=c(CYAN),
            padding=[0, dp(13), 0, 0],
            size_hint=(1, 1),
        )
        self.search_input.bind(text=lambda *a: self.refresh(self.app.history))
        search_box.add_widget(self.search_input)
        self.add_widget(search_box)

        self.filter_buttons = {}
        tabs = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(8))
        for mode, title in [("today", "Сегодня"), ("week", "Неделя"), ("month", "Месяц")]:
            btn = PillBtn(title, h=dp(40))
            btn.bind(on_release=lambda inst, m=mode: self.set_filter(m))
            self.filter_buttons[mode] = btn
            tabs.add_widget(btn)
        self.add_widget(tabs)

        self.scroll = ScrollView(
            size_hint=(1, 1),
            bar_width=dp(2),
            bar_color=ca(BORDER2, 0.6),
            bar_inactive_color=ca(BORDER, 0.2),
            scroll_type=["bars", "content"],
        )
        self._history_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8), padding=[0, dp(2), 0, dp(12)])
        self._history_box.bind(minimum_height=self._history_box.setter("height"))
        self.scroll.add_widget(self._history_box)
        self.add_widget(self.scroll)

        self.set_filter("today", refresh=False)
        Clock.schedule_once(lambda dt: self.refresh(self.app.history), 0)

    def set_filter(self, mode, refresh=True):
        self.filter_mode = mode
        for key, btn in self.filter_buttons.items():
            btn.set_active(key == mode)
        if refresh:
            self.refresh(self.app.history)

    def _passes_filter(self, item):
        ts = item.get("ts")
        if not ts:
            return True
        try:
            age = time.time() - float(ts)
        except Exception:
            return True
        if self.filter_mode == "today":
            return age <= 24 * 60 * 60
        if self.filter_mode == "week":
            return age <= 7 * 24 * 60 * 60
        if self.filter_mode == "month":
            return age <= 31 * 24 * 60 * 60
        return True

    def refresh(self, history):
        self._history_box.clear_widgets()
        q = (self.search_input.text or "").strip().lower()
        items = []
        for item in history:
            title = str(item.get("title", "Конспект"))
            body = str(item.get("text", ""))
            model = str(item.get("model", ""))
            mode = str(item.get("mode", ""))
            if q and q not in title.lower() and q not in body.lower() and q not in model.lower() and q not in mode.lower():
                continue
            if not self._passes_filter(item):
                continue
            items.append(item)

        if not items:
            empty_card = BoxLayout(size_hint_y=None, height=dp(64), padding=[dp(14), 0, dp(14), 0])
            self._paint_card(empty_card, bg=CARD, border=BORDER, radius=12, alpha=1.0, border_alpha=0.45)
            empty = Label(text="Здесь появятся сохранённые конспекты.", font_size=sp(13), color=c(TEXT3), halign="center", valign="middle")
            empty.bind(size=lambda inst, v: setattr(inst, "text_size", v))
            empty_card.add_widget(empty)
            self._history_box.add_widget(empty_card)
            return

        for idx, item in enumerate(items[:30]):
            self._history_box.add_widget(self._make_card(idx, item))

    def _make_card(self, idx, item):
        row = HistoryCard(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(68),
            spacing=dp(12),
            padding=[dp(14), dp(10), dp(14), dp(10)],
        )
        self._paint_card(row, bg=CARD, border=BORDER, radius=12, alpha=1.0, border_alpha=0.45)

        av = Label(
            text=(str(item.get("title", "?"))[:1].upper() or "?"),
            font_size=sp(15),
            bold=True,
            color=c(TEXT2),
            size_hint=(None, None),
            size=(dp(40), dp(40)),
            halign="center",
            valign="middle",
        )
        av.bind(size=lambda inst, v: setattr(inst, "text_size", v))
        with av.canvas.before:
            Color(*ca(BORDER, 0.35))
            av_bg = Ellipse(pos=av.pos, size=av.size)
        av.bind(pos=lambda inst, v: setattr(av_bg, "pos", v))
        av.bind(size=lambda inst, v: setattr(av_bg, "size", v))

        mid = BoxLayout(orientation="vertical", spacing=dp(2))
        title_str = str(item.get("title", "Конспект"))
        body = str(item.get("text", ""))
        preview = (body[:60] + "…") if len(body) > 60 else body[:60]
        mid.add_widget(lbl(title_str[:36], 13, TEXT, True, fixed_h=18))
        mid.add_widget(lbl(preview.replace("\n", " "), 11, TEXT3, fixed_h=16))
        mid.add_widget(lbl(f"{item.get('model', 'Модель')} · {item.get('mode', 'Стандарт')}", 10, TEXT3, fixed_h=14))

        chevron = Label(
            text="›",
            font_size=sp(20),
            bold=False,
            color=c(TEXT3),
            size_hint=(None, None),
            size=(dp(18), dp(40)),
            halign="center",
            valign="middle",
        )
        chevron.bind(size=lambda inst, v: setattr(inst, "text_size", v))

        row.add_widget(av)
        row.add_widget(mid)
        row.add_widget(chevron)

        row.bind(on_release=lambda inst, i=item: self.app.load_history_item_direct(i))
        return row


# ─── Main App ───────────────────────────────────────────────────────────────────

class AutoConspectApp(App):
    def build(self):
        Window.clearcolor = c(BG)

        self.selected_model = PRIMARY_MODEL
        self.detail_mode = "normal"
        self.last_result = ""
        self.last_model_used = ""
        self.request_running = False
        self.loaded_file_text = ""
        self.loaded_file_name = ""
        self.history = self.load_history()
        self.files_today = len(self.history)
        self.android_picker_request_code = 7337
        self.android_voice_request_code = 7447
        self.android_picker_bound = False

        # Root
        self.root_layout = AppBackground()

        # Content area (above navbar)
        self.screen_area = FloatLayout(size_hint=(1, 1))
        self.root_layout.add_widget(self.screen_area)

        # Build screens
        self.generator_screen = GeneratorScreen(self)
        self.history_screen = HistoryScreen(self)

        self.screen_area.add_widget(self.generator_screen)

        # Navbar
        self.navbar = NavBar(
            on_generator=self.show_generator,
            on_history=self.show_history,
            on_mic=self.on_mic_tap,
        )
        self.root_layout.add_widget(self.navbar)

        # Reserve space for navbar
        self._adjust_screen_area()
        Window.bind(on_resize=lambda *a: self._adjust_screen_area())
        self.root_layout.bind(size=lambda *a: self._adjust_screen_area())
        Clock.schedule_once(lambda dt: self._adjust_screen_area(), 0)

        return self.root_layout

    def _adjust_screen_area(self):
        nb_h = dp(72)
        rw = self.root_layout.width or Window.width
        rh = self.root_layout.height or Window.height
        self.screen_area.size_hint = (None, None)
        self.screen_area.pos = (0, nb_h)
        self.screen_area.size = (rw, max(dp(360), rh - nb_h))
        self.navbar.size_hint = (None, None)
        self.navbar.pos = (0, 0)
        self.navbar.size = (rw, nb_h)

    def show_generator(self, *a):
        self.screen_area.clear_widgets()
        self.screen_area.add_widget(self.generator_screen)
        self.navbar.set_active("gen")

    def show_history(self, *a):
        self.screen_area.clear_widgets()
        self.screen_area.add_widget(self.history_screen)
        self.history_screen.refresh(self.history)
        self.navbar.set_active("hist")

    def on_mic_tap(self, *a):
        self.show_generator()
        if kivy_platform == "android":
            try:
                self.open_android_voice_input()
                return
            except Exception as e:
                self.set_status("Голосовой ввод", f"Не открылся: {e}", AMBER)
                return
        self.set_status("Голосовой ввод", "На ПК используй поле текста или выбери аудиофайл.", CYAN)

    def open_android_voice_input(self):
        from jnius import autoclass
        from android import activity

        Intent = autoclass("android.content.Intent")
        RecognizerIntent = autoclass("android.speech.RecognizerIntent")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")

        if not self.android_picker_bound:
            activity.bind(on_activity_result=self.on_android_activity_result)
            self.android_picker_bound = True

        intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ru-RU")
        intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "Скажи тему или текст для конспекта")
        PythonActivity.mActivity.startActivityForResult(intent, self.android_voice_request_code)
        self.set_status("Голосовой ввод", "Слушаю через системное распознавание Android...", CYAN)

    # ── Detail mode ──────────────────────────────────────────────────────────────

    def set_detail_mode(self, mode):
        self.detail_mode = mode
        for key, btn in self.detail_buttons.items():
            btn.set_active(key == mode)
        self.update_ready_status()

    def update_ready_status(self):
        short = self.get_model_short(self.selected_model)
        detail = DETAIL_OPTIONS[self.detail_mode]["label"]
        if hasattr(self, "status_chip"):
            self.status_chip.update("Готов", f"Модель: {short}  ·  {detail}", GREEN)
        if hasattr(self, "model_btn"):
            self.model_btn.text = short

    def get_model_item(self, code):
        for item in MODEL_OPTIONS:
            if item["code"] == code:
                return item
        return MODEL_OPTIONS[0]

    def get_model_short(self, code):
        return self.get_model_item(code)["short"]

    # ── Model modal ──────────────────────────────────────────────────────────────

    def open_model_modal(self, *a):
        modal = ModalView(size_hint=(0.92, 0.78), background_color=(0, 0, 0, 0.65), auto_dismiss=True)

        outer = BoxLayout(
            orientation="vertical",
            padding=[dp(20), dp(20), dp(20), dp(20)],
            spacing=dp(12),
        )
        with outer.canvas.before:
            Color(*c(BG2))
            bg = RoundedRectangle(pos=outer.pos, size=outer.size, radius=[dp(16)])
            Color(*ca(BORDER, 0.50))
            border = Line(rounded_rectangle=(outer.x, outer.y, outer.width, outer.height, dp(16)), width=1)

        def upd_outer(*_):
            bg.pos = outer.pos
            bg.size = outer.size
            bg.radius = [dp(16)]
            border.rounded_rectangle = (outer.x, outer.y, outer.width, outer.height, dp(16))

        outer.bind(pos=upd_outer, size=upd_outer)

        outer.add_widget(lbl("Выбор модели", 18, TEXT, True, fixed_h=28))
        outer.add_widget(lbl("Переключайся, если одна перегружена.", 12, TEXT3, fixed_h=18))

        sc = ScrollView(
            size_hint=(1, 1),
            bar_width=dp(2),
            scroll_type=["bars", "content"],
            bar_color=ca(BORDER2, 0.6),
            bar_inactive_color=ca(BORDER, 0.2),
        )
        box = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        box.bind(minimum_height=box.setter("height"))

        for item in MODEL_OPTIONS:
            active = item["code"] == self.selected_model
            bg_col = CYAN if active else CARD
            fg_col = BG if active else TEXT

            title = item["label"]
            hint = item["hint"]
            state = "Выбрано" if active else "Выбрать"

            card = Button(
                text=f"{title}\n{hint}\n{state}",
                size_hint_y=None,
                height=dp(88),
                background_normal="",
                background_down="",
                background_color=(0, 0, 0, 0),
                color=c(fg_col),
                bold=active,
                font_size=sp(12.5),
                halign="left",
                valign="middle",
                padding=[dp(14), dp(8)],
            )
            card.bind(size=lambda inst, v: setattr(inst, "text_size", (max(10, v[0] - dp(28)), None)))

            with card.canvas.before:
                Color(*c(bg_col))
                rr = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(10)])
                Color(*ca(BORDER, 0.50 if not active else 0.0))
                ln = Line(rounded_rectangle=(card.x, card.y, card.width, card.height, dp(10)), width=1)

            def upd_card(inst, *_args, r=rr, l=ln, is_active=active):
                r.pos = inst.pos
                r.size = inst.size
                r.radius = [dp(10)]
                l.rounded_rectangle = (inst.x, inst.y, inst.width, inst.height, dp(10))

            card.bind(pos=upd_card, size=upd_card)
            card.bind(on_release=lambda inst, code=item["code"], m=modal: self.select_model(code, m))
            box.add_widget(card)

        sc.add_widget(box)
        outer.add_widget(sc)

        close_btn = GhostBtn("Закрыть", fg=TEXT2)
        close_btn.height = dp(44)
        close_btn.bind(on_release=lambda inst: modal.dismiss())
        outer.add_widget(close_btn)

        modal.add_widget(outer)
        modal.open()
    def select_model(self, code, modal=None):
        self.selected_model = code
        if modal:
            modal.dismiss()
        self.update_ready_status()

    # ── Generate ─────────────────────────────────────────────────────────────────

    def on_generate(self, *a):
        if self.request_running:
            self.set_status("Идёт запрос", "Дождись результата.", AMBER)
            return

        topic = self.topic_input.text.strip()
        file_text = self.loaded_file_text.strip()
        if not topic and not file_text:
            self.set_status("Нужна тема", "Введи тему или добавь файл.", RED)
            return

        item = self.get_model_item(self.selected_model)
        if item["provider"] == "gemini" and not GEMINI_API_KEY:
            self.set_status("Нет ключа", "GEMINI_API_KEY не найден.", RED)
            return
        if item["provider"] == "groq" and not GROQ_API_KEY:
            self.set_status("Нет ключа", "GROQ_API_KEY не найден.", RED)
            return

        material = self.compose_material(topic, file_text)
        mode_label = DETAIL_OPTIONS[self.detail_mode]["label"]
        max_tokens = DETAIL_OPTIONS[self.detail_mode]["tokens"]
        model = self.selected_model

        self.request_running = True
        self.generate_btn.disabled = True
        self.generate_btn.text = "Генерирую..."
        self.generate_btn.set_fill(CYAN_DIM)
        self.output_label.text = ""
        self.output_label.color = c(TEXT3)
        self.output_title.text = "Генерация"
        self.output_meta.text = f"{self.get_model_short(model)}  ·  {mode_label}"
        self.set_status("Отправляю запрос", "Создаю структуру конспекта...", TEXT2)

        threading.Thread(target=self._worker_generate, args=(material, model, max_tokens, mode_label), daemon=True).start()

    def _worker_generate(self, topic, model, max_tokens, mode_label):
        prompt = self.build_user_prompt(topic, mode_label)
        fallback_used = False
        model_used = model

        try:
            result = self.call_model_with_retry(model, prompt, max_tokens)
        except TemporaryAPIError:
            if model == PRIMARY_MODEL:
                fallback_used = True
                model_used = FALLBACK_MODEL
                self.ui(lambda: self.set_status("Сервер занят", f"Переключаюсь на {self.get_model_short(FALLBACK_MODEL)}...", AMBER))
                try:
                    result = self.call_model_with_retry(FALLBACK_MODEL, prompt, max_tokens)
                except Exception as e:
                    self.ui(lambda err=e: self.finish_error(f"Ошибка API: {err}"))
                    return
            else:
                self.ui(lambda: self.finish_error("Сервер перегружен. Попробуй другую модель."))
                return
        except Exception as e:
            self.ui(lambda err=e: self.finish_error(f"Ошибка API: {err}"))
            return

        text = result.get("text", "").strip()
        usage = result.get("usage", {})
        if not text:
            self.ui(lambda: self.finish_error("API вернул пустой ответ."))
            return
        self.ui(lambda: self.finish_success(text, model_used, fallback_used, usage))

    def build_user_prompt(self, topic, mode_label):
        if mode_label == "Кратко":
            instruction = (
                "Кратко: 120-180 слов. Обязательно короче стандартного режима. "
                "Формат: название, суть 1-2 предложения, 4-5 пунктов, 2-3 вывода. "
                "Не добавляй длинные объяснения."
            )
        elif mode_label == "Подробно":
            instruction = (
                "Подробно: 900-1400 слов. Обязательно намного больше стандартного режима. "
                "Формат: введение, 6-9 разделов с подзаголовками, определения, примеры, связи между понятиями, выводы."
            )
        else:
            instruction = (
                "Стандарт: 400-650 слов. Больше краткого, но меньше подробного. "
                "Формат: название, краткая суть, 4-7 пунктов, ключевые понятия, 3-5 выводов."
            )
        return f"Режим: {mode_label}.\nСтрого соблюдай объём: {instruction}\n\nМатериал:\n{topic}"

    def compose_material(self, topic, file_text):
        parts = []
        cleaned = self.strip_auto_preview(topic)
        if cleaned:
            parts.append("Запрос:\n" + cleaned)
        if file_text:
            limited = file_text[:24000]
            if len(file_text) > len(limited):
                limited += "\n\n[Файл длинный, использована первая часть текста.]"
            parts.append(f"Файл ({self.loaded_file_name}):\n" + limited)
        return "\n\n".join(parts)

    def strip_auto_preview(self, topic):
        text = (topic or "").strip()
        for marker in ["[Файл добавлен:", "[Аудио распознано:"]:
            if text.startswith(marker):
                return ""
            if "\n\n" + marker in text:
                return text.split("\n\n" + marker, 1)[0].strip()
        return text

    def call_model_with_retry(self, model, prompt, max_tokens):
        last_error = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                self.ui(lambda a=attempt, m=model: self.set_status(
                    "Генерирую", f"{self.get_model_short(m)}, попытка {a}/{MAX_ATTEMPTS}", TEXT2))
                return self.call_model_once(model, prompt, max_tokens)
            except TemporaryAPIError as e:
                last_error = e
                if attempt < MAX_ATTEMPTS:
                    wait = (2 ** (attempt - 1)) + random.uniform(0.0, 0.4)
                    time.sleep(wait)
            except Exception:
                raise
        raise last_error or TemporaryAPIError("Временная ошибка API")

    def call_model_once(self, model, prompt, max_tokens):
        item = self.get_model_item(model)
        if item["provider"] == "groq":
            return self.call_groq_once(model, prompt, max_tokens)
        return self.call_gemini_once(model, prompt, max_tokens)

    def open_request(self, req, timeout=None):
        t = timeout or TIMEOUT_SEC
        try:
            if SSL_CONTEXT:
                return urllib.request.urlopen(req, timeout=t, context=SSL_CONTEXT)
            return urllib.request.urlopen(req, timeout=t)
        except urllib.error.URLError:
            raise

    def call_gemini_once(self, model, prompt, max_tokens):
        item = self.get_model_item(model)
        api_v = item.get("api_version", "v1beta")
        url = f"https://generativelanguage.googleapis.com/{api_v}/models/{model}:generateContent"
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.45, "topP": 0.9, "maxOutputTokens": max_tokens, "responseMimeType": "text/plain"},
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json; charset=utf-8",
            "x-goog-api-key": GEMINI_API_KEY,
            "User-Agent": "Mozilla/5.0 AutoconspectApp/2.0",
        }, method="POST")
        try:
            with self.open_request(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            msg = self.parse_api_error(raw)
            if e.code in (429, 500, 502, 503, 504):
                raise TemporaryAPIError(msg)
            raise APIError(f"{e.code}: {msg}")
        except urllib.error.URLError as e:
            raise TemporaryAPIError(str(e))
        return self.parse_gemini_success(data)

    def call_groq_once(self, model, prompt, max_tokens):
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            "temperature": 0.45,
            "max_completion_tokens": max_tokens,
            "stream": False,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(GROQ_API_URL, data=body, headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "User-Agent": "Mozilla/5.0 AutoconspectApp/2.0",
        }, method="POST")
        try:
            with self.open_request(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            msg = self.parse_api_error(raw)
            if e.code in (429, 500, 502, 503, 504):
                raise TemporaryAPIError(msg)
            raise APIError(f"{e.code}: {msg}")
        except urllib.error.URLError as e:
            raise TemporaryAPIError(str(e))
        return self.parse_groq_success(data)

    def parse_gemini_success(self, data):
        candidates = data.get("candidates") or []
        if not candidates:
            raise APIError(f"Нет candidates: {data}")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            raise APIError(f"Нет текста: {data}")
        return {"text": text, "usage": data.get("usageMetadata", {})}

    def parse_groq_success(self, data):
        choices = data.get("choices") or []
        if not choices:
            raise APIError(f"Нет choices: {data}")
        text = (choices[0].get("message") or {}).get("content", "").strip()
        if not text:
            raise APIError(f"Нет текста Groq: {data}")
        return {"text": text, "usage": data.get("usage", {})}

    def parse_api_error(self, raw):
        try:
            data = json.loads(raw)
            err = data.get("error")
            if isinstance(err, dict):
                return err.get("message", raw)
            return str(err or raw)
        except Exception:
            return raw[:500]

    def finish_success(self, text, model_used, fallback_used, usage):
        self.last_result = text
        self.last_model_used = model_used
        self.output_label.text = text
        self.output_label.color = c(TEXT)
        self.output_title.text = "Конспект готов"
        tokens = usage.get("totalTokenCount") or usage.get("total_tokens") or ""
        token_part = f"  ·  {tokens} токенов" if tokens else ""
        fb = "  ·  fallback" if fallback_used else ""
        self.output_meta.text = f"{self.get_model_short(model_used)}{fb}{token_part}"
        self.set_status("Конспект готов ✓", self.get_model_short(model_used), GREEN)
        self.add_history_item(text, model_used)

        self.files_today += 1
        self.stat_label.text = f"Сегодня обработано: {self.files_today} файлов"

        self.request_running = False
        self.generate_btn.disabled = False
        self.generate_btn.text = "Создать конспект"
        self.generate_btn.set_fill(CYAN)

    def finish_error(self, msg):
        self.output_title.text = "Ошибка"
        self.output_meta.text = "Запрос не выполнен"
        self.output_label.text = msg
        self.output_label.color = c(RED)
        self.set_status("Ошибка", "Проверь ключ или сеть.", RED)
        self.request_running = False
        self.generate_btn.disabled = False
        self.generate_btn.text = "Создать конспект"
        self.generate_btn.set_fill(CYAN)

    def set_status(self, title, text, color_hex=GREEN):
        if hasattr(self, "status_chip"):
            self.status_chip.update(title, text, color_hex)

    def ui(self, func):
        Clock.schedule_once(lambda dt: func(), 0)

    def copy_result(self, *a):
        if not self.last_result:
            self.set_status("Нечего копировать", "Сначала создай конспект.", AMBER)
            return
        Clipboard.copy(self.last_result)
        self.set_status("Скопировано ✓", "Конспект в буфере обмена.", GREEN)

    def on_clear(self, *a):
        self.topic_input.text = ""
        self.last_result = ""
        self.output_title.text = "Конспект"
        self.output_meta.text = "Здесь появится готовый конспект"
        self.output_label.text = "Пока пусто. Введи тему и нажми «Создать конспект»."
        self.output_label.color = c(TEXT3)
        self.update_ready_status()

    # ── File picking ──────────────────────────────────────────────────────────────

    def pick_file(self, *a):
        if kivy_platform == "android":
            try:
                self.open_android_file_picker()
                return
            except Exception as e:
                # Запасной вариант для редких сборок, где нативный Intent не стартует.
                if filechooser is not None:
                    try:
                        self.open_plyer_file_picker()
                        return
                    except Exception as e2:
                        self.finish_file_error(f"Android picker не открылся: {e}; запасной picker тоже упал: {e2}")
                        return
                self.finish_file_error(f"Android picker не открылся: {e}")
                return

        try:
            self.open_desktop_file_picker()
        except Exception as e:
            self.finish_file_error(f"Не удалось открыть файл: {e}")

    def open_desktop_file_picker(self):
        if kivy_platform not in ("macosx", "ios") and filechooser is not None:
            try:
                self.open_plyer_file_picker()
                return
            except Exception:
                pass
        self.open_kivy_file_picker()

    def open_kivy_file_picker(self):
        modal = ModalView(size_hint=(0.94, 0.82), background_color=(0, 0, 0, 0.65), auto_dismiss=False)

        outer = BoxLayout(orientation="vertical", padding=[dp(14), dp(14), dp(14), dp(14)], spacing=dp(10))
        with outer.canvas.before:
            Color(*c(BG2))
            bg = RoundedRectangle(pos=outer.pos, size=outer.size, radius=[dp(14)])
            Color(*ca(BORDER, 0.50))
            border = Line(rounded_rectangle=(outer.x, outer.y, outer.width, outer.height, dp(14)), width=1)

        def upd_outer(*_):
            bg.pos = outer.pos
            bg.size = outer.size
            bg.radius = [dp(14)]
            border.rounded_rectangle = (outer.x, outer.y, outer.width, outer.height, dp(14))

        outer.bind(pos=upd_outer, size=upd_outer)

        outer.add_widget(lbl("Выберите файл или аудио", 16, TEXT, True, fixed_h=24))

        chooser = FileChooserListView(
            path=os.path.expanduser("~"),
            filters=[
                "*.txt", "*.docx", "*.pdf", "*.md", "*.csv",
                "*.mp3", "*.m4a", "*.wav", "*.ogg", "*.webm",
                "*.mp4", "*.mpeg", "*.mpga", "*.flac",
            ],
        )
        outer.add_widget(chooser)

        def apply_selection(selection):
            if not selection:
                self.set_status("Отменено", "Файл не выбран.", AMBER)
                return
            modal.dismiss()
            self.on_file_selected(selection)

        chooser.bind(on_submit=lambda inst, selection, *a: apply_selection(selection))

        btn_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(8))
        open_btn = AccentBtn("Открыть")
        open_btn.bind(on_release=lambda *a: apply_selection(chooser.selection))
        cancel_btn = GhostBtn("Отмена", fg=TEXT2)
        cancel_btn.bind(on_release=lambda *a: modal.dismiss())
        btn_row.add_widget(open_btn)
        btn_row.add_widget(cancel_btn)
        outer.add_widget(btn_row)

        modal.add_widget(outer)
        modal.open()

    def open_plyer_file_picker(self):
        if filechooser is None:
            raise APIError("Файловый выборщик недоступен.")
        filechooser.open_file(
            on_selection=self.on_file_selected,
            filters=[
                "*.txt", "*.docx", "*.pdf", "*.md", "*.csv",
                "*.mp3", "*.m4a", "*.wav", "*.ogg", "*.webm",
                "*.mp4", "*.mpeg", "*.mpga", "*.flac"
            ],
            multiple=False,
        )

    def open_android_file_picker(self):
        from jnius import autoclass
        from android import activity

        Intent = autoclass("android.content.Intent")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")

        if not self.android_picker_bound:
            activity.bind(on_activity_result=self.on_android_activity_result)
            self.android_picker_bound = True

        intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
        intent.addCategory(Intent.CATEGORY_OPENABLE)
        intent.setType("*/*")
        try:
            intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, False)
        except Exception:
            pass
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        intent.addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        intent.addFlags(Intent.FLAG_GRANT_PREFIX_URI_PERMISSION)

        target_intent = self.safe_create_chooser(intent, "Выберите файл или аудио")
        PythonActivity.mActivity.startActivityForResult(target_intent, self.android_picker_request_code)

        if hasattr(self, "file_label"):
            self.file_label.text = "Открыт системный проводник. Выбери TXT/DOCX/PDF или аудио."
        self.set_status("Выбор файла", "Ожидаю файл из системного проводника...", TEXT2)

    def safe_create_chooser(self, intent, title):
        """
        Безопасная обёртка над Intent.createChooser.
        На pyjnius обычная Python-строка иногда не матчится с CharSequence и даёт:
        No static methods called createChooser matching your arguments.
        Поэтому сначала явно создаём java.lang.String, а если и это не сработает,
        возвращаем исходный ACTION_OPEN_DOCUMENT intent без chooser.
        """
        try:
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            JavaString = autoclass("java.lang.String")
            return Intent.createChooser(intent, JavaString(title))
        except Exception:
            return intent

    def on_android_activity_result(self, request_code, result_code, intent):
        try:
            from jnius import autoclass

            Activity = autoclass("android.app.Activity")
            Intent = autoclass("android.content.Intent")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")

            if request_code == self.android_voice_request_code:
                if result_code != Activity.RESULT_OK or intent is None:
                    self.ui(lambda: self.set_status("Отменено", "Голосовой ввод отменён.", AMBER))
                    return
                try:
                    RecognizerIntent = autoclass("android.speech.RecognizerIntent")
                    results = intent.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                    spoken = ""
                    if results is not None and results.size() > 0:
                        spoken = str(results.get(0)).strip()
                    if spoken:
                        def apply_voice():
                            current = self.topic_input.text.strip()
                            self.topic_input.text = (current + "\n" + spoken).strip() if current else spoken
                            self.set_status("Голос добавлен", "Текст вставлен в поле ввода.", GREEN)
                        self.ui(apply_voice)
                    else:
                        self.ui(lambda: self.set_status("Пусто", "Android не вернул текст.", AMBER))
                except Exception as e:
                    self.ui(lambda err=e: self.set_status("Ошибка голоса", str(err), RED))
                return

            if request_code != self.android_picker_request_code:
                return

            if result_code != Activity.RESULT_OK or intent is None:
                self.ui(lambda: self.set_status("Отменено", "Файл не выбран.", AMBER))
                return

            uri = intent.getData()

            # Некоторые файловые менеджеры возвращают файл через ClipData, а не getData().
            if uri is None:
                try:
                    clip = intent.getClipData()
                    if clip is not None and clip.getItemCount() > 0:
                        uri = clip.getItemAt(0).getUri()
                except Exception:
                    uri = None

            if uri is None:
                self.ui(lambda: self.finish_file_error(
                    "Android не вернул URI файла. Выбери файл через системное приложение «Файлы»."
                ))
                return

            try:
                flags = intent.getFlags()
                read_flags = Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
                PythonActivity.mActivity.getContentResolver().takePersistableUriPermission(uri, flags & read_flags)
            except Exception:
                pass

            uri_text = uri.toString()
            self.ui(lambda u=uri_text: self.on_file_selected([u]))
        except Exception as e:
            self.ui(lambda err=e: self.finish_file_error(f"Ошибка Android picker: {err}"))

    def on_file_selected(self, selection):
        raw_path = self.normalize_file_selection(selection)
        if not raw_path:
            self.finish_file_error(
                "Файл не выбран: Android/Plyer вернул пустой путь. "
                "Нажми «Выбрать файл» и выбери документ через системное приложение «Файлы»."
            )
            return

        try:
            local_path, name, mime_type = self.materialize_selection(raw_path)
        except Exception as e:
            self.finish_file_error(f"Не удалось получить файл от Android: {e}")
            return

        self.loaded_file_name = name or "файл"
        if hasattr(self, "file_label"):
            self.file_label.text = f"Выбран: {self.loaded_file_name}"

        if self.is_audio_selection(local_path, name, mime_type):
            self.start_audio_transcription(local_path, name, mime_type)
            return

        self.set_status("Читаю файл", self.loaded_file_name, TEXT2)
        threading.Thread(target=self._worker_read_document, args=(local_path, name, mime_type), daemon=True).start()

    def materialize_selection(self, path):
        """
        Превращает Android content:// URI в обычный локальный временный файл.
        Исправление главное: больше не используем проблемный helper массивов из pyjnius,
        из-за которого у тебя падало чтение файла. Теперь копируем поток через Java NIO.
        """
        path_str = str(path)
        if path_str.startswith("content://"):
            name, mime_type, size = self.get_android_uri_meta(path_str)
            name = self.ensure_filename_with_extension(name, mime_type)
            temp_dir = os.path.join(self.user_data_dir, "selected_files")
            os.makedirs(temp_dir, exist_ok=True)
            safe_name = f"{uuid.uuid4().hex}_{self.safe_ascii_filename(name)}"
            local_path = os.path.join(temp_dir, safe_name)
            self.copy_android_content_uri_to_file(path_str, local_path)
            if not os.path.exists(local_path) or os.path.getsize(local_path) == 0:
                raise APIError("Android вернул пустой файл или не дал прочитать содержимое.")
            return local_path, name, mime_type or mimetypes.guess_type(name)[0] or ""

        name = os.path.basename(path_str) or "file"
        mime_type = mimetypes.guess_type(name)[0] or ""
        return path_str, name, mime_type

    def ensure_filename_with_extension(self, name, mime_type):
        name = os.path.basename(str(name or "file")) or "file"
        root, ext = os.path.splitext(name)
        if ext:
            return name

        mime_to_ext = {
            "text/plain": ".txt",
            "text/markdown": ".md",
            "text/csv": ".csv",
            "application/csv": ".csv",
            "application/pdf": ".pdf",
            "application/msword": ".doc",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "audio/mpeg": ".mp3",
            "audio/mp3": ".mp3",
            "audio/mp4": ".m4a",
            "audio/x-m4a": ".m4a",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/ogg": ".ogg",
            "audio/webm": ".webm",
            "audio/flac": ".flac",
            "video/mp4": ".mp4",
            "video/webm": ".webm",
        }
        ext = mime_to_ext.get((mime_type or "").lower())
        if not ext:
            guessed = mimetypes.guess_extension((mime_type or "").lower())
            ext = guessed if guessed else ""
        return name + ext

    def normalize_file_selection(self, selection):
        if selection is None:
            return None
        if isinstance(selection, str):
            v = selection.strip()
            return v if v and v.lower() != "none" else None
        if isinstance(selection, (list, tuple)):
            for item in selection:
                if item is None:
                    continue
                v = str(item).strip()
                if v and v.lower() != "none":
                    return v
            return None
        v = str(selection).strip()
        return v if v and v.lower() != "none" else None

    def finish_file_error(self, msg):
        self.output_title.text = "Ошибка файла"
        self.output_meta.text = "Файл не добавлен"
        self.output_label.text = str(msg)
        self.output_label.color = c(RED)
        if hasattr(self, "file_label"):
            self.file_label.text = "Файл не добавлен. Выбери файл через системный проводник «Файлы»."
        # В статусе коротко, иначе длинная ошибка налезает на дизайн.
        self.set_status("Ошибка файла", "Подробности ниже.", RED)

    def _worker_read_document(self, path, name, mime_type):
        try:
            text = self.read_text_from_path(path, name, mime_type)
            text = text.strip()
            if not text:
                raise APIError("Файл прочитан, но текст не найден.")
            self.ui(lambda n=name, t=text: self.finish_loaded_text(n, t, "Файл добавлен"))
        except Exception as e:
            self.ui(lambda err=e: self.finish_file_error(str(err)))

    def finish_loaded_text(self, name, text, source_label="Файл добавлен"):
        self.loaded_file_text = text
        self.loaded_file_name = name or "файл"
        self.file_label.text = f"{source_label}: {self.loaded_file_name}  ·  {len(text)} символов"
        self.insert_loaded_preview(source_label, self.loaded_file_name, text)
        self.set_status(source_label, "Текст вставлен в поле. Можно создавать конспект.", GREEN)

    def insert_loaded_preview(self, source_label, name, text):
        preview = (text or "").strip()[:3200]
        if len(text or "") > 3200:
            preview += "\n\n[Показана часть текста. Для конспекта используется больше.]"
        block = f"[{source_label}: {name}]\n{preview}"
        current = self.strip_auto_preview(self.topic_input.text)
        self.topic_input.text = (current + "\n\n" + block) if current else block

    def clear_loaded_file(self, *a):
        self.loaded_file_text = ""
        self.loaded_file_name = ""
        self.file_label.text = "Файл не добавлен. Поддержка: TXT, DOCX, PDF, MP3/M4A/WAV"
        self.topic_input.text = self.strip_auto_preview(self.topic_input.text)
        self.set_status("Файл убран", "Поле очищено.", TEXT2)

    def read_text_from_path(self, path, name=None, mime_type=""):
        lower = (name or path or "").lower()

        if lower.endswith(".docx") or "wordprocessingml" in (mime_type or ""):
            return self.read_docx(path)

        if lower.endswith(".pdf") or mime_type == "application/pdf":
            return self.read_pdf(path)

        if lower.endswith((".txt", ".md", ".csv")) or (mime_type or "").startswith("text/"):
            with open(path, "rb") as f:
                return self.decode_plain_text(f.read())

        raise APIError(
            "Поддерживаются TXT, MD, CSV, DOCX, текстовый PDF и аудио "
            "MP3/M4A/WAV/OGG/WEBM/MP4/FLAC. Старый DOC сохрани как DOCX."
        )

    # Старое имя оставлено для совместимости с уже написанной логикой.
    def read_text_from_file(self, path):
        name = os.path.basename(str(path)) or "file"
        mime_type = mimetypes.guess_type(name)[0] or ""
        return self.read_text_from_path(path, name, mime_type)

    def read_docx(self, path):
        try:
            import docx2txt
            extracted = docx2txt.process(path) or ""
            if extracted.strip():
                return extracted
        except Exception:
            pass

        with open(path, "rb") as f:
            data = f.read()
        return self.read_docx_bytes(data)

    def read_docx_bytes(self, data):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml_data = z.read("word/document.xml")
        root = ET.fromstring(xml_data)
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs = []
        for p in root.iter(ns + "p"):
            line = "".join(node.text for node in p.iter(ns + "t") if node.text).strip()
            if line:
                paragraphs.append(line)
        return "\n".join(paragraphs)

    def read_pdf(self, path):
        try:
            from pypdf import PdfReader
        except Exception:
            raise APIError("Для PDF нужен pypdf в buildozer.spec.")

        try:
            reader = PdfReader(path)
        except Exception as e:
            raise APIError(f"PDF не открылся: {e}")

        pages_text = []
        for i in range(min(len(reader.pages), 80)):
            try:
                t = (reader.pages[i].extract_text() or "").strip()
                if t:
                    pages_text.append(f"[Стр. {i + 1}]\n{t}")
            except Exception:
                continue

        if not pages_text:
            raise APIError("PDF прочитан, но текст не найден. Если это скан, нужен OCR.")

        return "\n\n".join(pages_text)

    def read_pdf_bytes(self, data):
        temp_dir = os.path.join(self.user_data_dir, "selected_files")
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, "temp_pdf.pdf")
        with open(temp_path, "wb") as f:
            f.write(data)
        return self.read_pdf(temp_path)

    def read_selected_file_bytes(self, path):
        path_str = str(path)
        if path_str.startswith("content://"):
            data, name, mime, _size = self.read_android_content_uri(path_str)
            return data, name, mime
        name = os.path.basename(path_str) or "file"
        mime = mimetypes.guess_type(name)[0] or ""
        with open(path_str, "rb") as f:
            return f.read(), name, mime

    def get_selected_file_meta(self, path):
        path_str = str(path)
        if path_str.startswith("content://"):
            name, mime, _size = self.get_android_uri_meta(path_str)
            return name or "file", mime or ""
        name = os.path.basename(path_str) or "file"
        return name, mimetypes.guess_type(name)[0] or ""

    def get_android_uri_meta(self, uri_text):
        if kivy_platform != "android":
            return os.path.basename(str(uri_text)) or "file", "", None

        try:
            from jnius import autoclass
            Uri = autoclass("android.net.Uri")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            OpenableColumns = autoclass("android.provider.OpenableColumns")

            resolver = PythonActivity.mActivity.getContentResolver()
            uri = Uri.parse(uri_text)
            mime = resolver.getType(uri) or ""
            name = ""
            size = None

            cursor = resolver.query(uri, None, None, None, None)
            if cursor:
                try:
                    if cursor.moveToFirst():
                        ni = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                        si = cursor.getColumnIndex(OpenableColumns.SIZE)
                        if ni >= 0:
                            name = cursor.getString(ni) or ""
                        if si >= 0:
                            size = cursor.getLong(si)
                finally:
                    cursor.close()

            if not name:
                name = uri.getLastPathSegment() or "file"

            return name or "file", mime, size
        except Exception:
            return os.path.basename(str(uri_text)) or "file", "", None

    def copy_android_content_uri_to_file(self, uri_text, local_path):
        """
        Копирует content:// URI во временный файл без проблемного helper массива pyjnius.
        Используем Java NIO:
        ContentResolver.openInputStream(uri) -> Channels.newChannel -> FileOutputStream.
        """
        if kivy_platform != "android":
            raise APIError("content:// доступен только на Android.")

        try:
            from jnius import autoclass
            Uri = autoclass("android.net.Uri")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Channels = autoclass("java.nio.channels.Channels")
            FileOutputStream = autoclass("java.io.FileOutputStream")

            resolver = PythonActivity.mActivity.getContentResolver()
            uri = Uri.parse(uri_text)
            stream = resolver.openInputStream(uri)
            if stream is None:
                raise APIError("Android не дал доступ к файлу.")

            source = None
            out_stream = None
            dest = None
            try:
                source = Channels.newChannel(stream)
                out_stream = FileOutputStream(local_path)
                dest = out_stream.getChannel()
                position = 0
                chunk_size = 8 * 1024 * 1024
                while True:
                    copied = dest.transferFrom(source, position, chunk_size)
                    if copied is None or copied <= 0:
                        break
                    position += int(copied)
            finally:
                try:
                    if dest is not None:
                        dest.close()
                except Exception:
                    pass
                try:
                    if out_stream is not None:
                        out_stream.close()
                except Exception:
                    pass
                try:
                    if source is not None:
                        source.close()
                except Exception:
                    pass
                try:
                    stream.close()
                except Exception:
                    pass
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Android не смог скопировать файл: {e}")

    def read_android_content_uri(self, uri_text):
        """
        Совместимость для старых участков кода: возвращает байты выбранного content://.
        Внутри сначала копируем URI в temp-файл, потом читаем его Python open().
        """
        if kivy_platform != "android":
            raise APIError("content:// доступен только на Android.")

        try:
            name, mime, size = self.get_android_uri_meta(uri_text)
            name = self.ensure_filename_with_extension(name, mime)
            temp_dir = os.path.join(self.user_data_dir, "selected_files")
            os.makedirs(temp_dir, exist_ok=True)
            local_path = os.path.join(temp_dir, f"read_{uuid.uuid4().hex}_{self.safe_ascii_filename(name)}")
            self.copy_android_content_uri_to_file(uri_text, local_path)
            with open(local_path, "rb") as f:
                data = f.read()
            return data, name or "file", mime or "", size
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Android не смог прочитать файл: {e}")

    def decode_plain_text(self, data):
        for enc in ["utf-8", "utf-8-sig", "cp1251", "windows-1251", "iso-8859-1"]:
            try:
                return data.decode(enc)
            except Exception:
                pass
        raise APIError("Не удалось определить кодировку файла.")

    def is_audio_selection(self, path, name, mime_type):
        lower = ((name or "") + " " + str(path)).lower()
        exts = (".mp3", ".m4a", ".wav", ".ogg", ".webm", ".mp4", ".mpeg", ".mpga", ".flac")
        return lower.endswith(exts) or (mime_type or "").startswith("audio/") or (mime_type or "") in ("video/mp4", "video/webm")

    def start_audio_transcription(self, path, name, mime_type):
        if not GROQ_API_KEY:
            self.finish_file_error("Для распознавания аудио нужен GROQ_API_KEY в GitHub Secrets.")
            return
        self.loaded_file_name = name or "аудио"
        self.file_label.text = f"Аудио: {self.loaded_file_name}. Расшифровываю..."
        self.set_status("Распознаю аудио", self.loaded_file_name, AMBER)
        threading.Thread(target=self._worker_transcribe_audio, args=(path, name, mime_type), daemon=True).start()

    def _worker_transcribe_audio(self, path, name, mime_type):
        try:
            file_name = self.ensure_supported_audio_filename(name or os.path.basename(path) or "audio.m4a", mime_type)
            file_mime = mime_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream"

            if os.path.getsize(path) > MAX_AUDIO_BYTES:
                raise APIError("Аудио больше 25 МБ. Groq не принимает такой файл одним куском.")

            transcript = self.transcribe_audio(path, file_name, file_mime).strip()
            if not transcript:
                raise APIError("Groq вернул пустую расшифровку.")

            self.ui(lambda n=file_name, t=transcript: self.finish_loaded_text(n, t, "Аудио распознано"))
        except Exception as e:
            self.ui(lambda err=e: self.finish_file_error("Ошибка аудио: " + str(err)))

    def ensure_supported_audio_filename(self, file_name, mime_type):
        name = os.path.basename(str(file_name or "audio.m4a")) or "audio.m4a"
        ext = os.path.splitext(name)[1].lower()
        allowed = {".flac", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".ogg", ".wav", ".webm"}
        if ext in allowed:
            return name

        mime_to_ext = {
            "audio/mpeg": ".mp3",
            "audio/mp3": ".mp3",
            "audio/mp4": ".m4a",
            "audio/x-m4a": ".m4a",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/ogg": ".ogg",
            "audio/webm": ".webm",
            "audio/flac": ".flac",
            "video/mp4": ".mp4",
            "video/webm": ".webm",
        }
        return name + mime_to_ext.get((mime_type or "").lower(), ".m4a")

    def transcribe_audio(self, path, file_name, mime_type):
        if requests is not None:
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "User-Agent": "Mozilla/5.0 AutoconspectApp/2.0",
            }
            data = {
                "model": "whisper-large-v3-turbo",
                "response_format": "json",
                "temperature": "0",
                "prompt": "Учебная лекция. Распознай максимально точно, сохраняя термины.",
            }
            with open(path, "rb") as f:
                files = {"file": (self.safe_ascii_filename(file_name), f, mime_type or "application/octet-stream")}
                verify_path = certifi.where() if certifi else True
                resp = requests.post(GROQ_TRANSCRIPTION_URL, headers=headers, data=data, files=files, timeout=240, verify=verify_path)

            if resp.status_code >= 400:
                raise APIError(f"Groq audio {resp.status_code}: {self.parse_api_error(resp.text)}")

            try:
                return resp.json().get("text", "")
            except Exception:
                return resp.text

        # Fallback без requests.
        with open(path, "rb") as f:
            file_bytes = f.read()
        return self.transcribe_audio_with_groq(file_name, file_bytes, mime_type)

    def transcribe_audio_with_groq(self, file_name, data, mime_type):
        fields = {
            "model": "whisper-large-v3-turbo",
            "response_format": "json",
            "temperature": "0",
            "prompt": "Учебная лекция. Распознай максимально точно, сохраняя термины.",
        }
        body, content_type = self.build_multipart_body(fields, "file", file_name, data, mime_type)
        req = urllib.request.Request(GROQ_TRANSCRIPTION_URL, data=body, headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": content_type,
            "User-Agent": "Mozilla/5.0 AutoconspectApp/2.0",
        }, method="POST")
        try:
            with self.open_request(req, timeout=240) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            raise APIError(f"Groq audio {e.code}: {self.parse_api_error(e.read().decode('utf-8', errors='replace'))}")
        except urllib.error.URLError as e:
            raise TemporaryAPIError(str(e))
        try:
            return json.loads(raw).get("text", "")
        except Exception:
            return raw

    def build_multipart_body(self, fields, file_field, file_name, file_bytes, mime_type):
        boundary = "----AutoConspect" + uuid.uuid4().hex
        chunks = []
        for key, value in fields.items():
            chunks.append(f"--{boundary}\r\n".encode("utf-8"))
            chunks.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
            chunks.append(str(value).encode("utf-8"))
            chunks.append(b"\r\n")
        safe_name = self.safe_ascii_filename(file_name)
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{file_field}"; filename="{safe_name}"\r\n'.encode("utf-8"))
        chunks.append(f"Content-Type: {mime_type or 'application/octet-stream'}\r\n\r\n".encode("utf-8"))
        chunks.append(file_bytes)
        chunks.append(b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
        return b"".join(chunks), f"multipart/form-data; boundary={boundary}"

    def safe_ascii_filename(self, file_name):
        name = os.path.basename(str(file_name or "file")) or "file"
        safe = []
        for ch in name:
            if 32 <= ord(ch) < 127 and ch not in '\\/:*?"<>|':
                safe.append(ch)
            else:
                safe.append("_")
        return "".join(safe) or "file"

    # ── History ───────────────────────────────────────────────────────────────────

    def history_path(self):
        return os.path.join(self.user_data_dir, "conspect_history.json")

    def load_history(self):
        try:
            path = self.history_path()
            if not os.path.exists(path):
                return []
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return []
            clean = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                if not item.get("text"):
                    continue
                item.setdefault("title", "Конспект")
                item.setdefault("model", "Модель")
                item.setdefault("mode", "Стандарт")
                item.setdefault("ts", time.time())
                clean.append(item)
            return clean[:30]
        except Exception:
            return []

    def save_history(self):
        try:
            with open(self.history_path(), "w", encoding="utf-8") as f:
                json.dump(self.history[:30], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add_history_item(self, text, model_code):
        topic = self.strip_auto_preview(self.topic_input.text).strip() or self.loaded_file_name or "Конспект"
        title = topic.replace("\n", " ")[:40] or "Конспект"
        self.history.insert(0, {
            "title": title,
            "model": self.get_model_short(model_code),
            "mode": DETAIL_OPTIONS[self.detail_mode]["label"],
            "text": text,
            "ts": time.time(),
        })
        self.history = self.history[:30]
        self.save_history()
        if hasattr(self, "history_screen"):
            self.history_screen.refresh(self.history)

    def load_history_item_direct(self, item):
        self.last_result = item["text"]
        self.output_label.text = item["text"]
        self.output_label.color = c(TEXT)
        self.output_title.text = "Конспект из истории"
        self.output_meta.text = f"{item['model']}  ·  {item['mode']}"
        self.set_status("Открыто из истории", item["title"], GREEN)
        self.show_generator()


class APIError(Exception):
    pass


class TemporaryAPIError(APIError):
    pass



# ─── Startup crash guard ───────────────────────────────────────────────────────
_original_autoconspect_build = AutoConspectApp.build

def _safe_autoconspect_build(self):
    try:
        return _original_autoconspect_build(self)
    except Exception:
        import traceback
        err = traceback.format_exc()
        try:
            with open(os.path.join(self.user_data_dir, "startup_crash.txt"), "w", encoding="utf-8") as f:
                f.write(err)
        except Exception:
            pass
        root = BoxLayout(orientation="vertical", padding=[dp(14), dp(14), dp(14), dp(14)], spacing=dp(10))
        with root.canvas.before:
            Color(*c(BG))
            bg_rect = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=lambda inst, v: setattr(bg_rect, "pos", v))
        root.bind(size=lambda inst, v: setattr(bg_rect, "size", v))
        root.add_widget(Label(text="Ошибка запуска приложения", font_size=sp(20), bold=True, color=c(RED), size_hint_y=None, height=dp(42)))
        info = Label(text="Скинь этот текст ошибки. Теперь приложение показывает причину, а не просто закрывается.", font_size=sp(13), color=c(TEXT2), size_hint_y=None, height=dp(70), halign="left", valign="top")
        info.bind(width=lambda inst, v: setattr(inst, "text_size", (v, None)))
        root.add_widget(info)
        sc = ScrollView()
        er = Label(text=err, font_size=sp(11), color=c(TEXT), halign="left", valign="top", size_hint_y=None)
        er.bind(width=lambda inst, v: setattr(inst, "text_size", (v, None)))
        er.bind(texture_size=lambda inst, v: setattr(inst, "height", v[1] + dp(20)))
        sc.add_widget(er)
        root.add_widget(sc)
        return root

AutoConspectApp.build = _safe_autoconspect_build


if __name__ == "__main__":
    AutoConspectApp().run()
