"""Implementação Windows das operações dependentes do sistema."""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import threading
import time
import winreg
from ctypes import wintypes
from pathlib import Path
from typing import Callable

import psutil

__all__ = [
    "listar_processos", "pasta_area_de_trabalho", "flags_processo", "encerrar_arvore", "executar_como_admin",
    "habilitar_cores_terminal", "comando_proprio", "abrir_pasta", "abrir_url", "abrir_vscode",
    "abrir_terminal", "registrar_atalho_global", "copiar_texto", "pasta_inicializacao", "SEM_JANELA",
    "NOMES_VMMEM", "ambiente_externo", "proteger", "desproteger", "interromper_console",
]

SEM_JANELA = subprocess.CREATE_NO_WINDOW
CREATE_BREAKAWAY_FROM_JOB = 0x01000000

# Processo da VM do WSL (onde o Docker Desktop roda)
NOMES_VMMEM = ("vmmem", "vmmemwsl")


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260),
    ]


def listar_processos() -> list[tuple[int, int, str]]:
    """(pid, ppid, nome) de todos os processos numa única leitura.

    O psutil faz uma varredura completa para cada `ppid()`, o que custa segundos
    quando há centenas de processos.
    """
    k32 = ctypes.windll.kernel32
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if snap in (None, wintypes.HANDLE(-1).value):
        return [(p.pid, p.ppid(), p.name()) for p in psutil.process_iter()]
    saida = []
    try:
        e = _PROCESSENTRY32W()
        e.dwSize = ctypes.sizeof(e)
        ok = k32.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            saida.append((e.th32ProcessID, e.th32ParentProcessID, e.szExeFile))
            ok = k32.Process32NextW(snap, ctypes.byref(e))
    finally:
        k32.CloseHandle(snap)
    return saida


def pasta_area_de_trabalho() -> str:
    """Área de Trabalho real (respeita redirecionamento do OneDrive)."""
    try:
        chave = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        )
        valor, _ = winreg.QueryValueEx(chave, "Desktop")
        return os.path.expandvars(valor)
    except OSError:
        return str(Path.home() / "Desktop")


def flags_processo(junto: bool = False) -> int:
    """Flags para iniciar um processo gerenciado.

    Por padrão o processo ganha um console próprio e invisível, então fechar o
    terminal que o iniciou não o derruba. Com `junto=True` ele fica preso ao
    terminal atual, como um comando normal.
    """
    if junto:
        return 0
    return SEM_JANELA | subprocess.CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB


def interromper_console(pid: int) -> None:
    """Manda Ctrl+Break a todos os processos do console de `pid`.

    Só funciona de dentro de um processo descartável (`argos _interromper`): é preciso
    largar o próprio console e entrar no do alvo, e o sinal atinge também quem o envia.
    """
    k32 = ctypes.windll.kernel32
    k32.FreeConsole()
    if not k32.AttachConsole(wintypes.DWORD(pid)):
        raise OSError(f"não consegui entrar no console do processo {pid}")
    k32.GenerateConsoleCtrlEvent(1, 0)  # CTRL_BREAK_EVENT para o console inteiro
    time.sleep(0.3)


def encerrar_arvore(pid: int, gentil: bool = False, espera: float = 4) -> tuple[bool, bool]:
    """Encerra o processo e todos os descendentes. Retorna (ok, acesso_negado).

    Com `gentil`, primeiro manda Ctrl+Break e espera o servidor fechar sozinho (salvar
    arquivos, soltar conexões); o que sobrar depois de `espera` segundos é encerrado à
    força. Só deve ser usado em processos com console próprio (os iniciados pelo Argos):
    num terminal compartilhado o sinal atingiria também o shell do usuário.
    """
    try:
        raiz = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return True, False
    try:
        filhos = raiz.children(recursive=True)
    except psutil.Error:
        filhos = []
    if gentil:
        try:
            subprocess.run(comando_proprio() + ["_interromper", str(pid)], capture_output=True,
                           creationflags=SEM_JANELA, timeout=5)
            psutil.wait_procs([raiz, *filhos], timeout=espera)
        except (OSError, subprocess.SubprocessError):
            pass
    negado = False
    for p in [raiz, *filhos]:
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            negado = True
    _, vivos = psutil.wait_procs([raiz, *filhos], timeout=5)
    return not vivos, negado


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(nome: str, dados: bytes) -> bytes:
    funcao = getattr(ctypes.windll.crypt32, nome)
    buf = ctypes.create_string_buffer(dados, len(dados))
    entrada = _Blob(len(dados), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    saida = _Blob()
    if not funcao(ctypes.byref(entrada), None, None, None, None, 0, ctypes.byref(saida)):
        raise OSError(f"{nome} falhou")
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        liberar = ctypes.windll.kernel32.LocalFree
        liberar.argtypes = [ctypes.c_void_p]
        liberar(ctypes.cast(saida.pbData, ctypes.c_void_p))


def proteger(dados: bytes) -> bytes:
    """Cifra com a DPAPI do Windows: só o mesmo usuário, nesta máquina, consegue abrir."""
    return _dpapi("CryptProtectData", dados)


def desproteger(dados: bytes) -> bytes:
    return _dpapi("CryptUnprotectData", dados)


def comando_proprio() -> list[str]:
    """Como chamar o CLI do Argos (exe empacotado ou python -m argos)."""
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).with_name("argos.exe"))]
    python = Path(sys.executable)
    if python.name.lower() == "pythonw.exe":
        python = python.with_name("python.exe")
    return [str(python), "-m", "argos"]


def executar_como_admin(args: list[str]) -> bool:
    """Roda `argos <args>` como administrador (abre a janela do UAC)."""
    cmd = comando_proprio()
    exe, params = cmd[0], subprocess.list2cmdline(cmd[1:] + args)
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    return r > 32


def habilitar_cores_terminal() -> None:
    """Liga o suporte a cores ANSI no console clássico."""
    try:
        k32 = ctypes.windll.kernel32
        h = k32.GetStdHandle(-11)
        modo = wintypes.DWORD()
        if k32.GetConsoleMode(h, ctypes.byref(modo)):
            k32.SetConsoleMode(h, modo.value | 0x0004)
    except OSError:
        pass


def copiar_texto(texto: str) -> bool:
    """Coloca texto na área de transferência (CF_UNICODETEXT)."""
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    k32.GlobalAlloc.restype = wintypes.HGLOBAL
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    # Handles são de 64 bits: sem argtypes o ctypes tenta passar como int de 32 e estoura
    k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    u32.SetClipboardData.restype = wintypes.HANDLE
    dados = texto.encode("utf-16-le") + b"\x00\x00"
    for _ in range(40):  # outro programa pode estar com a área de transferência aberta por um instante
        if u32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        return False
    try:
        u32.EmptyClipboard()
        h = k32.GlobalAlloc(0x0002, len(dados))  # GMEM_MOVEABLE
        p = k32.GlobalLock(h)
        ctypes.memmove(p, dados, len(dados))
        k32.GlobalUnlock(h)
        return bool(u32.SetClipboardData(13, h))  # CF_UNICODETEXT
    finally:
        u32.CloseClipboard()


def abrir_pasta(caminho: str) -> None:
    os.startfile(caminho)


def abrir_url(url: str) -> None:
    os.startfile(url)


def ambiente_externo() -> dict:
    """Variáveis para programas que o Argos abre (VS Code, terminal, Docker, Godot).

    O app empacotado põe as próprias pastas no PATH. Herdando isso, o VS Code chegou a
    carregar DLLs de dentro do Argos e prendê-las, e a atualização não conseguia
    substituir os arquivos.
    """
    from argos.core.registro import _limpar_env

    return _limpar_env(dict(os.environ))


def abrir_vscode(caminho: str) -> bool:
    code = shutil.which("code")
    if not code:
        return False
    subprocess.Popen([code, caminho], creationflags=SEM_JANELA, env=ambiente_externo())
    return True


def abrir_terminal(pasta: str, comando: str | None = None) -> None:
    """Abre o Windows Terminal (ou PowerShell) na pasta, opcionalmente rodando um comando."""
    shell = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
    extra = ["-NoExit", "-Command", comando] if comando else []
    wt = shutil.which("wt")
    if wt:
        subprocess.Popen([wt, "-d", pasta, shell, *extra], env=ambiente_externo())
    else:
        subprocess.Popen([shell, *extra], cwd=pasta, creationflags=subprocess.CREATE_NEW_CONSOLE, env=ambiente_externo())


def pasta_inicializacao() -> Path:
    return Path(os.environ["APPDATA"]) / r"Microsoft\Windows\Start Menu\Programs\Startup"


_MODS = {"ctrl": 0x2, "alt": 0x1, "shift": 0x4, "win": 0x8}


def registrar_atalho_global(atalho: str, callback: Callable[[], None]) -> bool:
    """Registra um atalho global (ex: 'ctrl+alt+d'). Roda numa thread própria."""
    partes = [p.strip().lower() for p in atalho.split("+")]
    mods = 0x4000  # MOD_NOREPEAT
    tecla = None
    for p in partes:
        if p in _MODS:
            mods |= _MODS[p]
        elif len(p) == 1:
            tecla = ord(p.upper())
        elif p.startswith("f") and p[1:].isdigit():
            tecla = 0x6F + int(p[1:])
    if tecla is None:
        return False

    pronto = threading.Event()
    resultado = {"ok": False}

    def laco():
        user32 = ctypes.windll.user32
        resultado["ok"] = bool(user32.RegisterHotKey(None, 1, mods, tecla))
        pronto.set()
        if not resultado["ok"]:
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x0312:  # WM_HOTKEY
                try:
                    callback()
                except Exception:
                    pass

    threading.Thread(target=laco, daemon=True, name="atalho-global").start()
    pronto.wait(2)
    return resultado["ok"]
