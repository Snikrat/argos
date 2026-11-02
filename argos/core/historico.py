"""Histórico do que rodou: eventos de início/fim gravados pelo app."""

from __future__ import annotations

import json
import time

from argos.config import ARQUIVO_HISTORICO, PASTA_DADOS

MANTER_DIAS = 14


def chave(u: dict) -> str:
    return f"{u['pid']}-{int(u['inicio'])}"


def registrar(tipo: str, u: dict, quando: float | None = None) -> None:
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    ev = {"ts": quando or time.time(), "tipo": tipo, "chave": chave(u), "nome": u["nome"],
          "projeto": u.get("projeto", ""), "inicio": u["inicio"]}
    with open(ARQUIVO_HISTORICO, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def _eventos() -> list[dict]:
    try:
        linhas = ARQUIVO_HISTORICO.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    saida = []
    for l in linhas:
        try:
            saida.append(json.loads(l))
        except ValueError:
            pass
    return saida


def podar() -> None:
    limite = time.time() - MANTER_DIAS * 86400
    evs = [e for e in _eventos() if e["ts"] >= limite]
    try:
        ARQUIVO_HISTORICO.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in evs), encoding="utf-8")
    except OSError:
        pass


def do_dia(ativos: list[dict] | None = None) -> list[dict]:
    """Tudo que rodou hoje, com a duração. `ativos` são as unidades rodando agora."""
    meia_noite = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
    itens: dict[str, dict] = {}
    for e in _eventos():
        it = itens.setdefault(e["chave"], {"nome": e["nome"], "projeto": e["projeto"],
                                           "inicio": e["inicio"], "fim": None})
        if e["tipo"] == "fim":
            it["fim"] = e["ts"]
    for u in ativos or []:
        itens.setdefault(chave(u), {"nome": u["nome"], "projeto": u.get("projeto", ""),
                                    "inicio": u["inicio"], "fim": None})
    vivos = {chave(u) for u in ativos or []}
    agora = time.time()
    saida = []
    for k, it in itens.items():
        fim = it["fim"] or (agora if k in vivos else None)
        if fim is None or fim < meia_noite:
            continue
        it["rodando"] = k in vivos
        it["duracao"] = fim - max(it["inicio"], meia_noite)
        saida.append(it)
    saida.sort(key=lambda i: i["inicio"])
    return saida
