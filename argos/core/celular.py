"""Abrir um servidor local no celular: endereço na rede e QR code."""

from __future__ import annotations

import socket

import segno

from argos.config import Config
from argos.core.coleta import Fotografia

# Como fazer cada ferramenta aceitar conexões da rede (e não só deste PC)
DICAS_HOST = [
    ("vite", "rode com --host, ex: npm run dev -- --host"),
    ("next", "rode com -H 0.0.0.0, ex: next dev -H 0.0.0.0"),
    ("uvicorn", "rode com --host 0.0.0.0"),
    ("runserver", "use runserver 0.0.0.0:8000"),
    ("flask", "use flask run --host 0.0.0.0"),
    ("http.server", "use --bind 0.0.0.0"),
]


def ip_local() -> str | None:
    """IP desta máquina na rede local. Nenhum pacote é enviado (UDP só escolhe a rota)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.254.254.254", 1))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def qr_svg(texto: str) -> str:
    # Só viewBox (o tamanho vem do CSS) e bordas nítidas: links longos geram QRs maiores,
    # e reduzir com antialiasing borra os módulos a ponto de a câmera não ler
    svg = segno.make(texto, error="m").svg_inline(scale=1, border=4, dark="#000", light="#fff", omitsize=True)
    return svg.replace("<svg ", '<svg shape-rendering="crispEdges" ', 1)


def qr_terminal(texto: str) -> None:
    segno.make(texto, error="m").terminal(compact=True)


def info(cfg: Config, porta: int, foto: Fotografia | None = None) -> dict:
    foto = foto or Fotografia(cfg)
    pids = foto.porta_pids.get(porta)
    ip = ip_local()
    if not pids:
        return {"ok": False, "msg": f"Nada está usando a porta {porta}."}
    if not ip:
        return {"ok": False, "msg": "Este PC não parece estar conectado a uma rede."}

    so_local = all(e in ("127.0.0.1", "::1") for e in foto.porta_ips[porta])
    dica = ""
    if so_local:
        pid = next(iter(pids))
        cmd = (foto.cmdline(pid) + " " + foto.cmdline(foto.raiz(pid))).lower()
        dica = next((d for chave, d in DICAS_HOST if chave in cmd),
                    "configure o servidor para escutar em 0.0.0.0")
    url = f"http://{ip}:{porta}"
    return {"ok": True, "url": url, "ip": ip, "porta": porta, "so_local": so_local, "dica": dica,
            "svg": qr_svg(url)}
