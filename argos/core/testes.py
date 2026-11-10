"""Testes de cada projeto: detectar como rodar, rodar e guardar o resultado."""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

from argos.config import PASTA_DADOS, PASTA_LOGS
from argos.core import arquivo
from argos.plataforma import SEM_JANELA

ARQUIVO = PASTA_DADOS / "testes.json"
TEMPO_MAXIMO = 20 * 60


def _detectar_pasta(pasta: Path, sub: str) -> list[dict]:
    from argos.core.projetos import _gerenciador_node, _ler, _ler_json

    saida = []
    pkg = pasta / "package.json"
    if pkg.exists():
        teste = _ler_json(pkg).get("scripts", {}).get("test", "")
        if teste and "no test specified" not in teste:
            saida.append(f"{_gerenciador_node(pasta)} test")
    pyproject = _ler(pasta / "pyproject.toml")
    if (pasta / "tests").is_dir() or "pytest" in pyproject or "pytest" in _ler(pasta / "requirements.txt"):
        if pyproject or (pasta / "requirements.txt").exists() or (pasta / "tests").is_dir():
            uv = "uv run " if (pasta / "uv.lock").exists() or "[tool.uv" in pyproject else ""
            saida.append(f"{uv}pytest -q")
    if (pasta / "go.mod").exists():
        saida.append("go test ./...")
    if (pasta / "Cargo.toml").exists():
        saida.append("cargo test")
    if list(pasta.glob("*.sln")) or list(pasta.glob("*.csproj")):
        saida.append("dotnet test")
    if re.search(r"^test\s*:", _ler(pasta / "Makefile"), re.M):
        saida.append("make test")
    return [{"cmd": c, "sub": sub, "pasta": str(pasta), "chave": f"{sub or '.'}|{c}"} for c in saida]


def detectar(pasta_projeto: str) -> list[dict]:
    from argos.core.projetos import subpastas_app

    raiz = Path(pasta_projeto)
    saida = _detectar_pasta(raiz, "")
    for rotulo, sub in subpastas_app(raiz):
        saida += _detectar_pasta(sub, rotulo)
    return saida


def _ler() -> dict:
    return arquivo.ler(ARQUIVO, {})


def resultados(projeto: str) -> dict:
    return _ler().get(projeto.lower(), {})


def resumo(projeto: str) -> dict | None:
    """Último resultado de cada teste juntado: ok só se todos passaram."""
    r = resultados(projeto)
    if not r:
        return None
    return {"ok": all(x["ok"] for x in r.values()), "quando": max(x["quando"] for x in r.values()),
            "falhas": sum(not x["ok"] for x in r.values()), "total": len(r)}


def _resumo_saida(texto: str) -> str:
    """Linha que resume o resultado (ex: '12 passed in 0.3s')."""
    limpo = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", texto)
    linhas = [l.strip() for l in limpo.splitlines() if l.strip()]
    for l in reversed(linhas):
        if re.search(r"\b(passed|failed|pass|fail|tests?|ok|FAIL|PASS)\b", l, re.I):
            return l[:160]
    return linhas[-1][:160] if linhas else ""


def rodar(projeto: str, teste: dict) -> dict:
    """Roda um teste até o fim e guarda o resultado."""
    from argos.core.registro import _limpar_env, _slug

    PASTA_LOGS.mkdir(parents=True, exist_ok=True)
    log = PASTA_LOGS / f"testes-{_slug(projeto)}-{_slug(teste['sub'] or 'raiz')}.log"
    # CI=true: Jest/Vitest rodam uma vez em vez de ficar em modo "watch"
    env = {**_limpar_env(dict(os.environ)), "CI": "true", "FORCE_COLOR": "1"}
    inicio = time.time()
    with open(log, "wb") as saida:
        try:
            r = subprocess.run(teste["cmd"], cwd=teste["pasta"], shell=True, env=env, stdout=saida,
                               stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=TEMPO_MAXIMO,
                               creationflags=SEM_JANELA)
            codigo = r.returncode
        except subprocess.TimeoutExpired:
            codigo = -1
    texto = log.read_text(encoding="utf-8", errors="replace")
    resultado = {"ok": codigo == 0, "codigo": codigo, "cmd": teste["cmd"], "sub": teste["sub"],
                 "quando": time.time(), "duracao": time.time() - inicio, "log": str(log),
                 "resumo": "tempo esgotado" if codigo == -1 else _resumo_saida(texto)}
    with arquivo.trava(ARQUIVO):
        dados = _ler()
        dados.setdefault(projeto.lower(), {})[teste["chave"]] = resultado
        arquivo.gravar(ARQUIVO, dados)
    return resultado
