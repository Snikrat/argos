"""Arquivos JSON de dados: leitura tolerante, escrita atômica e trava entre processos.

O CLI, o app e o servidor MCP são processos diferentes mexendo nos mesmos arquivos.
Quem lê, altera e grava precisa segurar a trava, senão uma escrita apaga a outra.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
from pathlib import Path

TRAVA_VELHA = 10     # segundos: trava mais antiga que isso é de um processo que morreu
ESPERA_MAXIMA = 20   # segundos tentando pegar a trava antes de desistir


class TravaOcupada(RuntimeError):
    """Outro processo segurou a trava por tempo demais."""


@contextlib.contextmanager
def trava(caminho: Path):
    """Trava de `caminho` (arquivo .lock ao lado). Levanta TravaOcupada em vez de seguir sem ela."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    arq = caminho.with_suffix(".lock")
    limite = time.time() + ESPERA_MAXIMA
    while True:
        try:
            fd = os.open(arq, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                if time.time() - arq.stat().st_mtime > TRAVA_VELHA:
                    arq.unlink()
                    continue
            except OSError:
                pass
        except PermissionError:
            pass  # o Windows nega por um instante enquanto outro processo apaga a trava
        if time.time() > limite:
            raise TravaOcupada(f"{caminho.name} está em uso por outro processo do Argos.")
        time.sleep(0.03)
    try:
        yield
    finally:
        os.close(fd)
        with contextlib.suppress(OSError):
            arq.unlink()


def ler(caminho: Path, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def gravar(caminho: Path, dados, indent: int | None = 1) -> None:
    """Grava num temporário e troca de uma vez: quem lê nunca vê o arquivo pela metade."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=indent), encoding="utf-8")
    for tentativa in range(20):
        try:
            os.replace(tmp, caminho)
            return
        except PermissionError:
            # Antivírus ou outro leitor com o arquivo aberto por um instante
            if tentativa == 19:
                raise
            time.sleep(0.02)
