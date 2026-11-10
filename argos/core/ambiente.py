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


def e_exemplo(nome: str) -> bool:
    return nome in ARQUIVOS_EXEMPLO or nome.endswith((".example", ".sample", ".template", ".dist"))


def arquivos_env(pasta: Path) -> list[Path]:
    """.env e .env.<ambiente> da pasta (staging, production...), sem os de exemplo."""
    try:
        achados = [f for f in pasta.iterdir() if f.is_file() and (f.name == ".env" or f.name.startswith(".env."))
                   and not e_exemplo(f.name)]
    except OSError:
        return []
    ordem = {n: i for i, n in enumerate(ARQUIVOS_ENV)}
    return sorted(achados, key=lambda f: (ordem.get(f.name, len(ordem)), f.name))


def variaveis_escolhidas(projeto: dict, sub: str = "") -> dict[str, str]:
    """Variáveis do arquivo .env escolhido para a pasta, para pôr no ambiente do processo.

    Sem escolha devolve {}: o projeto carrega o .env dele como sempre. Com escolha
    (ex: .env.staging), essas variáveis vão no ambiente e valem sobre as do .env padrão,
    porque as bibliotecas de .env não sobrescrevem o que já está definido.
    """
    from argos.core import preferencias

    sub = (sub or "").strip("\\/")
    nome = preferencias.arquivo_env(projeto["nome"], sub)
    if not nome:
        return {}
    arq = (Path(projeto["pasta"]) / sub / nome) if sub and sub != "." else Path(projeto["pasta"]) / nome
    return ler_chaves(arq) if arq.is_file() and not e_exemplo(nome) else {}


def analisar_pasta(pasta: Path, sub: str = "") -> dict | None:
    """Arquivos .env de uma pasta e as variáveis que faltam (comparando com o exemplo)."""
    envs = arquivos_env(pasta)
    exemplo = next((pasta / n for n in ARQUIVOS_EXEMPLO if (pasta / n).is_file()), None)
    if not envs and not exemplo:
        return None
    definidas: set[str] = set()
    # "Faltando" compara com os arquivos de desenvolvimento: um .env.production completo não conta
    for e in envs:
        if e.name in ARQUIVOS_ENV:
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
    nome_ok = p.name == ".env" or p.name.startswith(".env.")
    return nome_ok and any(Path(r).resolve() in p.parents for r in pastas_projetos)
