[app]
title = Автоконспект
package.name = autoconspect
package.domain = org.autoconspect

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas

version = 1.0

requirements = python3,kivy,certifi

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
