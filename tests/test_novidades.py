import json

import pytest

from argos.app.monitor import vazando
from argos.core import projetos


def toml(tmp_path, texto):
    (tmp_path / "argos.toml").write_text(texto, encoding="utf-8")
    return tmp_path


def test_grupo_ordena_por_dependencia(tmp_path):
    p = toml(tmp_path, """
[[servico]]
nome = "web"
cmd = "npm run dev"
depois = ["api"]

[[servico]]
nome = "api"
cmd = "uv run uvicorn main:app"
pronto = "porta:8000"
depois = ["banco"]

[[servico]]
nome = "banco"
docker = "db"
pronto = "porta:5432"
""")
    assert [s["nome"] for s in projetos.carregar_grupo(p)] == ["banco", "api", "web"]


@pytest.mark.parametrize("texto, erro", [
    ('[[servico]]\nnome = "a"\n', "cmd"),
    ('[[servico]]\nnome = "a"\ncmd = "x"\ndepois = ["b"]\n', "não existe"),
    ('[[servico]]\nnome = "a"\ncmd = "x"\npronto = "5173"\n', "pronto"),
    ('[[servico]]\nnome = "a"\ncmd = "x"\ndepois = ["b"]\n[[servico]]\nnome = "b"\ncmd = "y"\ndepois = ["a"]\n', "circular"),
    ('isso não é toml', "sintaxe"),
])
def test_grupo_invalido(tmp_path, texto, erro):
    with pytest.raises(projetos.ErroGrupo, match=erro):
        projetos.carregar_grupo(toml(tmp_path, texto))


def test_detectar_mostra_subir_tudo(tmp_path):
    toml(tmp_path, '[[servico]]\nnome = "a"\ncmd = "x"\n')
    p = projetos.detectar(tmp_path)
    assert p["grupo"] == ["a"]
    assert p["comandos"][0]["tipo"] == "grupo"


def test_modelo_gerado_e_valido(tmp_path):
    (tmp_path / "docker-compose.yml").write_text('services:\n  db:\n    ports:\n      - "5432:5432"\n')
    front = tmp_path / "frontend"
    front.mkdir()
    (front / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}, "devDependencies": {"vite": "5"}}))
    back = tmp_path / "backend"
    back.mkdir()
    (back / "pyproject.toml").write_text("")
    (back / "main.py").write_text("import uvicorn\n")
    (tmp_path / "argos.toml").write_text(projetos.gerar_grupo(tmp_path), encoding="utf-8")
    servicos = projetos.carregar_grupo(tmp_path)
    assert [s["nome"] for s in servicos] == ["containers", "backend", "frontend"]
    assert servicos[2]["pronto"] == "porta:5173"


@pytest.mark.parametrize("cmd, esperado", [
    (r'node "C:\p\agendamento\frontend\node_modules\.bin\..\vite\bin\vite.js"', "site"),
    (r'"C:\x\python.exe" "C:\p\agendamento\backend\.venv\Scripts\uvicorn.exe" app.main:app --reload', "api"),
    (r'"C:\Program Files\nodejs\node.exe" --require "C:\p\intranet\backend\node_modules\tsx\dist\preflight.cjs"', "api"),
    (r'node C:\p\loja\node_modules\next\dist\bin\next dev', "site"),
    (r'python manage.py runserver', "api"),
    (r'node server.js', ""),
])
def test_classificar_porta(cmd, esperado):
    from argos.core.coleta import classificar_porta
    assert classificar_porta(cmd) == esperado


def test_vazamento():
    subindo = [100 + i * 10 for i in range(60)]
    estavel = [500 + (i % 5) for i in range(60)]
    assert vazando(subindo, idade=3600)
    assert not vazando(estavel, idade=3600)
    assert not vazando(subindo, idade=600)  # recém-iniciado: subir é normal
