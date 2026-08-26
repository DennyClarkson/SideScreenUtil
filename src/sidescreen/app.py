from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from sidescreen.i18n import tr
from sidescreen.main_window import MainWindow
from sidescreen.resources import asset_path
from sidescreen.win32_api import enable_per_monitor_dpi_awareness


def configure_logging() -> None:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SideScreenUtil"
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        base.mkdir(parents=True, exist_ok=True)
        handlers.insert(0, logging.FileHandler(base / "sidescreen.log", encoding="utf-8"))
    except OSError:
        # The app should remain usable in a locked-down or read-only profile.
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def main(argv: list[str] | None = None) -> int:
    if sys.platform != "win32":
        print(tr("platform.windows_only"), file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--startup", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--capture-smoke-test", action="store_true")
    arguments, qt_arguments = parser.parse_known_args(argv)
    enable_per_monitor_dpi_awareness()
    configure_logging()
    QCoreApplication.setOrganizationName("SideScreenUtil")
    QCoreApplication.setApplicationName("SideScreenUtil")
    application = QApplication([sys.argv[0], *qt_arguments])
    application.setQuitOnLastWindowClosed(False)
    application.setWindowIcon(QIcon(str(asset_path("sidescreen.ico"))))
    window = MainWindow()
    capture_session = None
    if arguments.capture_smoke_test:
        from sidescreen.capture import CaptureSession
        from sidescreen.filters import FilterConfig
        from sidescreen.win32_api import enumerate_windows

        sources = enumerate_windows()
        if not sources:
            QTimer.singleShot(0, lambda: application.exit(3))
        else:
            capture_session = CaptureSession()

            def finish_capture_test(exit_code: int) -> None:
                if capture_session is not None:
                    capture_session.stop()
                window._tray.hide()
                application.exit(exit_code)

            capture_session.frame_ready.connect(
                lambda _data, _width, _height: finish_capture_test(0)
            )
            capture_session.start(sources[0], 8, FilterConfig(style="edge"))
            QTimer.singleShot(8000, lambda: finish_capture_test(4))
    elif arguments.smoke_test:
        QTimer.singleShot(300, window.quit_application)
    else:
        window.sync_startup_registration()
        if not window.silent_start:
            window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
