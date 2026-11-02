# PyInstaller: gera dist/argos/ com argos.exe (terminal) e argos-app.exe (bandeja),
# compartilhando a mesma pasta _internal.
from pathlib import Path

RAIZ = Path(SPECPATH).parent
AQUI = Path(SPECPATH)

cli = Analysis([str(AQUI / "entrada_cli.py")], pathex=[str(RAIZ)])
app = Analysis(
    [str(AQUI / "entrada_app.py")],
    pathex=[str(RAIZ)],
    datas=[(str(RAIZ / "argos" / "app" / "ui"), "argos/app/ui")],
    hiddenimports=["pystray._win32", "webview.platforms.edgechromium", "webview.platforms.winforms"],
)

exe_cli = EXE(
    PYZ(cli.pure), cli.scripts, [], exclude_binaries=True, name="argos",
    console=True, icon=str(AQUI / "argos.ico"),
)
exe_app = EXE(
    PYZ(app.pure), app.scripts, [], exclude_binaries=True, name="argos-app",
    console=False, icon=str(AQUI / "argos.ico"),
)

COLLECT(exe_cli, cli.binaries, cli.datas, exe_app, app.binaries, app.datas, name="argos")
