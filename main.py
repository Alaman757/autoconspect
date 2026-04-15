import json
import os

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from kivy.utils import get_color_from_hex
from kivy.metrics import dp
from kivy.network.urlrequest import UrlRequest

# ─────────────────────────────────────────
#  КЛЮЧ ТЕПЕРЬ БЕРЁТСЯ ИЗ secret_config.py
# ─────────────────────────────────────────
from secret_config import GEMINI_API_KEY
# ─────────────────────────────────────────

SYSTEM_PROMPT = """Ты — профессиональный составитель конспектов. Пишешь на русском языке.

ВАЖНО — читай запрос внимательно и соблюдай указания пользователя:
- Если просят "больше", "подробнее", "развёрнуто" — пиши максимально полный конспект
- Если просят "короче", "кратко", "сжато" — пиши только самое главное
- Если просят "простыми словами" — избегай сложных терминов
- Если просят "академически" — используй научный стиль

Стандартный формат конспекта:
1. Заголовок темы (большими буквами)
2. Краткое введение (2-3 предложения)
3. Основные разделы с подзаголовками
4. Ключевые понятия выделяй через двоеточие
5. Важные списки оформляй через •
6. В конце — краткие выводы

Только конспект — без вводных слов."""


class ConspectApp(App):
    def build(self):
        Window.clearcolor = get_color_from_hex("#0f1117")

        self.current_request = None

        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))

        title = Label(
            text="Автоконспект",
            font_size=dp(22),
            bold=True,
            color=get_color_from_hex("#4f8cff"),
            size_hint_y=None,
            height=dp(50),
        )
        root.add_widget(title)

        subtitle = Label(
            text="ИИ генерирует конспект по вашей теме",
            font_size=dp(13),
            color=get_color_from_hex("#8890a4"),
            size_hint_y=None,
            height=dp(25),
        )
        root.add_widget(subtitle)

        self.topic_input = TextInput(
            hint_text="Введите тему или описание...",
            font_size=dp(15),
            background_color=get_color_from_hex("#1a1d27"),
            foreground_color=get_color_from_hex("#e8eaf0"),
            hint_text_color=get_color_from_hex("#8890a4"),
            cursor_color=get_color_from_hex("#4f8cff"),
            size_hint_y=None,
            height=dp(80),
            multiline=True,
            padding=[dp(12), dp(10)],
        )
        root.add_widget(self.topic_input)

        btn_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(48),
            spacing=dp(10)
        )

        self.gen_btn = Button(
            text="Создать конспект",
            font_size=dp(15),
            bold=True,
            background_color=get_color_from_hex("#4f8cff"),
            color=get_color_from_hex("#ffffff"),
            on_press=self.on_generate,
        )
        btn_row.add_widget(self.gen_btn)

        clear_btn = Button(
            text="Очистить",
            font_size=dp(14),
            background_color=get_color_from_hex("#1a1d27"),
            color=get_color_from_hex("#8890a4"),
            size_hint_x=0.35,
            on_press=self.on_clear,
        )
        btn_row.add_widget(clear_btn)

        root.add_widget(btn_row)

        self.status_label = Label(
            text="Введите тему и нажмите «Создать конспект»",
            font_size=dp(12),
            color=get_color_from_hex("#8890a4"),
            size_hint_y=None,
            height=dp(25),
        )
        root.add_widget(self.status_label)

        scroll = ScrollView()

        self.output_label = Label(
            text="",
            font_size=dp(14),
            color=get_color_from_hex("#e8eaf0"),
            size_hint_y=None,
            text_size=(Window.width - dp(32), None),
            markup=True,
            valign="top",
            padding=[dp(12), dp(12)],
        )
        self.output_label.bind(texture_size=self.output_label.setter("size"))

        scroll.add_widget(self.output_label)
        root.add_widget(scroll)

        return root

    def on_generate(self, *args):
        topic = self.topic_input.text.strip()

        if not topic:
            self.status_label.text = "Введите тему!"
            self.status_label.color = get_color_from_hex("#e05c5c")
            return

        self.output_label.text = ""
        self.status_label.text = "Генерирую..."
        self.status_label.color = get_color_from_hex("#8890a4")
        self.gen_btn.disabled = True
        self.gen_btn.text = "Генерирую..."

        # ❗ КЛЮЧ УБРАН ИЗ URL
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

        payload_dict = {
            "system_instruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": [
                {
                    "parts": [
                        {
                            "text": f"Составь конспект по теме: {topic}"
                        }
                    ]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": 8192,
                "temperature": 0.7
            }
        }

        body = json.dumps(payload_dict)

        # ❗ КЛЮЧ ТЕПЕРЬ В HEADER
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        }

        try:
            self.current_request = UrlRequest(
                url=url,
                req_body=body,
                req_headers=headers,
                method="POST",
                timeout=60,
                on_success=self.request_success,
                on_error=self.request_error,
                on_failure=self.request_failure,
                on_redirect=self.request_redirect,
                verify=False
            )
        except Exception as e:
            self.on_error(f"Ошибка запуска запроса: {str(e)}")

    def request_success(self, request, result):
        try:
            candidates = result.get("candidates")
            text = candidates[0]["content"]["parts"][0]["text"]

            self.output_label.text = text
            self.status_label.text = "Конспект готов"
            self.status_label.color = get_color_from_hex("#4caf82")
            self.gen_btn.disabled = False
            self.gen_btn.text = "Создать конспект"

        except Exception as e:
            self.on_error(f"Ошибка обработки: {str(e)}")

    def request_error(self, request, error):
        self.on_error(f"Ошибка сети: {str(error)}")

    def request_failure(self, request, result):
        self.on_error(f"Ошибка API: {str(result)}")

    def request_redirect(self, request, result):
        self.on_error("Редирект запроса")

    def on_error(self, msg):
        self.output_label.text = f"[color=#e05c5c]{msg}[/color]"
        self.status_label.text = "Ошибка"
        self.status_label.color = get_color_from_hex("#e05c5c")
        self.gen_btn.disabled = False
        self.gen_btn.text = "Создать конспект"

    def on_clear(self, *args):
        self.topic_input.text = ""
        self.output_label.text = ""
        self.status_label.text = "Введите тему и нажмите «Создать конспект»"
        self.status_label.color = get_color_from_hex("#8890a4")


if __name__ == "__main__":
    ConspectApp().run()
