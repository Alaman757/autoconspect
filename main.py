import json
import os
import random
import threading
import time
import urllib.error
import urllib.request

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.properties import ListProperty, NumericProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import get_color_from_hex

try:
    from secret_config import GEMINI_API_KEY
except Exception:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

MODEL_OPTIONS = [
    {
        "label": "Gemini 2.5 Flash",
        "short": "2.5 Flash",
        "code": "gemini-2.5-flash",
        "hint": "Основная модель. Качество выше, но иногда ловит 503 из-за нагрузки.",
    },
    {
        "label": "Gemini 2.5 Flash-Lite",
        "short": "2.5 Lite",
        "code": "gemini-2.5-flash-lite",
        "hint": "Быстрее и стабильнее. Хороший запасной вариант для диплома.",
    },
    {
        "label": "Gemini 1.5 Flash",
        "short": "1.5 Flash",
        "code": "gemini-1.5-flash",
        "hint": "Старый режим. Может быть недоступен в API, но оставлен для проверки.",
    },
]

DETAIL_OPTIONS = {
    "short": {"label": "Кратко", "tokens": 512},
    "normal": {"label": "Стандарт", "tokens": 896},
    "full": {"label": "Подробно", "tokens": 1400},
}

PRIMARY_MODEL = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-2.5-flash-lite"
MAX_ATTEMPTS = 3
TIMEOUT_SEC = 45

SYSTEM_PROMPT = """Ты — профессиональный составитель учебных конспектов. Пиши на русском языке.

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
• пункт
• пункт
• пункт

Ключевые понятия:
• термин: объяснение

Главное запомнить:
1. мысль
2. мысль
3. мысль
"""


def color(hex_value):
    return get_color_from_hex(hex_value)


class Card(BoxLayout):
    bg_color = ListProperty(color("#111827"))
    border_color = ListProperty(color("#243146"))
    radius = NumericProperty(dp(18))
    border_width = NumericProperty(1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
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
            radius=self._update_canvas,
        )

    def _update_canvas(self, *args):
        self._bg_col.rgba = self.bg_color
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._bg_rect.radius = [self.radius]
        self._border_col.rgba = self.border_color
        self._border_line.rounded_rectangle = (self.x, self.y, self.width, self.height, self.radius)
        self._border_line.width = self.border_width


class AutoConspectApp(App):
    def build(self):
        Window.clearcolor = color("#0B1220")
        self.selected_model = PRIMARY_MODEL
        self.detail_mode = "normal"
        self.last_result = ""
        self.last_model_used = ""
        self.request_running = False
        self.model_popup = None

        self.root_float = FloatLayout()

        scroll = ScrollView(
            size_hint=(1, 1),
            bar_width=dp(4),
            scroll_type=["bars", "content"],
        )
        self.content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=[dp(18), dp(22), dp(18), dp(105)],
            spacing=dp(14),
        )
        self.content.bind(minimum_height=self.content.setter("height"))
        scroll.add_widget(self.content)
        self.root_float.add_widget(scroll)

        self._build_header()
        self._build_input_card()
        self._build_action_row()
        self._build_status_card()
        self._build_output_card()
        self._build_model_fab()

        return self.root_float

    def _make_label(self, text, font_size, color_hex="#F5F7FB", bold=False, height=None):
        label = Label(
            text=text,
            font_size=sp(font_size),
            color=color(color_hex),
            bold=bold,
            halign="left",
            valign="middle",
            size_hint_y=None,
        )
        label.bind(width=lambda inst, value: setattr(inst, "text_size", (value, None)))
        if height is None:
            label.bind(texture_size=lambda inst, value: setattr(inst, "height", value[1] + dp(4)))
        else:
            label.height = dp(height)
        return label

    def _make_button(self, text, bg="#172033", fg="#F5F7FB", height=48, bold=True):
        btn = Button(
            text=text,
            font_size=sp(14),
            bold=bold,
            size_hint_y=None,
            height=dp(height),
            background_normal="",
            background_down="",
            background_color=color(bg),
            color=color(fg),
        )
        return btn

    def _build_header(self):
        header = Card(
            orientation="vertical",
            padding=[dp(18), dp(18), dp(18), dp(16)],
            spacing=dp(8),
            size_hint_y=None,
            bg_color=color("#101A2D"),
            border_color=color("#263854"),
            radius=dp(22),
        )
        header.bind(minimum_height=header.setter("height"))

        title_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(10))

        logo = Card(
            size_hint=(None, None),
            size=(dp(42), dp(42)),
            bg_color=color("#1D4ED8"),
            border_color=color("#5B8CFF"),
            radius=dp(14),
        )
        logo_label = Label(text="AI", font_size=sp(16), bold=True, color=color("#FFFFFF"))
        logo.add_widget(logo_label)
        title_row.add_widget(logo)

        title_box = BoxLayout(orientation="vertical", spacing=dp(0))
        title_box.add_widget(self._make_label("Автоконспект", 24, "#F5F7FB", True, 28))
        title_box.add_widget(self._make_label("Тема → структура → готовый конспект", 12, "#AEB8CC", False, 18))
        title_row.add_widget(title_box)

        header.add_widget(title_row)
        header.add_widget(self._make_label(
            "Вставь тему, текст лекции или тезисы. Приложение само соберёт аккуратный учебный конспект.",
            14,
            "#AEB8CC",
        ))
        self.content.add_widget(header)

    def _build_input_card(self):
        card = Card(
            orientation="vertical",
            padding=[dp(16), dp(16), dp(16), dp(16)],
            spacing=dp(12),
            size_hint_y=None,
            bg_color=color("#111827"),
            border_color=color("#243146"),
            radius=dp(20),
        )
        card.bind(minimum_height=card.setter("height"))

        card.add_widget(self._make_label("Что законспектировать?", 17, "#F5F7FB", True))
        card.add_widget(self._make_label("Чем точнее запрос, тем чище структура. Например: 'Фотосинтез простыми словами, кратко'.", 12, "#7E8AA3"))

        input_wrap = Card(
            orientation="vertical",
            padding=[dp(12), dp(8), dp(12), dp(8)],
            size_hint_y=None,
            height=dp(128),
            bg_color=color("#172033"),
            border_color=color("#2B3A55"),
            radius=dp(18),
        )
        self.topic_input = TextInput(
            hint_text="Введите тему, описание или текст...",
            font_size=sp(15),
            background_normal="",
            background_active="",
            background_color=(0, 0, 0, 0),
            foreground_color=color("#F5F7FB"),
            hint_text_color=color("#7E8AA3"),
            cursor_color=color("#5B8CFF"),
            multiline=True,
            padding=[0, dp(8), 0, dp(8)],
        )
        input_wrap.add_widget(self.topic_input)
        card.add_widget(input_wrap)

        chips = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(42))
        self.detail_buttons = {}
        for key, info in DETAIL_OPTIONS.items():
            btn = self._make_button(info["label"], bg="#172033", fg="#AEB8CC", height=40, bold=True)
            btn.bind(on_release=lambda inst, mode=key: self.set_detail_mode(mode))
            chips.add_widget(btn)
            self.detail_buttons[key] = btn
        card.add_widget(chips)
        self.content.add_widget(card)
        self.set_detail_mode("normal")

    def _build_action_row(self):
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(54), spacing=dp(10))
        self.generate_btn = self._make_button("Создать конспект", bg="#5B8CFF", fg="#FFFFFF", height=54, bold=True)
        self.generate_btn.bind(on_release=self.on_generate)
        row.add_widget(self.generate_btn)

        clear_btn = self._make_button("Очистить", bg="#111827", fg="#AEB8CC", height=54, bold=True)
        clear_btn.size_hint_x = 0.38
        clear_btn.bind(on_release=self.on_clear)
        row.add_widget(clear_btn)

        self.content.add_widget(row)

    def _build_status_card(self):
        self.status_card = Card(
            orientation="vertical",
            padding=[dp(14), dp(12), dp(14), dp(12)],
            spacing=dp(4),
            size_hint_y=None,
            bg_color=color("#0F172A"),
            border_color=color("#243146"),
            radius=dp(18),
        )
        self.status_card.bind(minimum_height=self.status_card.setter("height"))

        self.status_title = self._make_label("Готов к работе", 14, "#2CCB8C", True)
        self.status_text = self._make_label("Модель: Gemini 2.5 Flash · режим: Стандарт", 12, "#AEB8CC")
        self.status_card.add_widget(self.status_title)
        self.status_card.add_widget(self.status_text)
        self.content.add_widget(self.status_card)

    def _build_output_card(self):
        card = Card(
            orientation="vertical",
            padding=[dp(16), dp(16), dp(16), dp(16)],
            spacing=dp(12),
            size_hint_y=None,
            bg_color=color("#111827"),
            border_color=color("#243146"),
            radius=dp(20),
        )
        card.bind(minimum_height=card.setter("height"))

        top_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
        title_box = BoxLayout(orientation="vertical")
        self.output_title = self._make_label("Конспект", 17, "#F5F7FB", True, 23)
        self.output_meta = self._make_label("Здесь появится результат", 12, "#7E8AA3", False, 17)
        title_box.add_widget(self.output_title)
        title_box.add_widget(self.output_meta)
        top_row.add_widget(title_box)

        copy_btn = self._make_button("Копия", bg="#172033", fg="#AEB8CC", height=40, bold=True)
        copy_btn.size_hint_x = 0.32
        copy_btn.bind(on_release=self.copy_result)
        top_row.add_widget(copy_btn)
        card.add_widget(top_row)

        result_wrap = Card(
            orientation="vertical",
            padding=[dp(14), dp(14), dp(14), dp(14)],
            size_hint_y=None,
            bg_color=color("#0B1220"),
            border_color=color("#1E2B43"),
            radius=dp(16),
        )
        result_wrap.bind(minimum_height=result_wrap.setter("height"))

        self.output_label = Label(
            text="Пока пусто. Введи тему выше и нажми «Создать конспект».",
            font_size=sp(14),
            color=color("#AEB8CC"),
            halign="left",
            valign="top",
            markup=False,
            size_hint_y=None,
        )
        self.output_label.bind(width=lambda inst, value: setattr(inst, "text_size", (value, None)))
        self.output_label.bind(texture_size=lambda inst, value: setattr(inst, "height", value[1] + dp(10)))
        result_wrap.add_widget(self.output_label)
        card.add_widget(result_wrap)
        self.content.add_widget(card)

    def _build_model_fab(self):
        holder = AnchorLayout(
            anchor_x="right",
            anchor_y="bottom",
            size_hint=(1, 1),
            padding=[0, 0, dp(16), dp(18)],
        )
        self.model_button = Button(
            text="2.5 Flash  ↓",
            font_size=sp(13),
            bold=True,
            size_hint=(None, None),
            size=(dp(136), dp(52)),
            background_normal="",
            background_down="",
            background_color=color("#1D4ED8"),
            color=color("#FFFFFF"),
        )
        self.model_button.bind(on_release=self.open_model_popup)
        holder.add_widget(self.model_button)
        self.root_float.add_widget(holder)

    def set_detail_mode(self, mode):
        self.detail_mode = mode
        for key, btn in self.detail_buttons.items():
            if key == mode:
                btn.background_color = color("#5B8CFF")
                btn.color = color("#FFFFFF")
            else:
                btn.background_color = color("#172033")
                btn.color = color("#AEB8CC")
        if hasattr(self, "status_text"):
            self.update_ready_status()

    def update_ready_status(self):
        model_short = self.get_model_short(self.selected_model)
        detail = DETAIL_OPTIONS[self.detail_mode]["label"]
        self.status_text.text = f"Модель: Gemini {model_short} · режим: {detail}"
        self.model_button.text = f"{model_short}  ↓"

    def get_model_short(self, code):
        for item in MODEL_OPTIONS:
            if item["code"] == code:
                return item["short"]
        return code.replace("gemini-", "")

    def open_model_popup(self, *args):
        box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))
        hint = Label(
            text="Выбери модель для новых запросов. Если 2.5 перегружена, попробуй Flash-Lite или 1.5.",
            font_size=sp(13),
            color=color("#AEB8CC"),
            size_hint_y=None,
            halign="left",
            valign="top",
        )
        hint.bind(width=lambda inst, value: setattr(inst, "text_size", (value, None)))
        hint.bind(texture_size=lambda inst, value: setattr(inst, "height", value[1] + dp(8)))
        box.add_widget(hint)

        for item in MODEL_OPTIONS:
            active = item["code"] == self.selected_model
            text = item["label"]
            if active:
                text += "  · активно"
            btn = self._make_button(
                text,
                bg="#5B8CFF" if active else "#172033",
                fg="#FFFFFF" if active else "#F5F7FB",
                height=48,
                bold=True,
            )
            btn.bind(on_release=lambda inst, model=item["code"]: self.select_model(model))
            box.add_widget(btn)

            sub = self._make_label(item["hint"], 11, "#7E8AA3")
            box.add_widget(sub)

        self.model_popup = Popup(
            title="Версия Gemini",
            content=box,
            size_hint=(0.92, None),
            height=dp(410),
            auto_dismiss=True,
        )
        self.model_popup.open()

    def select_model(self, model_code):
        self.selected_model = model_code
        if self.model_popup:
            self.model_popup.dismiss()
        self.status_title.text = "Модель переключена"
        self.status_title.color = color("#2CCB8C")
        self.update_ready_status()

    def on_generate(self, *args):
        if self.request_running:
            self.set_status("Запрос уже идёт", "Дождись ответа. Повторный тап не ускорит сервер, внезапно.", "#F0B24C")
            return

        topic = self.topic_input.text.strip()
        if not topic:
            self.set_status("Нужна тема", "Поле пустое. Модель не умеет читать мысли, трагедия века.", "#FF6B6B")
            return

        if not GEMINI_API_KEY:
            self.show_error("Не найден GEMINI_API_KEY. Проверь GitHub Secret и шаг Create secret_config.py в build.yml.")
            return

        mode_label = DETAIL_OPTIONS[self.detail_mode]["label"]
        max_tokens = DETAIL_OPTIONS[self.detail_mode]["tokens"]
        model = self.selected_model

        self.request_running = True
        self.generate_btn.disabled = True
        self.generate_btn.text = "Генерирую..."
        self.output_label.text = ""
        self.output_label.color = color("#AEB8CC")
        self.output_title.text = "Генерация"
        self.output_meta.text = f"{self.get_model_short(model)} · {mode_label}"
        self.set_status("Отправляем запрос", "Создаю структуру конспекта...", "#AEB8CC")

        thread = threading.Thread(
            target=self._worker_generate,
            args=(topic, model, max_tokens, mode_label),
            daemon=True,
        )
        thread.start()

    def _worker_generate(self, topic, model, max_tokens, mode_label):
        prompt = self.build_user_prompt(topic, mode_label)
        fallback_used = False
        model_used = model

        try:
            result = self.call_gemini_with_retry(model, prompt, max_tokens)
        except TemporaryGeminiError:
            if model != FALLBACK_MODEL:
                fallback_used = True
                model_used = FALLBACK_MODEL
                self.ui(lambda: self.set_status(
                    "Сервер занят",
                    f"{self.get_model_short(model)} перегружена. Пробую {self.get_model_short(FALLBACK_MODEL)}...",
                    "#F0B24C",
                ))
                try:
                    result = self.call_gemini_with_retry(FALLBACK_MODEL, prompt, max_tokens)
                except Exception as e:
                    self.ui(lambda err=e: self.finish_error(f"Ошибка API: {err}"))
                    return
            else:
                self.ui(lambda: self.finish_error("Сервер Gemini сейчас перегружен. Попробуй позже или переключи модель."))
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
        return (
            f"Режим длины: {mode_label}.\n\n"
            f"Составь конспект по теме или материалу ниже.\n\n"
            f"Материал:\n{topic}"
        )

    def call_gemini_with_retry(self, model, prompt, max_tokens):
        last_error = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                self.ui(lambda a=attempt, m=model: self.set_status(
                    "Генерирую",
                    f"Модель {self.get_model_short(m)} · попытка {a}/{MAX_ATTEMPTS}",
                    "#AEB8CC",
                ))
                return self.call_gemini_once(model, prompt, max_tokens)
            except TemporaryGeminiError as e:
                last_error = e
                if attempt < MAX_ATTEMPTS:
                    wait = (2 ** (attempt - 1)) + random.uniform(0.0, 0.4)
                    self.ui(lambda w=wait: self.set_status(
                        "Сервер занят",
                        f"Повтор через {w:.1f} сек...",
                        "#F0B24C",
                    ))
                    time.sleep(wait)
            except Exception:
                raise
        raise last_error or TemporaryGeminiError("Временная ошибка Gemini")

    def call_gemini_once(self, model, prompt, max_tokens):
        url = API_URL.format(model=model)
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
            with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            message = self.parse_api_error(raw)
            if e.code in (429, 503, 504):
                raise TemporaryGeminiError(message)
            raise GeminiAPIError(f"{e.code}: {message}")
        except urllib.error.URLError as e:
            raise TemporaryGeminiError(str(e))

        return self.parse_api_success(data)

    def parse_api_success(self, data):
        candidates = data.get("candidates") or []
        if not candidates:
            raise GeminiAPIError(f"Нет candidates в ответе: {data}")

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            raise GeminiAPIError(f"Нет текста в ответе: {data}")

        return {
            "text": text,
            "usage": data.get("usageMetadata", {}),
        }

    def parse_api_error(self, raw):
        try:
            data = json.loads(raw)
            return data.get("error", {}).get("message", raw)
        except Exception:
            return raw[:500] if raw else "Неизвестная ошибка API"

    def finish_success(self, text, model_used, fallback_used, usage):
        self.last_result = text
        self.last_model_used = model_used
        self.output_label.text = text
        self.output_label.color = color("#F5F7FB")
        self.output_title.text = "Конспект готов"

        tokens = usage.get("totalTokenCount") or usage.get("total_tokens")
        token_part = f" · токены: {tokens}" if tokens else ""
        fallback_part = " · fallback" if fallback_used else ""
        self.output_meta.text = f"{self.get_model_short(model_used)}{fallback_part}{token_part}"

        if fallback_used:
            self.set_status("Готово через запасную модель", f"Основная была занята, использована {self.get_model_short(model_used)}.", "#F0B24C")
        else:
            self.set_status("Конспект готов", f"Модель: {self.get_model_short(model_used)}", "#2CCB8C")

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

    def set_status(self, title, text, title_color="#AEB8CC"):
        self.status_title.text = title
        self.status_title.color = color(title_color)
        self.status_text.text = text

    def ui(self, func):
        Clock.schedule_once(lambda dt: func(), 0)

    def copy_result(self, *args):
        if not self.last_result:
            self.set_status("Копировать нечего", "Сначала создай конспект. Пустоту в буфер тащить не будем.", "#F0B24C")
            return
        Clipboard.copy(self.last_result)
        self.set_status("Скопировано", "Конспект отправлен в буфер обмена.", "#2CCB8C")

    def on_clear(self, *args):
        self.topic_input.text = ""
        self.last_result = ""
        self.output_title.text = "Конспект"
        self.output_meta.text = "Здесь появится результат"
        self.output_label.text = "Пока пусто. Введи тему выше и нажми «Создать конспект»."
        self.output_label.color = color("#AEB8CC")
        self.status_title.text = "Готов к работе"
        self.status_title.color = color("#2CCB8C")
        self.update_ready_status()


class GeminiAPIError(Exception):
    pass


class TemporaryGeminiError(GeminiAPIError):
    pass


if __name__ == "__main__":
    AutoConspectApp().run()
