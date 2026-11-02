"""Configuração e caminhos de dados (%LOCALAPPDATA%\\argos)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

PASTA_DADOS = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "argos"
PASTA_LOGS = PASTA_DADOS / "logs"
ARQUIVO_CONFIG = PASTA_DADOS / "config.json"
ARQUIVO_REGISTRO = PASTA_DADOS / "registro.json"
ARQUIVO_HISTORICO = PASTA_DADOS / "historico.jsonl"


def _pasta_projetos_padrao() -> str:
    from argos.plataforma import pasta_area_de_trabalho

    return str(Path(pasta_area_de_trabalho()) / "projetos")


@dataclass
class Config:
    # Pastas cujas subpastas são consideradas projetos
    pastas_projetos: list[str] = field(default_factory=lambda: [_pasta_projetos_padrao()])
    # Segundos entre atualizações do painel
    intervalo: int = 3
    # Avisar quando algo estiver rodando há mais de N horas (0 desliga)
    alerta_horas: float = 4
    # Avisar quando surgir processo órfão
    alerta_orfaos: bool = True
    # Atalho global para abrir o painel
    atalho: str = "ctrl+alt+d"
    # Processos donos de porta que nunca aparecem (além da lista interna)
    ignorar: list[str] = field(default_factory=list)
    # Cada comando ganha uma porta própria e estável (ex: agendamento sempre na 5173)
    portas_fixas: bool = True
    # Endereços com nome: http://projeto.localhost (proxy local do app)
    proxy: bool = True
    porta_proxy: int = 80
    # Avisar quando um servidor fica sem nenhuma conexão por N horas (0 desliga)
    ocioso_horas: float = 3
    # Buscar novidades do Git (git fetch) a cada N minutos (0 desliga)
    git_fetch_minutos: int = 15
    # Pasta onde procurar versões novas do Argos (vazio = projetos\argos\dist)
    pasta_atualizacao: str = ""


# Antes de virar Argos o app se chamava "devs" e guardava tudo em %LOCALAPPDATA%\devs
PASTA_ANTIGA = PASTA_DADOS.with_name("devs")
NAO_MIGRAR = {"app", "build", "venv-dev", "webview"}  # o instalador cuida desses


def _caminhos_novos(valor, antigo: str, novo: str):
    """Troca caminhos da pasta antiga pelos da nova, só para arquivos que já foram movidos."""
    if isinstance(valor, dict):
        return {k: _caminhos_novos(v, antigo, novo) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_caminhos_novos(v, antigo, novo) for v in valor]
    if isinstance(valor, str) and valor.lower().startswith(antigo.lower()):
        trocado = novo + valor[len(antigo):]
        if Path(trocado).exists() and not Path(valor).exists():
            return trocado
    return valor


def migrar_pasta_antiga() -> None:
    """Traz config, registro, preferências, sessões e logs da pasta do devs (uma vez só)."""
    if not PASTA_ANTIGA.is_dir() or ARQUIVO_CONFIG.exists():
        return
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    for item in PASTA_ANTIGA.iterdir():
        if item.name in NAO_MIGRAR:
            continue
        destino = PASTA_DADOS / item.name
        # Arquivo a arquivo: logs de processos ainda rodando ficam presos e continuam na pasta antiga
        arquivos = [item] if item.is_file() else [f for f in item.rglob("*") if f.is_file()]
        for f in arquivos:
            alvo = destino / f.relative_to(item) if item.is_dir() else destino
            if alvo.exists():
                continue
            try:
                alvo.parent.mkdir(parents=True, exist_ok=True)
                os.replace(f, alvo)
            except OSError:
                pass
    for arq in PASTA_DADOS.glob("*.json"):
        try:
            dados = json.loads(arq.read_text(encoding="utf-8"))
            novo = _caminhos_novos(dados, str(PASTA_ANTIGA), str(PASTA_DADOS))
            if novo != dados:
                arq.write_text(json.dumps(novo, ensure_ascii=False, indent=1), encoding="utf-8")
        except (OSError, ValueError):
            pass


def carregar() -> Config:
    try:
        migrar_pasta_antiga()
    except OSError:
        pass
    cfg = Config()
    try:
        dados = json.loads(ARQUIVO_CONFIG.read_text(encoding="utf-8"))
        for k, v in dados.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
    except FileNotFoundError:
        salvar(cfg)
    except (OSError, ValueError):
        pass
    return cfg


def salvar(cfg: Config) -> None:
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    ARQUIVO_CONFIG.write_text(json.dumps(asdict(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
