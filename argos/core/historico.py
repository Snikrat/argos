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
    """Tira o que é antigo e os eventos repetidos (cada abertura do app regravava os "início")."""
    limite = time.time() - MANTER_DIAS * 86400
    vistos, evs = set(), []
    for e in _eventos():
        marca = (e["chave"], e["tipo"])
        if e["ts"] >= limite and marca not in vistos:
            vistos.add(marca)
            evs.append(e)
    try:
        ARQUIVO_HISTORICO.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in evs), encoding="utf-8")
    except OSError:
        pass


def abertos() -> dict[str, dict]:
    """Processos com "início" e sem "fim" no arquivo: chave -> dados para `registrar`."""
    saida: dict[str, dict] = {}
    for e in _eventos():
        if e["tipo"] == "inicio":
            saida[e["chave"]] = {"pid": int(e["chave"].split("-")[0]), "nome": e["nome"],
                                 "projeto": e["projeto"], "inicio": e["inicio"]}
        else:
            saida.pop(e["chave"], None)
    return saida


def ultima_escrita() -> float:
    """Última vez que o app gravou o histórico: o mais perto que se sabe de quando ele fechou."""
    try:
        return ARQUIVO_HISTORICO.stat().st_mtime
    except OSError:
        return time.time()


def da_semana(ativos: list[dict] | None = None, dias: int = 7) -> list[dict]:
    """Tempo rodando por projeto em cada um dos últimos `dias` (hoje por último)."""
    agora = time.time()
    hoje = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
    inicio_dia = [hoje - 86400 * d for d in range(dias - 1, -1, -1)]
    itens: dict[str, dict] = {}
    for e in _eventos():
        it = itens.setdefault(e["chave"], {"projeto": e["projeto"] or "(sem projeto)", "inicio": e["inicio"], "fim": None})
        if e["tipo"] == "fim":
            it["fim"] = e["ts"]
    vivos = {chave(u) for u in ativos or []}
    for u in ativos or []:
        itens.setdefault(chave(u), {"projeto": u.get("projeto") or "(sem projeto)", "inicio": u["inicio"], "fim": None})
    intervalos: dict[str, list[tuple[float, float]]] = {}
    for k, it in itens.items():
        fim = it["fim"] or (agora if k in vivos else None)
        if fim is not None:
            intervalos.setdefault(it["projeto"], []).append((it["inicio"], fim))
    por_projeto: dict[str, list[float]] = {}
    for projeto, lista in intervalos.items():
        serie = [0.0] * dias
        for n, comeco in enumerate(inicio_dia):
            # Backend e frontend rodando juntos contam uma vez só: une os intervalos do dia
            ate = comeco
            for ini, fim in sorted((max(i, comeco), min(f, comeco + 86400)) for i, f in lista):
                if fim > max(ini, ate):
                    serie[n] += fim - max(ini, ate)
                    ate = fim
        por_projeto[projeto] = serie
    saida = [{"projeto": p, "dias": s, "total": sum(s)} for p, s in por_projeto.items() if sum(s) >= 60]
    saida.sort(key=lambda x: -x["total"])
    return saida


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
