from pathlib import Path

from sidescreen.startup import startup_command


def test_startup_command_quotes_executable_and_adds_startup_flag() -> None:
    executable = Path(r"C:\Program Files\SideScreenUtil\SideScreenUtil.exe")
    assert startup_command(executable) == (
        r'"C:\Program Files\SideScreenUtil\SideScreenUtil.exe" --startup'
    )
