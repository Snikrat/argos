"""argos-app: ícone na bandeja + janela do painel."""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
import time
from pathlib import Path

from argos import config

UI = Path(__file__).with_name("ui")
MUTEX = "Local\\argos-app"
EVENTO_MOSTRAR = "Local\\argos-app-mostrar"


def _configurar_log() -> None:
    config.PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=config.PASTA_DADOS / "app.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")


def _ja_rodando() -> bool:
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = ctypes.c_void_p
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    # "Reiniciar o Argos": a instância nova espera a antiga terminar de fechar
    tentativas = 60 if "--reinicio" in sys.argv else 1
    for n in range(tentativas):
        _configurar_log.mutex = k32.CreateMutexW(None, False, MUTEX)  # mantém o handle vivo
        existe = k32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
        if not existe or n == tentativas - 1:
            break
        k32.CloseHandle(_configurar_log.mutex)
        time.sleep(0.25)
    if existe:
        ev = k32.OpenEventW(0x0002, False, EVENTO_MOSTRAR)  # EVENT_MODIFY_STATE
        if ev:
            k32.SetEvent(ev)
            k32.CloseHandle(ev)
        return True
    return False


def tema_escuro() -> bool:
    import winreg

    try:
        chave = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        return winreg.QueryValueEx(chave, "AppsUseLightTheme")[0] == 0
    except OSError:
        return True


def arredondar_cantos(janela) -> None:
    """Cantos arredondados do Windows 11 também na janela sem borda."""
    try:
        hwnd = janela.native.Handle.ToInt32()
        valor = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(valor), 4)
    except Exception:
        logging.exception("não consegui arredondar os cantos")


def _esperar_pedidos(mostrar) -> None:
    """Outra instância pediu para mostrar a janela (ex: `argos app` com o app já aberto)."""
    k32 = ctypes.windll.kernel32
    ev = k32.CreateEventW(None, False, False, EVENTO_MOSTRAR)
    while True:
        if k32.WaitForSingleObject(ev, 0xFFFFFFFF) == 0:
            mostrar()


def main() -> None:
    _configurar_log()
    if _ja_rodando():
        return

    import webview

    from argos.app.api import Api
    from argos.app.bandeja import Bandeja
    from argos.app.monitor import Monitor
    from argos.plataforma import abrir_pasta, registrar_atalho_global

    oculto = "--oculto" in sys.argv
    cfg = config.carregar()
    monitor = Monitor(cfg)
    api = Api(cfg, monitor)
    saindo = threading.Event()

    # Janela sem a barra do Windows: os semáforos e a área de arrastar são
    # desenhados no HTML (só o próprio elemento .pywebview-drag-region arrasta,
    # não os botões dentro dele)
    webview.settings["DRAG_REGION_DIRECT_TARGET_ONLY"] = True
    janela = webview.create_window(
        "Argos", str(UI / "index.html"), js_api=api, width=1080, height=720,
        min_size=(720, 480), hidden=oculto, frameless=True, easy_drag=False, shadow=True,
        background_color="#1c1c1e" if tema_escuro() else "#f5f5f7",
    )
    api._janela = janela
    janela.events.shown += lambda: arredondar_cantos(janela)

    # Com a janela à vista, os avisos aparecem no painel; escondida, no Windows
    visivel = {"sim": not oculto}
    monitor.janela_visivel = lambda: visivel["sim"]
    api._ao_esconder = lambda: visivel.update(sim=False)
    api._ao_mostrar = lambda: visivel.update(sim=True)

    def mostrar():
        janela.show()
        janela.restore()
        visivel["sim"] = True

    def ao_fechar():
        if saindo.is_set():
            return True
        janela.hide()
        visivel["sim"] = False
        return False

    def sair():
        saindo.set()
        bandeja.parar()
        janela.destroy()

    def modo_jogo():
        mostrar()
        janela.evaluate_js("window.abrirModoJogo && window.abrirModoJogo()")

    api._sair = sair
    janela.events.closing += ao_fechar

    bandeja = Bandeja(api, mostrar, modo_jogo, lambda: abrir_pasta(str(config.PASTA_LOGS)), sair)
    monitor.ao_mudar = bandeja.atualizar
    monitor.notificar = bandeja.notificar

    def ao_iniciar():
        if cfg.proxy:
            from argos.app.proxy import Proxy
            monitor.proxy = Proxy(cfg.porta_proxy)
            monitor.proxy.iniciar()
        monitor.iniciar()
        bandeja.iniciar()
        if cfg.atalho and not registrar_atalho_global(cfg.atalho, mostrar):
            logging.warning("atalho %s já está em uso", cfg.atalho)
        threading.Thread(target=_esperar_pedidos, args=(mostrar,), daemon=True).start()

    logging.info("argos-app iniciado")
    # private_mode: sem cache em disco. Com cache, o WebView2 continuava mostrando o
    # app.js/style.css antigos depois de uma atualização.
    webview.start(ao_iniciar, private_mode=True)


if __name__ == "__main__":
    main()
