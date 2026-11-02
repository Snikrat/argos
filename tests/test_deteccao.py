import json

import pytest

from argos.core import preferencias, projetos


@pytest.fixture(autouse=True)
def prefs_isoladas(tmp_path, monkeypatch):
    monkeypatch.setattr(preferencias, "ARQUIVO", tmp_path / "prefs.json")


def criar(base, arquivos: dict):
    for rel, conteudo in arquivos.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(conteudo, encoding="utf-8")
    return base


def chaves(p):
    return [c["chave"] for c in p["comandos"]]


def test_subpastas_front_e_back(tmp_path):
    proj = criar(tmp_path / "loja", {
        "package.json": json.dumps({"scripts": {"dev": "concurrently ..."}}),
        "frontend/package.json": json.dumps({"scripts": {"dev": "vite"}, "devDependencies": {"vite": "5"}}),
        "backend/pyproject.toml": "[project]\nname='api'\n[tool.uv]\n",
        "backend/app/main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
        "frontend/node_modules/x/package.json": json.dumps({"scripts": {"dev": "x"}}),
        "docs/package.json": json.dumps({"scripts": {"dev": "docs"}}),
    })
    p = projetos.detectar(proj)
    por_chave = {c["chave"]: c for c in p["comandos"]}
    assert set(por_chave) == {".|npm run dev", "frontend|npm run dev",
                              "backend|uv run uvicorn app.main:app --reload --port 8000"}
    back = por_chave["backend|uv run uvicorn app.main:app --reload --port 8000"]
    assert back["pasta"].endswith("backend") and back["porta"] == 8000 and back["sub"] == "backend"
    assert por_chave["frontend|npm run dev"]["porta"] == 5173


def test_monorepo_apps(tmp_path):
    proj = criar(tmp_path / "mono", {
        "apps/web/package.json": json.dumps({"scripts": {"dev": "next dev"}, "dependencies": {"next": "14"}}),
        "apps/api/go.mod": "module api\n",
        "apps/api/main.go": "package main\nfunc main(){}\n",
    })
    p = projetos.detectar(proj)
    assert "apps/web|npm run dev" in chaves(p)
    assert "apps/api|go run ." in chaves(p)


@pytest.mark.parametrize("arquivos, cmd", [
    ({"Cargo.toml": "[package]\nname='x'\n"}, "cargo run"),
    ({"x.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>'}, "dotnet watch run"),
    ({"artisan": ""}, "php artisan serve"),
    ({"pom.xml": "<artifactId>spring-boot-starter-web</artifactId>"}, "mvn spring-boot:run"),
    ({"deno.json": '{"tasks": {"dev": "deno run -A main.ts"}}'}, "deno task dev"),
    ({"Makefile": "build:\n\tgo build\ndev:\n\tair\n"}, "make dev"),
    ({"bin/rails": ""}, "ruby bin/rails server"),
    ({"pyproject.toml": "[project]\nname='t'\n[project.scripts]\nmeu-app = 't:main'\n"}, "uv run meu-app"),
])
def test_linguagens(tmp_path, arquivos, cmd):
    p = projetos.detectar(criar(tmp_path / "p", arquivos))
    assert cmd in [c["cmd"] for c in p["comandos"]]


def test_ultimo_usado_vira_principal_e_fixo_vence(tmp_path):
    proj = criar(tmp_path / "app", {
        "package.json": json.dumps({"scripts": {"dev": "vite", "start": "node s.js"}}),
    })
    assert projetos.detectar(proj)["comandos"][0]["chave"] == ".|npm run dev"
    preferencias.registrar_uso("app", ".|npm run start")
    assert projetos.detectar(proj)["comandos"][0]["chave"] == ".|npm run start"
    preferencias.fixar("app", ".|npm run dev")
    p = projetos.detectar(proj)
    assert p["comandos"][0]["chave"] == ".|npm run dev" and p["fixo"] == ".|npm run dev"


def test_recentes_aparecem_e_somem(tmp_path):
    proj = criar(tmp_path / "app", {"package.json": json.dumps({"scripts": {"dev": "vite"}})})
    chave = preferencias.adicionar_recente("app", "npm run build", str(proj))
    preferencias.registrar_uso("app", chave)
    p = projetos.detectar(proj)
    assert p["comandos"][0]["chave"] == chave and p["comandos"][0]["recente"]
    preferencias.esquecer_recente("app", chave)
    assert chave not in chaves(projetos.detectar(proj))
