"""Sessões: guarda o que estava rodando para retomar depois com um clique.

O modo jogo salva uma sessão antes de parar tudo; "Retomar" sobe de novo os
mesmos processos (mesmo comando, pasta e variáveis) e containers.
"""

from __future__ import annotations

import json
import subprocess
import time
import uuid

import psutil

from argos.config import PASTA_DADOS
from argos.core import docker, registro

ARQUIVO = PASTA_DADOS / "sessoes.json"
MANTER = 10


def _ler() -> list[dict]:
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _gravar(sessoes: list[dict]) -> None:
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    tmp = ARQUIVO.with_suffix(".tmp")
    tmp.write_text(json.dumps(sessoes[:MANTER], ensure_ascii=False), encoding="utf-8")
    tmp.replace(ARQUIVO)


def salvar(est: dict, motivo: str = "manual") -> dict:
    """Fotografa os processos de dev e containers rodando agora."""
    itens = []
    for u in est["unidades"]:
        if u["categoria"] == "ferramenta":
            continue
        base = {"nome": u["nome"], "projeto": u["projeto"], "portas": u["portas"]}
        if u["gerenciado"]:
            e = registro.buscar(u["gerenciado"])
            if e:
                itens.append({**base, "tipo": "argos", "id": e["id"], "cmd": e["cmd"], "cwd": e["cwd"],
                              "shell": e["shell"], "env": e["env"], "auto": e.get("auto", False)})
            continue
        try:
            p = psutil.Process(u["pid"])
            args, cwd, env = p.cmdline(), p.cwd(), p.environ()
        except psutil.Error:
            continue
        itens.append({**base, "tipo": "externo", "cmd": subprocess.list2cmdline(args), "cwd": cwd,
                      "shell": False, "env": env})
    for c in est["docker"]["containers"]:
        if c["estado"] == "running":
            itens.append({"tipo": "container", "id": c["id"], "nome": c["nome"], "projeto": c["projeto"], "portas": []})

    sessao = {"id": uuid.uuid4().hex[:6], "quando": time.time(), "motivo": motivo, "itens": itens, "retomada": False}
    if itens:
        _gravar([sessao] + _ler())
    return sessao


def listar() -> list[dict]:
    return [{**s, "itens": [{k: v for k, v in i.items() if k != "env"} for i in s["itens"]]} for s in _ler()]


def pendente() -> dict | None:
    """Última sessão ainda não retomada (resumida, sem variáveis de ambiente)."""
    for s in _ler():
        if not s.get("retomada"):
            return {"id": s["id"], "quando": s["quando"], "motivo": s["motivo"],
                    "processos": sum(i["tipo"] != "container" for i in s["itens"]),
                    "containers": sum(i["tipo"] == "container" for i in s["itens"]),
                    "projetos": sorted({i["projeto"] for i in s["itens"] if i["projeto"]})}
        break
    return None


def descartar(id_: str) -> None:
    sessoes = _ler()
    for s in sessoes:
        if s["id"] == id_:
            s["retomada"] = True
    _gravar(sessoes)


def _rodando_agora() -> set[str]:
    """Linhas de comando já em execução (para não subir em dobro)."""
    saida = set()
    for p in psutil.process_iter(["cmdline"]):
        try:
            saida.add(subprocess.list2cmdline(p.info["cmdline"] or []))
        except (TypeError, psutil.Error):
            pass
    return saida


def retomar(id_: str | None = None, progresso=lambda msg: None) -> tuple[bool, str]:
    sessoes = _ler()
    sessao = next((s for s in sessoes if s["id"] == id_), None) if id_ else next(iter(sessoes), None)
    if not sessao:
        return False, "Nenhuma sessão salva."

    containers = [i for i in sessao["itens"] if i["tipo"] == "container"]
    if containers and docker.instalado() and not docker.ligado():
        progresso("Ligando o Docker Desktop…")
        docker.ligar_desktop()
        for _ in range(60):
            if docker.ligado():
                break
            time.sleep(2)

    rodando = _rodando_agora()
    subiu, falhou = [], []
    for i in sessao["itens"]:
        try:
            if i["tipo"] == "container":
                ok, _ = docker.iniciar([i["id"]])
                (subiu if ok else falhou).append(i["nome"])
                continue
            if i["tipo"] == "argos":
                e = registro.buscar(i["id"])
                if e and e["vivo"]:
                    continue
                if e:
                    registro.reiniciar(e)
                else:
                    registro.iniciar(i["cmd"], i["cwd"], i["env"], shell=i["shell"], nome=i["nome"],
                                     projeto=i["projeto"], auto=i.get("auto", False), id_=i["id"])
            else:
                if i["cmd"] in rodando:
                    continue
                registro.iniciar(i["cmd"], i["cwd"], i["env"], shell=False, nome=i["nome"], projeto=i["projeto"])
            progresso(f"Subindo {i['projeto'] or i['nome']}…")
            subiu.append(i["nome"])
        except Exception as e:  # um item com problema não impede os outros
            falhou.append(f"{i['nome']} ({e})")

    sessao["retomada"] = True
    _gravar(sessoes)
    msg = f"Retomados: {len(subiu)}" + (f" · falharam: {', '.join(falhou)}" if falhou else "")
    return not falhou, msg
