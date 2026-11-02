"""Link público temporário para um servidor local (Cloudflare Quick Tunnel).

Gera um endereço https://algo.trycloudflare.com que funciona de qualquer lugar
enquanto o túnel estiver aberto. Não precisa de conta na Cloudflare.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from argos.core import registro
from argos.plataforma import SEM_JANELA

URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
PREFIXO = "túnel :"


def cloudflared() -> str | None:
    if c := shutil.which("cloudflared"):
        return c
    for p in (Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "cloudflared.exe",
              Path(os.environ.get("ProgramFiles(x86)", "")) / "cloudflared" / "cloudflared.exe",
              Path(os.environ.get("ProgramFiles", "")) / "cloudflared" / "cloudflared.exe"):
        if p.is_file():
            return str(p)
    return None


def instalar() -> tuple[bool, str]:
    """Instala o cloudflared pelo winget (pacote oficial da Cloudflare)."""
    if not shutil.which("winget"):
        return False, "winget não encontrado. Baixe o cloudflared em developers.cloudflare.com."
    try:
        r = subprocess.run(["winget", "install", "--id", "Cloudflare.cloudflared", "-e", "--silent",
                            "--accept-package-agreements", "--accept-source-agreements"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=600, creationflags=SEM_JANELA)
    except subprocess.TimeoutExpired:
        return False, "A instalação demorou demais."
    ok = cloudflared() is not None
    return ok, "cloudflared instalado." if ok else (r.stdout + r.stderr)[-300:]


def _url_do_log(e: dict) -> str | None:
    try:
        m = URL.search(Path(e["log"]).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    return m.group(0) if m else None


def ativos() -> list[dict]:
    """Túneis abertos agora: porta local e endereço público."""
    saida = []
    for e in registro.listar():
        if e["vivo"] and e["nome"].startswith(PREFIXO):
            saida.append({"id": e["id"], "pid": e["pid"], "porta": int(e["nome"][len(PREFIXO):]),
                          "url": _url_do_log(e), "projeto": e.get("projeto", "")})
    return saida


def abrir(porta: int, host_local: str = "127.0.0.1", projeto: str = "", espera: float = 40) -> dict:
    existente = next((t for t in ativos() if t["porta"] == porta and t["url"]), None)
    if existente:
        return {"ok": True, **existente}
    exe = cloudflared()
    if not exe:
        return {"ok": False, "falta_cloudflared": True,
                "msg": "Para criar um link público é preciso o cloudflared (gratuito, da Cloudflare)."}
    origem = f"http://[::1]:{porta}" if host_local == "::1" else f"http://127.0.0.1:{porta}"
    # Host "localhost:porta" para o servidor (Vite e cia. recusam hosts desconhecidos)
    cmd = subprocess.list2cmdline([exe, "tunnel", "--no-autoupdate", "--url", origem,
                                   "--http-host-header", f"localhost:{porta}"])
    entrada, _ = registro.iniciar(cmd, str(Path.home()), dict(os.environ), shell=False,
                                  nome=f"{PREFIXO}{porta}", projeto=projeto)
    limite = time.time() + espera
    while time.time() < limite:
        url = _url_do_log(entrada)
        if url:
            return {"ok": True, "id": entrada["id"], "pid": entrada["pid"], "porta": porta, "url": url}
        if not registro.vivo(entrada):
            return {"ok": False, "id": entrada["id"], "msg": "O cloudflared fechou. Veja os logs."}
        time.sleep(0.5)
    return {"ok": False, "id": entrada["id"], "msg": "O túnel não respondeu a tempo. Veja os logs."}
