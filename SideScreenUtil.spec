# -*- mode: python ; coding: utf-8 -*-


def normalized_name(entry):
    return entry[0].replace("\\", "/")


def required_binary(entry):
    """Keep only the Qt runtime and plugins used by this widget application."""
    name = normalized_name(entry)
    unused_qt_libraries = {
        "PySide6/Qt6Network.dll",
        "PySide6/Qt6OpenGL.dll",
        "PySide6/Qt6Pdf.dll",
        "PySide6/Qt6Qml.dll",
        "PySide6/Qt6QmlMeta.dll",
        "PySide6/Qt6QmlModels.dll",
        "PySide6/Qt6QmlWorkerScript.dll",
        "PySide6/Qt6Quick.dll",
        "PySide6/Qt6VirtualKeyboard.dll",
        "PySide6/opengl32sw.dll",
    }
    if name in unused_qt_libraries:
        return False
    if name.startswith("PySide6/translations/"):
        return False
    if not name.startswith("PySide6/plugins/"):
        return True
    required_plugins = {
        "PySide6/plugins/iconengines/qsvgicon.dll",
        "PySide6/plugins/imageformats/qico.dll",
        "PySide6/plugins/imageformats/qsvg.dll",
        "PySide6/plugins/platforms/qwindows.dll",
        "PySide6/plugins/styles/qmodernwindowsstyle.dll",
    }
    return name in required_plugins


a = Analysis(
    ["src/sidescreen/app.py"],
    pathex=[],
    binaries=[("src/sidescreen/native/windows_capture.pyd", "sidescreen/native")],
    datas=[
        ("assets/sidescreen-logo-app.png", "assets"),
        ("assets/sidescreen.ico", "assets"),
        ("assets/chevron-down.svg", "assets"),
        ("assets/refresh.svg", "assets"),
        ("assets/i18n", "assets/i18n"),
        ("src/sidescreen/native/WINDOWS_CAPTURE_LICENSE.txt", "licenses"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "cv2",
        "windows_capture",
        "PySide6.QtNetwork",
        "PySide6.QtOpenGL",
        "PySide6.QtPdf",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtVirtualKeyboard",
        "numpy.testing",
        "tkinter",
        "unittest",
        "pydoc",
        "doctest",
    ],
    noarchive=False,
    optimize=2,
)
a.binaries = [entry for entry in a.binaries if required_binary(entry)]
a.datas = [
    entry
    for entry in a.datas
    if not normalized_name(entry).startswith("PySide6/translations/")
]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [("O", None, "OPTION"), ("O", None, "OPTION")],
    name="SideScreenUtil",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=["assets/sidescreen.ico"],
)
