"""Variáveis de ambiente (.env): ver, editar e achar o que falta em relação ao .env.example."""

from __future__ import annotations

import re
from pathlib import Path

ARQUIVOS_ENV = (".env", ".env.local", ".env.development", ".env.development.local")
ARQUIVOS_EXEMPLO = (".env.example", ".env.sample", ".env.template", ".env.dist")
_LINHA = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_.-]*)\s*=\s*(.*)$")


def ler_chaves(caminho: Path) -> dict[str, str]:
    try:
        texto = caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    saida = {}
    for linha in texto.splitlines():
        if linha.lstrip().startswith("#"):
            continue
        m = _LINHA.match(linha)
        if m:
            saida[m.group(1)] = m.group(2).strip().strip("'\"")
    return saida


def analisar_pasta(pasta: Path, sub: str = "") -> dict | None:
    """Arquivos .env de uma pasta e as variáveis que faltam (comparando com o exemplo)."""
    envs = [pasta / n for n in ARQUIVOS_ENV if (pasta / n).is_file()]
    exemplo = next((pasta / n for n in ARQUIVOS_EXEMPLO if (pasta / n).is_file()), None)
    if not envs and not exemplo:
        return None
    definidas: set[str] = set()
    for e in envs:
        definidas |= set(ler_chaves(e))
    faltando = sorted(set(ler_chaves(exemplo)) - definidas) if exemplo else []
    return {
        "sub": sub, "pasta": str(pasta),
        "arquivos": [{"nome": e.name, "caminho": str(e), "chaves": len(ler_chaves(e))} for e in envs],
        "exemplo": {"nome": exemplo.name, "caminho": str(exemplo)} if exemplo else None,
        "faltando": faltando, "sem_env": bool(exemplo and not envs),
    }


def analisar(pasta_projeto: str) -> list[dict]:
    from argos.core.projetos import subpastas_app

    raiz = Path(pasta_projeto)
    saida = [a for a in [analisar_pasta(raiz)] if a]
    for rotulo, sub in subpastas_app(raiz):
        a = analisar_pasta(sub, rotulo)
        if a:
            saida.append(a)
    return saida


def total_faltando(pasta_projeto: str) -> int:
    return sum(len(a["faltando"]) for a in analisar(pasta_projeto))


def gravar(caminho: Path, texto: str) -> None:
    """Grava mantendo o fim de linha que o arquivo já usa (LF ou CRLF).

    O modo texto do Python no Windows troca todo "\\n" por "\\r\\n"; num .env lido por
    bash ou Docker, o "\\r" vira parte do valor da variável.
    """
    try:
        fim = "\r\n" if b"\r\n" in caminho.read_bytes() else "\n"
    except OSError:
        fim = "\n"
    texto = texto.replace("\r\n", "\n").replace("\r", "\n").replace("\n", fim)
    caminho.write_bytes(texto.encode("utf-8"))


def completar(pasta: str) -> tuple[bool, str]:
    """Cria o .env a partir do exemplo ou acrescenta só as variáveis que faltam."""
    p = Path(pasta)
    a = analisar_pasta(p)
    if not a or not a["exemplo"]:
        return False, "Essa pasta não tem .env.example."
    exemplo = Path(a["exemplo"]["caminho"])
    destino = p / ".env"
    if not destino.exists():
        destino.write_bytes(exemplo.read_bytes())  # cópia fiel, com o fim de linha do exemplo
        return True, f".env criado a partir do {exemplo.name}. Preencha os valores."
    if not a["faltando"]:
        return True, "Nada faltando."
    valores = ler_chaves(exemplo)
    extra = "\n# Adicionadas pelo Argos a partir do " + exemplo.name + "\n" + "".join(
        f"{k}={valores.get(k, '')}\n" for k in a["faltando"])
    texto = destino.read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n")
    gravar(destino, texto.rstrip("\n") + "\n" + extra)
    return True, f"{len(a['faltando'])} variável(is) adicionada(s) ao .env. Preencha os valores."


def arquivo_valido(caminho: str, pastas_projetos: list[str]) -> bool:
    """Só deixa ler/gravar arquivos .env dentro das pastas de projetos."""
    p = Path(caminho).resolve()
    nome_ok = p.name in ARQUIVOS_ENV or p.name in ARQUIVOS_EXEMPLO
    return nome_ok and any(Path(r).resolve() in p.parents for r in pastas_projetos)
