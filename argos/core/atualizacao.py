"""Atualização do próprio Argos.

Dois canais:
- Releases do GitHub: o instalador publicado na release mais recente. O hash SHA-256
  informado pelo GitHub é conferido depois do download.
- Uma pasta (por padrão, `dist` do projeto): útil para quem gera o instalador numa máquina
  e sincroniza a pasta com as outras. Se houver um `<arquivo>.sha256` ao lado, ele é conferido.

O pacote é o instalador (`Argos-Setup-<versão>.exe`), executado em modo silencioso: ele
fecha o app, troca os arquivos e abre de novo. Zips antigos (`argos-<versão>.zip`, com
um `instalar.ps1` dentro) continuam aceitos.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from argos import __version__
from argos.config import PASTA_DADOS, Config

NOME_SETUP = re.compile(r"Argos-Setup-(\d+\.\d+\.\d+)\.exe$", re.I)
NOME_ZIP = re.compile(r"argos-(\d+\.\d+\.\d+)\.zip$")
TAMANHO_MAXIMO = 300 * 2**20
SILENCIOSO = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]


def _versao(texto: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", texto)[:3])


def _pacote(nome: str) -> tuple[str, str] | None:
    """(versão, tipo) se `nome` é um pacote do Argos."""
    for padrao, tipo in ((NOME_SETUP, "setup"), (NOME_ZIP, "zip")):
        m = padrao.match(nome)
        if m:
            return m.group(1), tipo
    return None


def _ordem(c: dict) -> tuple:
    # Versão maior; na mesma versão, o instalador antes do zip e a pasta antes do download
    return _versao(c["versao"]), c["tipo"] == "setup", c["origem"] == "pasta"


def pasta_canal(cfg: Config) -> Path:
    if cfg.pasta_atualizacao:
        return Path(cfg.pasta_atualizacao)
    return Path(cfg.pastas_projetos[0] if cfg.pastas_projetos else ".") / "argos" / "dist"


def _da_pasta(cfg: Config) -> dict | None:
    try:
        arquivos = [f for f in pasta_canal(cfg).iterdir() if f.is_file()]
    except OSError:
        return None
    candidatas = []
    for f in arquivos:
        p = _pacote(f.name)
        if p:
            candidatas.append({"versao": p[0], "tipo": p[1], "arquivo": str(f), "nome": f.name, "origem": "pasta"})
    return max(candidatas, key=_ordem) if candidatas else None


def _do_github(cfg: Config, timeout: float = 8) -> dict | None:
    """Pacote da release mais recente do repositório configurado (None sem rede ou sem release)."""
    repo = cfg.repo_atualizacao.strip().strip("/")
    if not cfg.procurar_atualizacao or not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        return None
    pedido = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest",
                                    headers={"User-Agent": "argos", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as r:
            dados = json.loads(r.read(2 * 2**20))
    except (OSError, ValueError, urllib.error.URLError):
        return None
    candidatas = []
    for a in dados.get("assets", []):
        p = _pacote(a.get("name", ""))
        url = a.get("browser_download_url", "")
        # Só o endereço de download da própria release desse repositório
        if p and url.startswith(f"https://github.com/{repo}/releases/download/"):
            candidatas.append({"versao": p[0], "tipo": p[1], "url": url, "nome": a["name"], "origem": "github",
                               "tamanho": a.get("size", 0),
                               "sha256": (a.get("digest") or "").removeprefix("sha256:").lower()})
    return max(candidatas, key=_ordem) if candidatas else None


def disponivel(cfg: Config) -> dict | None:
    """Versão maior que a instalada, da pasta ou do GitHub (a maior das duas)."""
    candidatas = [c for c in (_da_pasta(cfg), _do_github(cfg)) if c and _versao(c["versao"]) > _versao(__version__)]
    if not candidatas:
        return None
    return {**max(candidatas, key=_ordem), "atual": __version__}


def _sha256(arquivo: Path) -> str:
    h = hashlib.sha256()
    with open(arquivo, "rb") as f:
        for bloco in iter(lambda: f.read(2**20), b""):
            h.update(bloco)
    return h.hexdigest()


def _baixar(nova: dict, destino: Path) -> tuple[Path | None, str]:
    if not nova.get("sha256"):
        return None, "O GitHub não informou o hash desse arquivo, então não dá para conferir o download."
    if nova.get("tamanho", 0) > TAMANHO_MAXIMO:
        return None, "O arquivo da release é grande demais para ser o Argos."
    arquivo = destino / nova["nome"]
    try:
        pedido = urllib.request.Request(nova["url"], headers={"User-Agent": "argos"})
        with urllib.request.urlopen(pedido, timeout=60) as r, open(arquivo, "wb") as f:
            total = 0
            for bloco in iter(lambda: r.read(2**20), b""):
                total += len(bloco)
                if total > TAMANHO_MAXIMO:
                    return None, "O download passou do tamanho esperado."
                f.write(bloco)
    except (OSError, urllib.error.URLError) as e:
        return None, f"Não consegui baixar a atualização: {e}"
    if _sha256(arquivo) != nova["sha256"]:
        arquivo.unlink(missing_ok=True)
        return None, "O arquivo baixado não confere com o hash publicado. Atualização cancelada."
    return arquivo, ""


def _da_pasta_conferido(nova: dict, destino: Path) -> tuple[Path | None, str]:
    """Copia o pacote da pasta para fora dela (pode estar sincronizando) e confere o .sha256, se houver."""
    origem = Path(nova["arquivo"])
    lado = origem.with_name(origem.name + ".sha256")
    try:
        esperado = lado.read_text(encoding="utf-8").split()[0].lower() if lado.is_file() else ""
        arquivo = Path(shutil.copy2(origem, destino / origem.name))
    except (OSError, IndexError) as e:
        return None, f"Não consegui ler {origem.name}: {e}"
    if esperado and _sha256(arquivo) != esperado:
        arquivo.unlink(missing_ok=True)
        return None, f"{origem.name} não confere com o {lado.name}. Atualização cancelada."
    return arquivo, ""


def preparar(nova: dict) -> tuple[list[str] | None, str]:
    """Baixa/copia e confere o pacote. Devolve o comando que instala (ou None e o motivo)."""
    destino = PASTA_DADOS / "atualizacao"
    shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir(parents=True, exist_ok=True)
    arquivo, erro = (_baixar if nova.get("origem") == "github" else _da_pasta_conferido)(nova, destino)
    if not arquivo:
        return None, erro
    if nova["tipo"] == "setup":
        return [str(arquivo), *SILENCIOSO], ""
    # Zip de versões antigas: traz o próprio instalador em PowerShell
    try:
        with zipfile.ZipFile(arquivo) as z:
            z.extractall(destino / "pacote")
    except (OSError, zipfile.BadZipFile) as e:
        return None, f"Não consegui abrir o zip: {e}"
    instalador = next((destino / "pacote").rglob("instalar.ps1"), None)
    if not instalador:
        return None, "Esse zip é a versão portátil (sem instalador). Baixe o Argos-Setup da mesma versão."
    return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(instalador)], ""


def aplicar(nova: dict) -> tuple[bool, str]:
    """Confere o pacote e roda o instalador, que fecha e reabre o app."""
    comando, erro = preparar(nova)
    if not comando:
        return False, erro
    subprocess.Popen(comando, creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS, close_fds=True)
    return True, "Atualizando… o Argos vai fechar e abrir de novo."
