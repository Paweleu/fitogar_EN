# buildozer.spec

[app]
title = Fitogar
package.name = fitogar
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,ini,txt,md,ttf,otf,ico
version = 1.0.0
requirements = python3,kivy,cython,bleak
orientation = portrait
fullscreen = 1
android.permissions = INTERNET,BLUETOOTH,BLUETOOTH_ADMIN,BLUETOOTH_CONNECT,BLUETOOTH_SCAN,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.archs = armeabi-v7a,arm64-v8a,x86,x86_64

# (Opcjonalnie) Dodaj inne ustawienia, np. ikony, splash, itd.
# android.icon = assets/images/ico_mini.png
# android.presplash = assets/images/tlo3.png

# ...reszta domyślnych ustawień buildozer.spec...
