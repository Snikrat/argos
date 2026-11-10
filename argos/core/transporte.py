"""Levar a configuração para outra máquina: exportar e importar um arquivo JSON.

Vai: opções, comando fixado, comandos apagados, recentes, portas fixas, arquivo .env
escolhido e os perfis montados a partir de comandos de projetos.
Não vai: variáveis de ambiente (podem ter chaves e tokens), sessões de processos
capturados (dependem de caminhos e do ambiente desta máquina), registro e logs.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from argos import __version__, config
from argos.core import arquivo, preferencias, sessoes

FORMATO = 1
# Opções que fazem sentido em qualquer máquina (pastas de projetos e de atualização ficam de fora)
OPCOES = ("intervalo", "alerta_horas", "alerta_orfaos", "atalho", "ignorar", "portas_fixas", "proxy", "porta_proxy",
          "ocioso_horas", "git_fetch_minutos", "procurar_atualizacao", "limite_ram_mb")


def exportar(cfg: config.Config) -> dict:
    perfis = []
    for s in sessoes._ler():
        comandos = [{"projeto": i["projeto"], "chave": i["chave"], "nome": i["nome"]}
                    for i in s["itens"] if i["tipo"] == "comando"]
        if s.get("nome") and comandos:
            perfis.append({"nome": s["nome"], "comandos": comandos})
    opcoes = {k: v for k, v in asdict(cfg).items() if k in OPCOES}
    return {"argos": __version__, "formato": FORMATO, "quando": time.time(), "opcoes": opcoes,
            "pastas_projetos": cfg.pastas_projetos, "preferencias": arquivo.ler(preferencias.ARQUIVO, {}), "perfis": perfis}


def gravar(cfg: config.Config, caminho: str) -> tuple[bool, str]:
    dados = exportar(cfg)
    try:
        Path(caminho).write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as e:
        return False, f"Não consegui gravar o arquivo: {e}"
    projetos = sum(1 for k in dados["preferencias"] if not k.startswith("_"))  # "_portas" não é projeto
    return True, (f"Configuração exportada: {projetos} projeto(s) com preferências e "
                  f"{len(dados['perfis'])} perfil(is). Variáveis de ambiente não são exportadas.")


def importar(cfg: config.Config, caminho: str) -> tuple[bool, str]:
    """Junta o arquivo ao que já existe: o importado vale sobre o local, o resto fica."""
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return False, f"Não consegui ler o arquivo: {e}"
    if not isinstance(dados, dict) or dados.get("formato") != FORMATO or "preferencias" not in dados:
        return False, "Esse arquivo não é uma configuração exportada pelo Argos."

    for k, v in (dados.get("opcoes") or {}).items():
        if k in OPCOES:
            setattr(cfg, k, config._ajustar(k, v, getattr(cfg, k)))
    # Pastas de projetos: só as que existem nesta máquina, sem tirar as atuais
    novas = [p for p in dados.get("pastas_projetos") or [] if isinstance(p, str) and Path(p).is_dir()
             and p.lower() not in {x.lower() for x in cfg.pastas_projetos}]
    cfg.pastas_projetos += novas
    config.salvar(cfg)

    importadas = dados["preferencias"] if isinstance(dados["preferencias"], dict) else {}
    with preferencias._editar() as locais:
        for projeto, prefs in importadas.items():
            if isinstance(prefs, dict):
                locais[projeto] = {**locais.get(projeto, {}), **prefs}

    perfis = 0
    for p in dados.get("perfis") or []:
        comandos = [c for c in p.get("comandos", []) if isinstance(c, dict) and c.get("projeto") and c.get("chave")]
        if p.get("nome") and comandos:
            sessoes.criar_perfil(str(p["nome"]), comandos)
            perfis += 1
    return True, (f"Importado: preferências de {sum(1 for k in importadas if not k.startswith('_'))} projeto(s), "
                  f"{perfis} perfil(is)" + (f" e {len(novas)} pasta(s) de projetos" if novas else "") + ".")
