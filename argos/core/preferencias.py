"""Preferências por projeto: comando fixado, último usado e comandos personalizados recentes.

Ficam em %LOCALAPPDATA%\\argos\\preferencias.json e decidem qual comando vira o
botão principal: o fixado; senão o último usado; senão a ordem detectada.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from argos.config import PASTA_DADOS

ARQUIVO = PASTA_DADOS / "preferencias.json"
MAX_RECENTES = 5


def _ler() -> dict:
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _gravar(dados: dict) -> None:
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    tmp = ARQUIVO.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ARQUIVO)


def _do_projeto(dados: dict, projeto: str) -> dict:
    return dados.setdefault(projeto.lower(), {"fixo": None, "ultimo": None, "recentes": []})


def registrar_uso(projeto: str, chave: str) -> None:
    dados = _ler()
    p = _do_projeto(dados, projeto)
    p["ultimo"], p["ultimo_em"] = chave, time.time()
    _gravar(dados)


def fixar(projeto: str, chave: str | None) -> None:
    dados = _ler()
    _do_projeto(dados, projeto)["fixo"] = chave
    _gravar(dados)


def adicionar_recente(projeto: str, cmd: str, pasta: str, sub: str = "") -> str:
    """Guarda um comando digitado à mão para aparecer na lista depois. Devolve a chave."""
    dados = _ler()
    p = _do_projeto(dados, projeto)
    novo = {"cmd": cmd, "pasta": pasta, "sub": sub}
    p["recentes"] = [novo] + [r for r in p.get("recentes", []) if (r["cmd"], r.get("sub", "")) != (cmd, sub)]
    p["recentes"] = p["recentes"][:MAX_RECENTES]
    _gravar(dados)
    return f"{sub or '.'}|{cmd}"


def esquecer_recente(projeto: str, chave: str) -> None:
    dados = _ler()
    p = _do_projeto(dados, projeto)
    p["recentes"] = [r for r in p.get("recentes", []) if f"{r.get('sub') or '.'}|{r['cmd']}" != chave]
    if p.get("fixo") == chave:
        p["fixo"] = None
    _gravar(dados)


# --- comandos detectados que o usuário apagou da lista -----------------------
# Ficam só escondidos: a detecção continua achando, e "restaurar" traz de volta.

def ocultar(projeto: str, chave: str) -> None:
    dados = _ler()
    p = _do_projeto(dados, projeto)
    if chave not in p.setdefault("ocultos", []):
        p["ocultos"].append(chave)
    if p.get("fixo") == chave:
        p["fixo"] = None
    _gravar(dados)


def restaurar(projeto: str, chave: str | None = None) -> None:
    """Traz de volta um comando escondido, ou todos (chave=None)."""
    dados = _ler()
    p = _do_projeto(dados, projeto)
    p["ocultos"] = [] if chave is None else [c for c in p.get("ocultos", []) if c != chave]
    _gravar(dados)


# --- portas fixas -----------------------------------------------------------

def _chave_porta(projeto: str, chave: str) -> str:
    return f"{projeto.lower()}|{chave}"


def porta_reservada(projeto: str, chave: str) -> int | None:
    return _ler().get("_portas", {}).get(_chave_porta(projeto, chave))


def portas_reservadas() -> dict[str, int]:
    return dict(_ler().get("_portas", {}))


def reservar_porta(projeto: str, chave: str, porta: int | None) -> None:
    dados = _ler()
    portas = dados.setdefault("_portas", {})
    if porta:
        portas[_chave_porta(projeto, chave)] = int(porta)
    else:
        portas.pop(_chave_porta(projeto, chave), None)
    _gravar(dados)


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
