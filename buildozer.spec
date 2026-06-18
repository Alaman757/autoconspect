[app]
title = Автоконспект
package.name = autoconspect
package.domain = org.autoconspect

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt,docx,pdf,md,csv,mp3,m4a,wav,ogg,webm,mp4,mpeg,mpga,flac
source.exclude_patterns = .git/*,.github/*,.venv/*,venv/*,__pycache__/*,*.pyc,*.pyo,*.rar,*.zip,*.apk,bin/*,build/*,.buildozer/*

version = 1.0

requirements = python3,kivy,certifi,pyjnius,plyer,pypdf,docx2txt,requests,urllib3

orientation = portrait
fullscreen = 0

android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True

p4a.bootstrap = sdl2

[buildozer]
log_level = 2
warn_on_root = 0
