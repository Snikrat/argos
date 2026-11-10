"""Atualização do próprio Argos.

Dois canais:
- Releases do GitHub: o zip publicado na release mais recente. O hash SHA-256 informado
  pelo GitHub é conferido depois do download.
- Uma pasta (por padrão, `dist` do projeto): útil para quem gera o zip numa máquina e
  sincroniza a pasta com as outras. Se houver um `argos-<versão>.zip.sha256` ao lado,
  ele também é conferido.
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

NOME_ZIP = re.compile(r"argos-(\d+\.\d+\.\d+)\.zip$")
TAMANHO_MAXIMO = 300 * 2**20


def _versao(texto: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", texto)[:3])


def pasta_canal(cfg: Config) -> Path:
    if cfg.pasta_atualizacao:
        return Path(cfg.pasta_atualizacao)
    return Path(cfg.pastas_projetos[0] if cfg.pastas_projetos else ".") / "argos" / "dist"


def _da_pasta(cfg: Config) -> dict | None:
    melhor = None
    try:
        zips = list(pasta_canal(cfg).glob("argos-*.zip"))
    except OSError:
        return None
    for z in zips:
        m = NOME_ZIP.match(z.name)
        if m and (not melhor or _versao(m.group(1)) > _versao(melhor["versao"])):
            melhor = {"versao": m.group(1), "zip": str(z), "origem": "pasta"}
    return melhor


def _do_github(cfg: Config, timeout: float = 8) -> dict | None:
    """Zip da release mais recente do repositório configurado (None sem rede ou sem release)."""
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
    for a in dados.get("assets", []):
        m = NOME_ZIP.match(a.get("name", ""))
        url = a.get("browser_download_url", "")
        # Só o endereço de download da própria release desse repositório
        if m and url.startswith(f"https://github.com/{repo}/releases/download/"):
            return {"versao": m.group(1), "url": url, "origem": "github", "tamanho": a.get("size", 0),
                    "sha256": (a.get("digest") or "").removeprefix("sha256:").lower()}
    return None


def disponivel(cfg: Config) -> dict | None:
    """Versão maior que a instalada, da pasta ou do GitHub (a maior das duas)."""
    candidatas = [c for c in (_da_pasta(cfg), _do_github(cfg)) if c and _versao(c["versao"]) > _versao(__version__)]
    if not candidatas:
        return None
    return {**max(candidatas, key=lambda c: (_versao(c["versao"]), c["origem"] == "pasta")), "atual": __version__}


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
    zip_ = destino / f"argos-{nova['versao']}.zip"
    try:
        pedido = urllib.request.Request(nova["url"], headers={"User-Agent": "argos"})
        with urllib.request.urlopen(pedido, timeout=60) as r, open(zip_, "wb") as f:
            total = 0
            for bloco in iter(lambda: r.read(2**20), b""):
                total += len(bloco)
                if total > TAMANHO_MAXIMO:
                    return None, "O download passou do tamanho esperado."
                f.write(bloco)
    except (OSError, urllib.error.URLError) as e:
        return None, f"Não consegui baixar a atualização: {e}"
    if _sha256(zip_) != nova["sha256"]:
        zip_.unlink(missing_ok=True)
        return None, "O arquivo baixado não confere com o hash publicado. Atualização cancelada."
    return zip_, ""


def aplicar(nova: dict | str) -> tuple[bool, str]:
    """Confere o zip, extrai e roda o instalador dele (que fecha e reabre o app)."""
    if isinstance(nova, str):
        nova = {"zip": nova, "origem": "pasta", "versao": ""}
    destino = PASTA_DADOS / "atualizacao"
    shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir(parents=True, exist_ok=True)
    if nova.get("origem") == "github":
        zip_, erro = _baixar(nova, destino)
        if not zip_:
            return False, erro
    else:
        zip_ = Path(nova["zip"])
        lado = zip_.with_name(zip_.name + ".sha256")
        try:
            esperado = lado.read_text(encoding="utf-8").split()[0].lower() if lado.is_file() else ""
        except (OSError, IndexError):
            esperado = ""
        if esperado and _sha256(zip_) != esperado:
            return False, f"{zip_.name} não confere com o {lado.name}. Atualização cancelada."
    try:
        with zipfile.ZipFile(zip_) as z:
            z.extractall(destino / "pacote")
    except (OSError, zipfile.BadZipFile) as e:
        return False, f"Não consegui abrir o zip: {e}"
    instalador = next((destino / "pacote").rglob("instalar.ps1"), None)
    if not instalador:
        return False, "O zip não tem instalar.ps1."
    subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(instalador)],
                     creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
    return True, "Atualizando… o Argos vai fechar e abrir de novo."
