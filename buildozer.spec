[app]
title = Автоконспект
package.name = autoconspect
package.domain = org.autoconspect

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json
source.exclude_patterns = .git/*,.github/*,.venv/*,venv/*,__pycache__/*,*.pyc,*.pyo,*.rar,*.zip,*.apk,bin/*,build/*,.buildozer/*,secret_config.local.py

version = 1.0
requirements = python3,kivy
orientation = portrait
fullscreen = 0

android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a
android.build_tools = 33.0.2
android.skip_update = True
android.accept_sdk_license = True

p4a.bootstrap = sdl2
p4a.branch = develop

[buildozer]
log_level = 2
