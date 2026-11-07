"""Docker via o próprio CLI `docker` (sem dependências extras)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import psutil

from argos.plataforma import NOMES_VMMEM, SEM_JANELA, ambiente_externo, listar_processos


def instalado() -> bool:
    return shutil.which("docker") is not None


def _docker(*args: str, timeout: float = 15, cwd: str | None = None) -> subprocess.CompletedProcess:
    # `docker desktop start` abre o Docker Desktop, que fica rodando: não pode herdar o PATH do Argos
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, cwd=cwd, creationflags=SEM_JANELA, env=ambiente_externo(),
    )


def ligado() -> bool:
    if not instalado():
        return False
    try:
        return _docker("info", "--format", "{{.ServerVersion}}", timeout=5).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def _labels(texto: str) -> dict[str, str]:
    saida = {}
    for par in (texto or "").split(","):
        if "=" in par:
            k, v = par.split("=", 1)
            saida[k] = v
    return saida


def containers() -> list[dict]:
    r = _docker("ps", "-a", "--no-trunc", "--format", "{{json .}}")
    if r.returncode != 0:
        return []
    saida = []
    for linha in r.stdout.splitlines():
        try:
            c = json.loads(linha)
        except ValueError:
            continue
        lb = _labels(c.get("Labels", ""))
        portas = sorted({(int(h), int(ct)) for h, ct in re.findall(r":(\d+)->(\d+)", c.get("Ports", ""))})
        saida.append({
            "id": c["ID"][:12],
            "nome": c["Names"],
            "imagem": c["Image"],
            "estado": c["State"],
            "status": c["Status"],
            "portas": portas,
            "projeto": lb.get("com.docker.compose.project", ""),
            "servico": lb.get("com.docker.compose.service", ""),
            "pasta": lb.get("com.docker.compose.project.working_dir", ""),
        })
    saida.sort(key=lambda c: (c["estado"] != "running", c["projeto"], c["nome"]))
    return saida


def _executar(*args: str, timeout: float = 120) -> tuple[bool, str]:
    try:
        r = _docker(*args, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "o Docker demorou demais para responder"
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def parar(ids: list[str]) -> tuple[bool, str]:
    return _executar("stop", *ids)


def iniciar(ids: list[str]) -> tuple[bool, str]:
    return _executar("start", *ids)


def reiniciar(ids: list[str]) -> tuple[bool, str]:
    return _executar("restart", *ids)


def compose_subir(pasta: str, servicos: list[str] | None = None) -> tuple[bool, str]:
    try:
        r = _docker("compose", "up", "-d", *(servicos or []), timeout=600, cwd=pasta)
    except subprocess.TimeoutExpired:
        return False, "docker compose up demorou demais"
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def logs(id_: str, linhas: int = 300) -> str:
    r = _docker("logs", "--tail", str(linhas), "--timestamps", id_)
    return r.stdout + r.stderr


def disco() -> list[dict]:
    r = _docker("system", "df", "--format", "{{json .}}")
    saida = []
    for linha in r.stdout.splitlines():
        try:
            d = json.loads(linha)
        except ValueError:
            continue
        saida.append({
            "tipo": {"Images": "Imagens", "Containers": "Containers", "Local Volumes": "Volumes",
                     "Build Cache": "Cache de build"}.get(d.get("Type"), d.get("Type")),
            "total": d.get("TotalCount"), "ativos": d.get("Active"),
            "tamanho": d.get("Size"), "recuperavel": d.get("Reclaimable"),
        })
    return saida


def limpar(volumes: bool = False) -> tuple[bool, str]:
    """Remove containers parados, imagens sem uso, redes sem uso e cache de build."""
    args = ["system", "prune", "-a", "-f"] + (["--volumes"] if volumes else [])
    ok, texto = _executar(*args, timeout=900)
    m = re.search(r"Total reclaimed space:\s*(.+)", texto)
    return ok, (f"Espaço liberado: {m.group(1)}" if m else texto[-300:])


def desligar_desktop() -> tuple[bool, str]:
    return _executar("desktop", "stop", timeout=180)


def ligar_desktop() -> tuple[bool, str]:
    return _executar("desktop", "start", timeout=240)


def desligar_wsl() -> tuple[bool, str]:
    r = subprocess.run(["wsl", "--shutdown"], capture_output=True, creationflags=SEM_JANELA, timeout=120)
    return r.returncode == 0, ""


def vmmem_mb() -> int | None:
    """RAM usada pela VM do WSL (onde o Docker Desktop roda). None = não está rodando."""
    total, achou = 0, False
    for pid, _, nome in listar_processos():
        if nome.lower().removesuffix(".exe") in NOMES_VMMEM:
            achou = True
            try:
                total += psutil.Process(pid).memory_info().rss
            except psutil.Error:
                pass
    return round(total / 2**20) if achou else None
