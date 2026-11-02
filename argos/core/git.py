"""Ações de Git: buscar, puxar, enviar e trocar de branch."""

from __future__ import annotations

import os
import subprocess

from argos.plataforma import SEM_JANELA


def _git(pasta: str, *args: str, timeout: float = 60) -> tuple[bool, str]:
    # Sem perguntas interativas: se precisar de senha, falha em vez de travar
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
    try:
        r = subprocess.run(["git", "-C", pasta, *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env, creationflags=SEM_JANELA)
    except subprocess.TimeoutExpired:
        return False, "o Git demorou demais (rede ou autenticação?)"
    except OSError:
        return False, "Git não encontrado."
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def branches(pasta: str) -> dict:
    ok, saida = _git(pasta, "branch", "--format=%(refname:short)|%(HEAD)", timeout=10)
    if not ok:
        return {"atual": "", "locais": []}
    locais, atual = [], ""
    for linha in saida.splitlines():
        nome, _, marca = linha.partition("|")
        locais.append(nome)
        if marca.strip() == "*":
            atual = nome
    return {"atual": atual, "locais": locais}


def fetch(pasta: str) -> tuple[bool, str]:
    ok, saida = _git(pasta, "fetch", "--quiet", "--prune", timeout=45)
    return ok, "Atualizado." if ok else saida[-300:]


def pull(pasta: str) -> tuple[bool, str]:
    # Só avança (sem merge automático): se divergiu, o usuário decide
    ok, saida = _git(pasta, "pull", "--ff-only", timeout=120)
    if ok:
        return True, "Já estava atualizado." if "Already up to date" in saida else "Commits novos baixados."
    if "Not possible to fast-forward" in saida or "diverg" in saida:
        return False, "Sua branch e a do servidor divergiram. Resolva no terminal (git pull --rebase ou merge)."
    return False, saida[-300:]


def _sem_commit(pasta: str) -> bool:
    ok, saida = _git(pasta, "status", "--porcelain", timeout=10)
    return ok and bool(saida)


def push(pasta: str) -> tuple[bool, str]:
    # Com upstream e nenhum commit à frente, não há o que enviar
    ok, saida = _git(pasta, "rev-list", "--count", "@{u}..HEAD", timeout=10)
    if ok and saida.strip() == "0":
        if _sem_commit(pasta):
            return True, "Nada para enviar: as alterações ainda não foram commitadas."
        return True, "Nada para enviar: já está tudo no servidor."
    ok, saida = _git(pasta, "push", timeout=120)
    if not ok and ("no upstream" in saida or "has no upstream" in saida):
        ok, saida = _git(pasta, "push", "-u", "origin", "HEAD", timeout=120)
    return ok, "Enviado." if ok else saida[-300:]


def checkout(pasta: str, branch: str) -> tuple[bool, str]:
    ok, saida = _git(pasta, "checkout", branch, timeout=30)
    if ok:
        return True, f"Agora na branch {branch}."
    if "would be overwritten" in saida or "commit your changes" in saida:
        return False, "Há alterações não commitadas que seriam perdidas. Faça commit ou stash antes de trocar."
    return False, saida[-300:]
