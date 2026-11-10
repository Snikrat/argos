"""Sessões: guarda o que estava rodando para retomar depois com um clique.

O modo jogo salva uma sessão antes de parar tudo; "Retomar" sobe de novo os
mesmos processos (mesmo comando, pasta e variáveis) e containers. Uma sessão
salva com nome vira um perfil ("trabalho", "jogo") que fica guardado.
"""

from __future__ import annotations

import subprocess
import time
import uuid

import psutil

from argos.config import PASTA_DADOS
from argos.core import arquivo, docker, registro, segredo

ARQUIVO = PASTA_DADOS / "sessoes.json"
MANTER = 10  # sessões sem nome guardadas (os perfis, com nome, ficam todos)


def _ler() -> list[dict]:
    sessoes = arquivo.ler(ARQUIVO, [])
    for s in sessoes:
        s["itens"] = [segredo.ler_de(i) for i in s.get("itens", [])]
    return sessoes


def _gravar(sessoes: list[dict]) -> None:
    sem_nome = 0
    manter = []
    for s in sessoes:
        if not s.get("nome"):
            sem_nome += 1
            if sem_nome > MANTER:
                continue
        manter.append({**s, "itens": [segredo.guardar_em(i) for i in s["itens"]]})
    arquivo.gravar(ARQUIVO, manter, indent=None)


def salvar(est: dict, motivo: str = "manual", nome: str = "") -> dict:
    """Fotografa os processos de dev e containers rodando agora. Com `nome`, vira um perfil."""
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
                      "shell": False, "env": segredo.sem_sessao(env)})
    for c in est["docker"]["containers"]:
        if c["estado"] == "running":
            itens.append({"tipo": "container", "id": c["id"], "nome": c["nome"], "projeto": c["projeto"], "portas": []})

    nome = nome.strip()
    sessao = {"id": uuid.uuid4().hex[:6], "quando": time.time(), "motivo": motivo, "nome": nome,
              "itens": itens, "retomada": bool(nome)}  # perfil não fica "pendente" na tela
    if itens:
        with arquivo.trava(ARQUIVO):
            # Salvar de novo com o mesmo nome substitui o perfil
            outras = [s for s in _ler() if not nome or s.get("nome", "").lower() != nome.lower()]
            _gravar([sessao] + outras)
    return sessao


def criar_perfil(nome: str, comandos: list[dict]) -> dict:
    """Perfil montado a partir de comandos de projetos (não precisa estar nada rodando).

    Cada item é {"projeto", "chave", "nome"}: ao retomar, o comando é procurado de novo no
    projeto e iniciado como pelo botão da tela (com porta fixa, .env escolhido etc.).
    """
    nome = nome.strip()
    itens = [{"tipo": "comando", "projeto": c["projeto"], "chave": c["chave"],
              "nome": c.get("nome") or c["chave"].split("|", 1)[-1], "portas": []} for c in comandos]
    sessao = {"id": uuid.uuid4().hex[:6], "quando": time.time(), "motivo": "perfil", "nome": nome,
              "itens": itens, "retomada": True}
    if nome and itens:
        with arquivo.trava(ARQUIVO):
            _gravar([sessao] + [s for s in _ler() if s.get("nome", "").lower() != nome.lower()])
    return sessao


def _iniciar_comando(item: dict) -> str | None:
    """Inicia o comando de um perfil. Devolve None se já estava rodando; levanta se falhar."""
    from argos import config
    from argos.core import acoes, projetos

    cfg = config.carregar()
    p = projetos.buscar(cfg, item["projeto"])
    c = projetos.buscar_comando(p, item["chave"]) if p else None
    if not c:
        raise RuntimeError("projeto ou comando não existe mais")
    rotulo = f"{c['sub']}: {c['rotulo']}" if c.get("sub") else c["rotulo"]
    if any(e["vivo"] and e.get("projeto", "").lower() == p["nome"].lower() and e["nome"] == rotulo for e in registro.listar()):
        return None
    r = acoes.iniciar_comando(cfg, p, c)
    if not r.ok:
        raise RuntimeError(r.msg)
    return rotulo


def _resumo(s: dict) -> dict:
    return {"id": s["id"], "quando": s["quando"], "motivo": s["motivo"], "nome": s.get("nome", ""),
            "retomada": bool(s.get("retomada")), "falhas": s.get("falhas", []),
            "processos": sum(i["tipo"] != "container" for i in s["itens"]),
            "containers": sum(i["tipo"] == "container" for i in s["itens"]),
            "projetos": sorted({i["projeto"] for i in s["itens"] if i["projeto"]})}


def listar() -> list[dict]:
    """Sessões e perfis, resumidos (sem comandos nem variáveis)."""
    return [_resumo(s) for s in _ler()]


def pendente() -> dict | None:
    """Última sessão sem nome ainda não retomada por completo."""
    for s in _ler():
        if s.get("nome"):
            continue
        return None if s.get("retomada") else _resumo(s)
    return None


def descartar(id_: str) -> None:
    with arquivo.trava(ARQUIVO):
        sessoes = _ler()
        for s in sessoes:
            if s["id"] == id_:
                s["retomada"] = True
                s.pop("falhas", None)
        _gravar(sessoes)


def apagar(id_: str) -> bool:
    with arquivo.trava(ARQUIVO):
        sessoes = _ler()
        resto = [s for s in sessoes if s["id"] != id_]
        _gravar(resto)
    return len(resto) < len(sessoes)


def _achar(sessoes: list[dict], alvo: str | None) -> dict | None:
    if alvo:
        return next((s for s in sessoes if s["id"] == alvo or s.get("nome", "").lower() == alvo.lower()), None)
    return next((s for s in sessoes if not s.get("nome") and not s.get("retomada")), None) or next(iter(sessoes), None)


def _rodando_agora() -> set[str]:
    """Linhas de comando já em execução (para não subir em dobro)."""
    saida = set()
    for p in psutil.process_iter(["cmdline"]):
        try:
            saida.add(subprocess.list2cmdline(p.info["cmdline"] or []))
        except (TypeError, psutil.Error):
            pass
    return saida


def retomar(alvo: str | None = None, progresso=lambda msg: None) -> tuple[bool, str]:
    """Sobe de novo os itens da sessão (por id ou nome do perfil; sem alvo, a pendente).

    Se algum item falhar, a sessão continua pendente com a lista do que falhou:
    retomar de novo tenta só o que ainda não está rodando.
    """
    sessao = _achar(_ler(), alvo)
    if not sessao:
        return False, "Nenhuma sessão salva." if not alvo else f"Sessão '{alvo}' não encontrada."

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
                if not ok:  # o container pode ter sido recriado com outro id
                    ok, _ = docker.iniciar([i["nome"]])
                (subiu if ok else falhou).append(i["nome"])
                continue
            if i["tipo"] == "comando":
                if _iniciar_comando(i) is None:
                    continue
                progresso(f"Subindo {i['projeto']}…")
                subiu.append(i["nome"])
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

    with arquivo.trava(ARQUIVO):
        sessoes = _ler()
        for s in sessoes:
            if s["id"] == sessao["id"]:
                s["falhas"] = falhou
                if not s.get("nome"):
                    s["retomada"] = not falhou
        _gravar(sessoes)
    if falhou:
        return False, f"Retomados: {len(subiu)}. Falharam: {', '.join(falhou)}. A sessão continua salva para tentar de novo."
    return True, f"Retomados: {len(subiu)}" if subiu else "Tudo dessa sessão já estava rodando."
