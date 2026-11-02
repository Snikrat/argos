"""Portas fixas: cada comando ganha uma porta própria e estável.

Sem isso, o segundo Vite aberto cai na 5174, depois na 5175... e muda a cada dia.
Aqui a porta é escolhida uma vez, guardada nas preferências e passada à
ferramenta (ex: `npm run dev -- --port 5180 --strictPort`).
"""

from __future__ import annotations

import re

# Faixas usadas quando a porta padrão da ferramenta já está reservada
FAIXAS = {"site": range(5173, 5300), "api": range(8000, 8100)}
TIPO = {"uvicorn": "api", "django": "api"}


def argumentos(ferramenta: str, porta: int) -> list[str]:
    """Como dizer a porta para cada ferramenta (vazio = só a variável PORT)."""
    if ferramenta == "vite":
        return ["--port", str(porta), "--strictPort"]
    if ferramenta in ("astro", "nuxi", "nuxt", "ng", "webpack", "webpack-dev-server", "svelte-kit", "remix"):
        return ["--port", str(porta)]
    if ferramenta in ("next", "gatsby"):
        return ["-p", str(porta)]
    return []  # react-scripts e outros leem a variável PORT


def aplicar(cmd: str, ferramenta: str, porta: int) -> tuple[str, dict[str, str]]:
    """Comando ajustado para a porta e variáveis extras."""
    env = {"PORT": str(porta)}
    if ferramenta == "uvicorn":
        if re.search(r"--port[ =]\d+", cmd):
            return re.sub(r"--port[ =]\d+", f"--port {porta}", cmd), env
        return f"{cmd} --port {porta}", env
    if ferramenta == "django":
        return re.sub(r"runserver(\s+[\d.:]+)?", f"runserver {porta}", cmd, count=1), env
    args = argumentos(ferramenta, porta)
    if not args:
        return cmd, env
    # npm precisa de "--" para repassar argumentos ao script; pnpm, yarn e bun não
    separador = " -- " if cmd.split()[0] == "npm" else " "
    return cmd + separador + " ".join(args), env


def escolher(comando: dict, reservadas: set[int], ocupadas: set[int]) -> int:
    """Primeira porta livre: a padrão da ferramenta, senão a próxima da faixa."""
    tipo = TIPO.get(comando.get("ferramenta") or "", "site")
    usadas = reservadas | ocupadas
    candidatas = ([comando["porta"]] if comando.get("porta") else []) + list(FAIXAS[tipo])
    for p in candidatas:
        if p not in usadas:
            return p
    return candidatas[-1]
