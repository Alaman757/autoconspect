import json
import os
import random
import ssl
import threading
import time
import urllib.error
import urllib.request

try:
    import certifi
except Exception:
    certifi = None

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.properties import ListProperty, NumericProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import get_color_from_hex

try:
    import secret_config
    GEMINI_API_KEY = getattr(secret_config, "GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", "")).strip()
    GROQ_API_KEY = getattr(secret_config, "GROQ_API_KEY", os.environ.get("GROQ_API_KEY", "")).strip()
except Exception:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()


GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

MODEL_OPTIONS = [
    {
        "label": "Gemini 2.5 Flash",
        "short": "2.5 Flash",
        "provider": "gemini",
        "code": "gemini-2.5-flash",
        "api_version": "v1beta",
        "hint": "Основная модель для качественных конспектов. Иногда ловит перегрузку.",
    },
    {
        "label": "Gemini 2.5 Flash Lite",
        "short": "2.5 Lite",
        "provider": "gemini",
        "code": "gemini-2.5-flash-lite",
        "api_version": "v1beta",
        "hint": "Более быстрый и лёгкий вариант, хороший запасной режим.",
    },
    {
        "label": "Gemini 1.5 Flash",
        "short": "1.5 Flash",
        "provider": "gemini",
        "code": "gemini-1.5-flash",
        "api_version": "v1",
        "hint": "Старый быстрый режим. Может быть недоступен в некоторых проектах.",
    },
    {
        "label": "Groq Llama 3.1 8B",
        "short": "Groq 8B",
        "provider": "groq",
        "code": "llama-3.1-8b-instant",
        "hint": "Очень быстрый Groq-вариант. Хорош для коротких и средних конспектов.",
    },
    {
        "label": "Groq Llama 3.3 70B",
        "short": "Groq 70B",
        "provider": "groq",
        "code": "llama-3.3-70b-versatile",
        "hint": "Более сильная модель Groq. Лучше качество, но может быть медленнее.",
    },
    {
        "label": "Groq Qwen3 32B",
        "short": "Groq Qwen",
        "provider": "groq",
        "code": "qwen/qwen3-32b",
        "hint": "Альтернативная Groq-модель. Часто хорошо держит структуру ответа.",
    },
]

DETAIL_OPTIONS = {
    "short": {"label": "Кратко", "tokens": 512, "desc": "только база"},
    "normal": {"label": "Стандарт", "tokens": 896, "desc": "баланс"},
    "full": {"label": "Подробно", "tokens": 1400, "desc": "максимум"},
}

PRIMARY_MODEL = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-2.5-flash-lite"
MAX_ATTEMPTS = 3
TIMEOUT_SEC = 45
ALLOW_SSL_FALLBACK = True

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


def color(hex_value):
    return get_color_from_hex(hex_value)


def make_ssl_context():
    try:
        if certifi:
            return ssl.create_default_context(cafile=certifi.where())
        return ssl.create_default_context()
    except Exception:
        return None


SSL_CONTEXT = make_ssl_context()


class NeonBackground(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*color("#07111F"))
            self.bg = Rectangle(pos=self.pos, size=self.size)

            Color(0.10, 0.32, 0.95, 0.20)
            self.glow_1 = Ellipse(pos=(self.x - dp(80), self.top - dp(170)), size=(dp(260), dp(260)))

            Color(0.34, 0.13, 0.95, 0.16)
            self.glow_2 = Ellipse(pos=(self.right - dp(180), self.y + dp(60)), size=(dp(260), dp(260)))

            Color(0.05, 0.73, 0.55, 0.10)
            self.glow_3 = Ellipse(pos=(self.right - dp(300), self.top - dp(310)), size=(dp(220), dp(220)))

        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size
        self.glow_1.pos = (self.x - dp(80), self.top - dp(170))
        self.glow_2.pos = (self.right - dp(180), self.y + dp(60))
        self.glow_3.pos = (self.right - dp(300), self.top - dp(310))


class Card(BoxLayout):
    bg_color = ListProperty(color("#111827"))
    border_color = ListProperty(color("#263348"))
    shadow_color = ListProperty((0, 0, 0, 0.18))
    radius = NumericProperty(dp(22))
    border_width = NumericProperty(1)
    shadow_offset = NumericProperty(dp(5))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._shadow_col = Color(*self.shadow_color)
            self._shadow = RoundedRectangle(
                pos=(self.x, self.y - self.shadow_offset),
                size=self.size,
                radius=[self.radius],
            )
            self._bg_col = Color(*self.bg_color)
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
            self._border_col = Color(*self.border_color)
            self._border_line = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, self.radius),
                width=self.border_width,
            )
        self.bind(
            pos=self._update_canvas,
            size=self._update_canvas,
            bg_color=self._update_canvas,
            border_color=self._update_canvas,
            shadow_color=self._update_canvas,
            radius=self._update_canvas,
            shadow_offset=self._update_canvas,
        )

    def _update_canvas(self, *args):
        self._shadow_col.rgba = self.shadow_color
        self._shadow.pos = (self.x, self.y - self.shadow_offset)
        self._shadow.size = self.size
        self._shadow.radius = [self.radius]
        self._bg_col.rgba = self.bg_color
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._bg_rect.radius = [self.radius]
        self._border_col.rgba = self.border_color
        self._border_line.rounded_rectangle = (self.x, self.y, self.width, self.height, self.radius)
        self._border_line.width = self.border_width


class PillButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.bold = True
        self.font_size = sp(14)
        self.size_hint_y = None
        self.height = dp(48)


class AutoConspectApp(App):
    def build(self):
        Window.clearcolor = color("#07111F")

        self.selected_model = PRIMARY_MODEL
        self.detail_mode = "normal"
        self.last_result = ""
        self.last_model_used = ""
        self.request_running = False
        self.model_modal = None

        self.root_float = NeonBackground()

        self.scroll = ScrollView(size_hint=(1, 1), bar_width=dp(4), scroll_type=["bars", "content"])
        self.content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=[dp(18), dp(22), dp(18), dp(110)],
            spacing=dp(16),
        )
        self.content.bind(minimum_height=self.content.setter("height"))
        self.scroll.add_widget(self.content)
        self.root_float.add_widget(self.scroll)

        self._build_header()
        self._build_input_card()
        self._build_action_row()
        self._build_status_card()
        self._build_output_card()
        self._build_model_button()

        return self.root_float

    def _make_label(self, text, font_size, color_hex="#F8FAFC", bold=False, height=None, halign="left"):
        label = Label(
            text=text,
            font_size=sp(font_size),
            color=color(color_hex),
            bold=bold,
            halign=halign,
            valign="middle",
            size_hint_y=None,
            markup=False,
        )
        label.bind(width=lambda inst, value: setattr(inst, "text_size", (value, None)))
        if height is None:
            label.bind(texture_size=lambda inst, value: setattr(inst, "height", value[1] + dp(4)))
        else:
            label.height = dp(height)
        return label

    def _make_button(self, text, bg="#172033", fg="#F8FAFC", height=48, bold=True):
        return PillButton(
            text=text,
            height=dp(height),
            background_color=color(bg),
            color=color(fg),
            bold=bold,
        )

    def _build_header(self):
        hero = Card(
            orientation="vertical",
            padding=[dp(18), dp(18), dp(18), dp(18)],
            spacing=dp(12),
            size_hint_y=None,
            bg_color=color("#0D1B2E"),
            border_color=color("#28466F"),
            shadow_color=(0.02, 0.05, 0.12, 0.42),
            radius=dp(26),
        )
        hero.bind(minimum_height=hero.setter("height"))

        title_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(54), spacing=dp(12))

        logo = Card(
            size_hint=(None, None),
            size=(dp(54), dp(54)),
            bg_color=color("#4F8CFF"),
            border_color=color("#7CADFF"),
            shadow_color=(0.12, 0.28, 0.80, 0.35),
            radius=dp(18),
        )
        logo.add_widget(Label(text="AI", font_size=sp(18), bold=True, color=color("#FFFFFF")))
        title_row.add_widget(logo)

        title_box = BoxLayout(orientation="vertical", spacing=dp(0))
        title_box.add_widget(self._make_label("Автоконспект", 26, "#FFFFFF", True, 32))
        title_box.add_widget(self._make_label("Умный учебный конспект из любой темы", 12, "#B9C7DD", False, 20))
        title_row.add_widget(title_box)

        hero.add_widget(title_row)

        sub_card = Card(
            orientation="vertical",
            padding=[dp(13), dp(11), dp(13), dp(11)],
            size_hint_y=None,
            bg_color=color("#10243D"),
            border_color=color("#244B78"),
            shadow_color=(0, 0, 0, 0),
            radius=dp(18),
        )
        sub_card.bind(minimum_height=sub_card.setter("height"))
        sub_card.add_widget(self._make_label(
            "Вставь тему, лекцию или тезисы. Приложение выделит структуру, ключевые понятия и главное для повторения.",
            14,
            "#C5D2E8",
        ))
        hero.add_widget(sub_card)

        stats = GridLayout(cols=3, spacing=dp(8), size_hint_y=None, height=dp(58))
        stats.add_widget(self._mini_stat("01", "Тема"))
        stats.add_widget(self._mini_stat("02", "Модель"))
        stats.add_widget(self._mini_stat("03", "Конспект"))
        hero.add_widget(stats)

        self.content.add_widget(hero)

    def _mini_stat(self, number, text):
        card = Card(
            orientation="vertical",
            padding=[dp(8), dp(6), dp(8), dp(6)],
            bg_color=color("#0A1628"),
            border_color=color("#1E3657"),
            shadow_color=(0, 0, 0, 0),
            radius=dp(16),
        )
        card.add_widget(self._make_label(number, 13, "#6EA0FF", True, 20, "center"))
        card.add_widget(self._make_label(text, 11, "#90A2BD", False, 18, "center"))
        return card

    def _build_input_card(self):
        card = Card(
            orientation="vertical",
            padding=[dp(16), dp(16), dp(16), dp(16)],
            spacing=dp(13),
            size_hint_y=None,
            bg_color=color("#0E1A2C"),
            border_color=color("#233B5D"),
            shadow_color=(0, 0, 0, 0.30),
            radius=dp(24),
        )
        card.bind(minimum_height=card.setter("height"))

        card.add_widget(self._make_label("Материал для конспекта", 18, "#FFFFFF", True))
        card.add_widget(self._make_label("Лучше писать конкретно: тема, класс, стиль и желаемая длина.", 12, "#8495AF"))

        input_wrap = Card(
            orientation="vertical",
            padding=[dp(14), dp(10), dp(14), dp(10)],
            size_hint_y=None,
            height=dp(142),
            bg_color=color("#131F34"),
            border_color=color("#2B456B"),
            shadow_color=(0, 0, 0, 0.12),
            radius=dp(20),
        )
        self.topic_input = TextInput(
            hint_text="Например: фотосинтез простыми словами",
            font_size=sp(15),
            background_normal="",
            background_active="",
            background_color=(0, 0, 0, 0),
            foreground_color=color("#F8FAFC"),
            hint_text_color=color("#74849F"),
            cursor_color=color("#6EA0FF"),
            multiline=True,
            padding=[0, dp(10), 0, dp(8)],
        )
        input_wrap.add_widget(self.topic_input)
        card.add_widget(input_wrap)

        chips = GridLayout(cols=3, spacing=dp(8), size_hint_y=None, height=dp(48))
        self.detail_buttons = {}
        for key, info in DETAIL_OPTIONS.items():
            btn = self._make_button(info["label"], bg="#121D30", fg="#AEBBCE", height=46, bold=True)
            btn.bind(on_release=lambda inst, mode=key: self.set_detail_mode(mode))
            chips.add_widget(btn)
            self.detail_buttons[key] = btn
        card.add_widget(chips)

        self.content.add_widget(card)
        self.set_detail_mode("normal")

    def _build_action_row(self):
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(58), spacing=dp(10))

        self.generate_btn = self._make_button("Создать конспект", bg="#5B8CFF", fg="#FFFFFF", height=58, bold=True)
        self.generate_btn.bind(on_release=self.on_generate)
        row.add_widget(self.generate_btn)

        clear_btn = self._make_button("Очистить", bg="#0E1A2C", fg="#AEBBCE", height=58, bold=True)
        clear_btn.size_hint_x = 0.38
        clear_btn.bind(on_release=self.on_clear)
        row.add_widget(clear_btn)

        self.content.add_widget(row)

    def _build_status_card(self):
        self.status_card = Card(
            orientation="vertical",
            padding=[dp(15), dp(12), dp(15), dp(12)],
            spacing=dp(5),
            size_hint_y=None,
            bg_color=color("#0B1728"),
            border_color=color("#223858"),
            shadow_color=(0, 0, 0, 0.20),
            radius=dp(22),
        )
        self.status_card.bind(minimum_height=self.status_card.setter("height"))

        self.status_title = self._make_label("Готов к работе", 15, "#35D49B", True)
        self.status_text = self._make_label("Модель: 2.5 Flash, режим: Стандарт", 12, "#AEBBCE")
        self.status_card.add_widget(self.status_title)
        self.status_card.add_widget(self.status_text)
        self.content.add_widget(self.status_card)

    def _build_output_card(self):
        card = Card(
            orientation="vertical",
            padding=[dp(16), dp(16), dp(16), dp(16)],
            spacing=dp(12),
            size_hint_y=None,
            bg_color=color("#0E1A2C"),
            border_color=color("#233B5D"),
            shadow_color=(0, 0, 0, 0.30),
            radius=dp(24),
        )
        card.bind(minimum_height=card.setter("height"))

        top_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(10))
        title_box = BoxLayout(orientation="vertical")
        self.output_title = self._make_label("Конспект", 18, "#FFFFFF", True, 25)
        self.output_meta = self._make_label("Здесь появится результат", 12, "#8495AF", False, 17)
        title_box.add_widget(self.output_title)
        title_box.add_widget(self.output_meta)
        top_row.add_widget(title_box)

        copy_btn = self._make_button("Копировать", bg="#14243B", fg="#D7E2F4", height=42, bold=True)
        copy_btn.size_hint_x = 0.36
        copy_btn.bind(on_release=self.copy_result)
        top_row.add_widget(copy_btn)
        card.add_widget(top_row)

        result_wrap = Card(
            orientation="vertical",
            padding=[dp(15), dp(15), dp(15), dp(15)],
            size_hint_y=None,
            bg_color=color("#08111F"),
            border_color=color("#1B2E4A"),
            shadow_color=(0, 0, 0, 0.08),
            radius=dp(18),
        )
        result_wrap.bind(minimum_height=result_wrap.setter("height"))

        self.output_label = Label(
            text="Пока пусто. Введи тему выше и нажми Создать конспект.",
            font_size=sp(14),
            color=color("#AEBBCE"),
            halign="left",
            valign="top",
            markup=False,
            size_hint_y=None,
        )
        self.output_label.bind(width=lambda inst, value: setattr(inst, "text_size", (value, None)))
        self.output_label.bind(texture_size=lambda inst, value: setattr(inst, "height", value[1] + dp(14)))
        result_wrap.add_widget(self.output_label)
        card.add_widget(result_wrap)

        self.content.add_widget(card)

    def _build_model_button(self):
        holder = AnchorLayout(anchor_x="right", anchor_y="bottom", size_hint=(1, 1), padding=[0, 0, dp(16), dp(18)])
        self.model_button = Button(
            text="Модель: 2.5 Flash",
            font_size=sp(13),
            bold=True,
            size_hint=(None, None),
            size=(dp(158), dp(54)),
            background_normal="",
            background_down="",
            background_color=color("#2563EB"),
            color=color("#FFFFFF"),
        )
        self.model_button.bind(on_release=self.open_model_modal)
        holder.add_widget(self.model_button)
        self.root_float.add_widget(holder)

    def set_detail_mode(self, mode):
        self.detail_mode = mode
        for key, btn in self.detail_buttons.items():
            if key == mode:
                btn.background_color = color("#5B8CFF")
                btn.color = color("#FFFFFF")
            else:
                btn.background_color = color("#121D30")
                btn.color = color("#AEBBCE")
        if hasattr(self, "status_text"):
            self.update_ready_status()

    def update_ready_status(self):
        model_short = self.get_model_short(self.selected_model)
        detail = DETAIL_OPTIONS[self.detail_mode]["label"]
        self.status_text.text = f"Модель: {model_short}, режим: {detail}"
        self.model_button.text = f"Модель: {model_short}"

    def get_model_item(self, code):
        for item in MODEL_OPTIONS:
            if item["code"] == code:
                return item
        return MODEL_OPTIONS[0]

    def get_model_short(self, code):
        return self.get_model_item(code)["short"]

    def open_model_modal(self, *args):
        modal = ModalView(
            size_hint=(0.92, 0.86),
            background_color=(0, 0, 0, 0.60),
            auto_dismiss=True,
        )

        outer = Card(
            orientation="vertical",
            padding=[dp(14), dp(14), dp(14), dp(14)],
            spacing=dp(12),
            bg_color=color("#07111F"),
            border_color=color("#2B456B"),
            shadow_color=(0, 0, 0, 0.45),
            radius=dp(28),
        )

        header = Card(
            orientation="vertical",
            padding=[dp(16), dp(14), dp(16), dp(14)],
            spacing=dp(6),
            size_hint_y=None,
            bg_color=color("#0E1A2C"),
            border_color=color("#2B456B"),
            shadow_color=(0, 0, 0, 0.18),
            radius=dp(22),
        )
        header.bind(minimum_height=header.setter("height"))
        header.add_widget(self._make_label("Выбор модели", 22, "#FFFFFF", True))
        header.add_widget(self._make_label(
            "Если одна модель перегружена, переключись на другую. Да, теперь приложение хоть немного похоже на инструмент, а не на кнопку страдания.",
            12,
            "#AEBBCE",
        ))
        outer.add_widget(header)

        models_scroll = ScrollView(size_hint=(1, 1), bar_width=dp(3), scroll_type=["bars", "content"])
        models_box = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        models_box.bind(minimum_height=models_box.setter("height"))

        for item in MODEL_OPTIONS:
            active = item["code"] == self.selected_model
            model_card = Card(
                orientation="vertical",
                padding=[dp(12), dp(10), dp(12), dp(10)],
                spacing=dp(7),
                size_hint_y=None,
                bg_color=color("#173966") if active else color("#101E32"),
                border_color=color("#6EA0FF") if active else color("#243B5D"),
                shadow_color=(0, 0, 0, 0.12),
                radius=dp(18),
            )
            model_card.bind(minimum_height=model_card.setter("height"))

            title = item["label"] + (" - выбрано" if active else "")
            btn = self._make_button(title, bg="#5B8CFF" if active else "#14243B", fg="#FFFFFF", height=42, bold=True)
            btn.bind(on_release=lambda inst, model=item["code"], view=modal: self.select_model(model, view))
            model_card.add_widget(btn)
            model_card.add_widget(self._make_label(item["hint"], 11, "#A7B7CF"))
            models_box.add_widget(model_card)

        models_scroll.add_widget(models_box)
        outer.add_widget(models_scroll)

        close_btn = self._make_button("Закрыть", bg="#0E1A2C", fg="#D7E2F4", height=46, bold=True)
        close_btn.bind(on_release=lambda inst: modal.dismiss())
        outer.add_widget(close_btn)

        modal.add_widget(outer)
        self.model_modal = modal
        modal.open()

    def select_model(self, model_code, view=None):
        self.selected_model = model_code
        if view:
            view.dismiss()
        self.status_title.text = "Модель переключена"
        self.status_title.color = color("#35D49B")
        self.update_ready_status()

    def on_generate(self, *args):
        if self.request_running:
            self.set_status("Запрос уже идет", "Дождись ответа перед новым запуском.", "#F0B24C")
            return

        topic = self.topic_input.text.strip()
        if not topic:
            self.set_status("Нужна тема", "Поле пустое. Введи тему или текст для конспекта.", "#FF6B6B")
            return

        model_item = self.get_model_item(self.selected_model)
        if model_item["provider"] == "gemini" and not GEMINI_API_KEY:
            self.show_error("Не найден GEMINI_API_KEY. Проверь GitHub Secret и шаг Create secret_config.py в build.yml.")
            return
        if model_item["provider"] == "groq" and not GROQ_API_KEY:
            self.show_error("Не найден GROQ_API_KEY. Создай GitHub Secret с ключом Groq.")
            return

        mode_label = DETAIL_OPTIONS[self.detail_mode]["label"]
        max_tokens = DETAIL_OPTIONS[self.detail_mode]["tokens"]
        model = self.selected_model

        self.request_running = True
        self.generate_btn.disabled = True
        self.generate_btn.text = "Генерирую..."
        self.output_label.text = ""
        self.output_label.color = color("#AEBBCE")
        self.output_title.text = "Генерация"
        self.output_meta.text = f"{self.get_model_short(model)}, {mode_label}"
        self.set_status("Отправляем запрос", "Создаю структуру конспекта...", "#AEBBCE")

        thread = threading.Thread(target=self._worker_generate, args=(topic, model, max_tokens, mode_label), daemon=True)
        thread.start()

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
                self.ui(lambda: self.set_status(
                    "Сервер занят",
                    f"{self.get_model_short(model)} перегружена. Пробую {self.get_model_short(FALLBACK_MODEL)}...",
                    "#F0B24C",
                ))
                try:
                    result = self.call_model_with_retry(FALLBACK_MODEL, prompt, max_tokens)
                except Exception as e:
                    self.ui(lambda err=e: self.finish_error(f"Ошибка API: {err}"))
                    return
            else:
                self.ui(lambda: self.finish_error("Сервер выбранной модели сейчас перегружен. Попробуй позже или переключи модель."))
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
        return f"Режим длины: {mode_label}.\n\nСоставь конспект по теме или материалу ниже.\n\nМатериал:\n{topic}"

    def call_model_with_retry(self, model, prompt, max_tokens):
        last_error = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                self.ui(lambda a=attempt, m=model: self.set_status(
                    "Генерирую",
                    f"Модель {self.get_model_short(m)}, попытка {a}/{MAX_ATTEMPTS}",
                    "#AEBBCE",
                ))
                return self.call_model_once(model, prompt, max_tokens)
            except TemporaryAPIError as e:
                last_error = e
                if attempt < MAX_ATTEMPTS:
                    wait = (2 ** (attempt - 1)) + random.uniform(0.0, 0.4)
                    self.ui(lambda w=wait: self.set_status("Сервер занят", f"Повтор через {w:.1f} сек...", "#F0B24C"))
                    time.sleep(wait)
            except Exception:
                raise
        raise last_error or TemporaryAPIError("Временная ошибка API")

    def call_model_once(self, model, prompt, max_tokens):
        item = self.get_model_item(model)
        if item["provider"] == "groq":
            return self.call_groq_once(model, prompt, max_tokens)
        return self.call_gemini_once(model, prompt, max_tokens)

    def open_request(self, req):
        try:
            if SSL_CONTEXT:
                return urllib.request.urlopen(req, timeout=TIMEOUT_SEC, context=SSL_CONTEXT)
            return urllib.request.urlopen(req, timeout=TIMEOUT_SEC)
        except urllib.error.URLError as e:
            text = str(e)
            if ALLOW_SSL_FALLBACK and "CERTIFICATE_VERIFY_FAILED" in text:
                insecure_context = ssl._create_unverified_context()
                return urllib.request.urlopen(req, timeout=TIMEOUT_SEC, context=insecure_context)
            raise

    def call_gemini_once(self, model, prompt, max_tokens):
        item = self.get_model_item(model)
        api_version = item.get("api_version", "v1beta")
        url = f"https://generativelanguage.googleapis.com/{api_version}/models/{model}:generateContent"

        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.45,
                "topP": 0.9,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "text/plain",
            },
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "x-goog-api-key": GEMINI_API_KEY,
            },
            method="POST",
        )

        try:
            with self.open_request(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            message = self.parse_api_error(raw)
            if e.code in (429, 500, 502, 503, 504):
                raise TemporaryAPIError(message)
            raise APIError(f"{e.code}: {message}")
        except urllib.error.URLError as e:
            raise TemporaryAPIError(str(e))

        return self.parse_gemini_success(data)

    def call_groq_once(self, model, prompt, max_tokens):
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.45,
            "max_completion_tokens": max_tokens,
            "stream": False,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            GROQ_API_URL,
            data=body,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {GROQ_API_KEY}",
            },
            method="POST",
        )

        try:
            with self.open_request(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            message = self.parse_api_error(raw)
            if e.code in (429, 500, 502, 503, 504):
                raise TemporaryAPIError(message)
            raise APIError(f"{e.code}: {message}")
        except urllib.error.URLError as e:
            raise TemporaryAPIError(str(e))

        return self.parse_groq_success(data)

    def parse_gemini_success(self, data):
        candidates = data.get("candidates") or []
        if not candidates:
            raise APIError(f"Нет candidates в ответе: {data}")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            raise APIError(f"Нет текста в ответе: {data}")
        return {"text": text, "usage": data.get("usageMetadata", {})}

    def parse_groq_success(self, data):
        choices = data.get("choices") or []
        if not choices:
            raise APIError(f"Нет choices в ответе Groq: {data}")
        message = choices[0].get("message") or {}
        text = (message.get("content") or "").strip()
        if not text:
            raise APIError(f"Нет текста в ответе Groq: {data}")
        return {"text": text, "usage": data.get("usage", {})}

    def parse_api_error(self, raw):
        try:
            data = json.loads(raw)
            error = data.get("error")
            if isinstance(error, dict):
                return error.get("message", raw)
            return str(error or raw)
        except Exception:
            return raw[:500] if raw else "Неизвестная ошибка API"

    def finish_success(self, text, model_used, fallback_used, usage):
        self.last_result = text
        self.last_model_used = model_used
        self.output_label.text = text
        self.output_label.color = color("#F8FAFC")
        self.output_title.text = "Конспект готов"

        tokens = usage.get("totalTokenCount") or usage.get("total_tokens") or usage.get("total_tokens_count")
        token_part = f", токены: {tokens}" if tokens else ""
        fallback_part = ", fallback" if fallback_used else ""
        self.output_meta.text = f"{self.get_model_short(model_used)}{fallback_part}{token_part}"

        if fallback_used:
            self.set_status("Готово через запасную модель", f"Основная была занята, использована {self.get_model_short(model_used)}.", "#F0B24C")
        else:
            self.set_status("Конспект готов", f"Модель: {self.get_model_short(model_used)}", "#35D49B")

        self.request_running = False
        self.generate_btn.disabled = False
        self.generate_btn.text = "Создать конспект"

    def finish_error(self, msg):
        self.show_error(msg)
        self.request_running = False
        self.generate_btn.disabled = False
        self.generate_btn.text = "Создать конспект"

    def show_error(self, msg):
        self.output_title.text = "Ошибка"
        self.output_meta.text = "Запрос не выполнен"
        self.output_label.text = msg
        self.output_label.color = color("#FF6B6B")
        self.set_status("Ошибка", "Проверь ключ, сеть или выбранную модель.", "#FF6B6B")

    def set_status(self, title, text, title_color="#AEBBCE"):
        self.status_title.text = title
        self.status_title.color = color(title_color)
        self.status_text.text = text

    def ui(self, func):
        Clock.schedule_once(lambda dt: func(), 0)

    def copy_result(self, *args):
        if not self.last_result:
            self.set_status("Копировать нечего", "Сначала создай конспект.", "#F0B24C")
            return
        Clipboard.copy(self.last_result)
        self.set_status("Скопировано", "Конспект отправлен в буфер обмена.", "#35D49B")

    def on_clear(self, *args):
        self.topic_input.text = ""
        self.last_result = ""
        self.output_title.text = "Конспект"
        self.output_meta.text = "Здесь появится результат"
        self.output_label.text = "Пока пусто. Введи тему выше и нажми Создать конспект."
        self.output_label.color = color("#AEBBCE")
        self.status_title.text = "Готов к работе"
        self.status_title.color = color("#35D49B")
        self.update_ready_status()


class APIError(Exception):
    pass


class TemporaryAPIError(APIError):
    pass


if __name__ == "__main__":
    AutoConspectApp().run()
