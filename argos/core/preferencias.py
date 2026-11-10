"""Preferências por projeto: comando fixado, último usado e comandos personalizados recentes.

Ficam em %LOCALAPPDATA%\\argos\\preferencias.json e decidem qual comando vira o
botão principal: o fixado; senão o último usado; senão a ordem detectada.
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path

from argos.config import PASTA_DADOS
from argos.core import arquivo

ARQUIVO = PASTA_DADOS / "preferencias.json"
MAX_RECENTES = 5


def _ler() -> dict:
    return arquivo.ler(ARQUIVO, {})


def _gravar(dados: dict) -> None:
    arquivo.gravar(ARQUIVO, dados)


@contextlib.contextmanager
def _editar():
    """Ler, alterar e gravar com a trava: o CLI, o app e o MCP mexem no mesmo arquivo."""
    with arquivo.trava(ARQUIVO):
        dados = _ler()
        yield dados
        _gravar(dados)


def _do_projeto(dados: dict, projeto: str) -> dict:
    return dados.setdefault(projeto.lower(), {"fixo": None, "ultimo": None, "recentes": []})


def registrar_uso(projeto: str, chave: str) -> None:
    with _editar() as dados:
        p = _do_projeto(dados, projeto)
        p["ultimo"], p["ultimo_em"] = chave, time.time()


def fixar(projeto: str, chave: str | None) -> None:
    with _editar() as dados:
        _do_projeto(dados, projeto)["fixo"] = chave


def adicionar_recente(projeto: str, cmd: str, pasta: str, sub: str = "") -> str:
    """Guarda um comando digitado à mão para aparecer na lista depois. Devolve a chave."""
    with _editar() as dados:
        p = _do_projeto(dados, projeto)
        novo = {"cmd": cmd, "pasta": pasta, "sub": sub}
        p["recentes"] = [novo] + [r for r in p.get("recentes", []) if (r["cmd"], r.get("sub", "")) != (cmd, sub)]
        p["recentes"] = p["recentes"][:MAX_RECENTES]
    return f"{sub or '.'}|{cmd}"


def esquecer_recente(projeto: str, chave: str) -> None:
    with _editar() as dados:
        p = _do_projeto(dados, projeto)
        p["recentes"] = [r for r in p.get("recentes", []) if f"{r.get('sub') or '.'}|{r['cmd']}" != chave]
        if p.get("fixo") == chave:
            p["fixo"] = None


# --- comandos detectados que o usuário apagou da lista -----------------------
# Ficam só escondidos: a detecção continua achando, e "restaurar" traz de volta.

def ocultar(projeto: str, chave: str) -> None:
    with _editar() as dados:
        p = _do_projeto(dados, projeto)
        if chave not in p.setdefault("ocultos", []):
            p["ocultos"].append(chave)
        if p.get("fixo") == chave:
            p["fixo"] = None


def restaurar(projeto: str, chave: str | None = None) -> None:
    """Traz de volta um comando escondido, ou todos (chave=None)."""
    with _editar() as dados:
        p = _do_projeto(dados, projeto)
        p["ocultos"] = [] if chave is None else [c for c in p.get("ocultos", []) if c != chave]


# --- arquivo .env usado ao iniciar ---------------------------------------------

def arquivo_env(projeto: str, sub: str = "") -> str | None:
    """Nome do arquivo .env escolhido para a pasta (None = o que o projeto carrega sozinho)."""
    return _ler().get(projeto.lower(), {}).get("env", {}).get(sub or ".")


def definir_arquivo_env(projeto: str, sub: str, nome: str | None) -> None:
    with _editar() as dados:
        escolhas = _do_projeto(dados, projeto).setdefault("env", {})
        if nome:
            escolhas[sub or "."] = nome
        else:
            escolhas.pop(sub or ".", None)


# --- portas fixas -----------------------------------------------------------

def _chave_porta(projeto: str, chave: str) -> str:
    return f"{projeto.lower()}|{chave}"


def porta_reservada(projeto: str, chave: str) -> int | None:
    return _ler().get("_portas", {}).get(_chave_porta(projeto, chave))


def portas_reservadas() -> dict[str, int]:
    return dict(_ler().get("_portas", {}))


def reservar_porta(projeto: str, chave: str, porta: int | None) -> None:
    with _editar() as dados:
        portas = dados.setdefault("_portas", {})
        if porta:
            portas[_chave_porta(projeto, chave)] = int(porta)
        else:
            portas.pop(_chave_porta(projeto, chave), None)


def aplicar(projeto: dict) -> None:
    """Acrescenta os recentes, mostra as portas fixas e põe o comando preferido em primeiro lugar."""
    dados = _ler()
    p = dados.get(projeto["nome"].lower(), {})
    portas = dados.get("_portas", {})
    ocultos = set(p.get("ocultos", []))
    projeto["ocultos"] = [{"chave": c["chave"], "rotulo": c["rotulo"], "sub": c.get("sub", "")}
                          for c in projeto["comandos"] if c["chave"] in ocultos]
    projeto["comandos"] = [c for c in projeto["comandos"] if c["chave"] not in ocultos]
    for c in projeto["comandos"]:
        fixa = portas.get(_chave_porta(projeto["nome"], c["chave"]))
        if fixa:
            c["porta"], c["porta_fixa"] = fixa, True
    existentes = {c["chave"] for c in projeto["comandos"]}
    for r in p.get("recentes", []):
        chave = f"{r.get('sub') or '.'}|{r['cmd']}"
        if chave in existentes or not Path(r["pasta"]).is_dir():
            continue
        projeto["comandos"].append({
            "rotulo": r["cmd"], "cmd": r["cmd"], "tipo": "processo", "porta": None, "detalhe": "usado antes",
            "pasta": r["pasta"], "sub": r.get("sub", ""), "chave": chave, "recente": True,
        })
        existentes.add(chave)

    fixo = p.get("fixo") if p.get("fixo") in existentes else None
    projeto["fixo"] = fixo
    preferido = fixo or (p.get("ultimo") if p.get("ultimo") in existentes else None)
    if preferido:
        projeto["comandos"].sort(key=lambda c: c["chave"] != preferido)
