"""Atualização do próprio Argos entre máquinas.

O `empacotar\\gerar_zip.ps1` gera dist\\argos-<versão>.zip. Como essa pasta está no
OneDrive, as outras máquinas enxergam o zip novo; o app avisa e instala com um clique.
"""

from __future__ import annotations

import re
import subprocess
import zipfile
from pathlib import Path

from argos import __version__
from argos.config import PASTA_DADOS, Config


def _versao(texto: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", texto)[:3])


def pasta_canal(cfg: Config) -> Path:
    if cfg.pasta_atualizacao:
        return Path(cfg.pasta_atualizacao)
    return Path(cfg.pastas_projetos[0] if cfg.pastas_projetos else ".") / "argos" / "dist"


def disponivel(cfg: Config) -> dict | None:
    """Zip com versão maior que a instalada, se houver."""
    melhor = None
    for z in pasta_canal(cfg).glob("argos-*.zip"):
        m = re.match(r"argos-(\d+\.\d+\.\d+)\.zip$", z.name)
        if m and _versao(m.group(1)) > _versao(__version__):
            if not melhor or _versao(m.group(1)) > _versao(melhor["versao"]):
                melhor = {"versao": m.group(1), "zip": str(z), "atual": __version__}
    return melhor


def aplicar(zip_: str) -> tuple[bool, str]:
    """Extrai o zip e roda o instalador dele (que fecha e reabre o app)."""
    destino = PASTA_DADOS / "atualizacao"
    try:
        import shutil

        shutil.rmtree(destino, ignore_errors=True)
        with zipfile.ZipFile(zip_) as z:
            z.extractall(destino)
    except (OSError, zipfile.BadZipFile) as e:
        return False, f"Não consegui abrir o zip: {e}"
    instalador = next(destino.rglob("instalar.ps1"), None)
    if not instalador:
        return False, "O zip não tem instalar.ps1."
    subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(instalador)],
                     creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
    return True, "Atualizando… o Argos vai fechar e abrir de novo."
