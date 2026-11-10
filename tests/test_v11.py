"""Testes das funcionalidades da 1.1: portas fixas, proxy, .env, testes, sessões, atualização e MCP."""
import io
import json
import sys

import pytest

from argos import __version__
from argos.core import ambiente, atualizacao, portas, preferencias, projetos, testes


@pytest.fixture(autouse=True)
def prefs_isoladas(tmp_path, monkeypatch):
    monkeypatch.setattr(preferencias, "ARQUIVO", tmp_path / "prefs.json")


# --- portas fixas -----------------------------------------------------------

@pytest.mark.parametrize("script, ferramenta", [
    ("vite", "vite"), ("vite --host", "vite"), ("next dev", "next"), ("astro dev", "astro"),
    ("react-scripts start", "react-scripts"), ("concurrently \"npm:dev:*\"", None),
    ("tsx watch src/server.ts", None), ("vite build && vite preview", None),
])
def test_ferramenta_do_script(script, ferramenta):
    assert projetos.ferramenta_do_script(script) == ferramenta


@pytest.mark.parametrize("cmd, ferramenta, esperado", [
    ("npm run dev", "vite", "npm run dev -- --port 5180 --strictPort"),
    ("pnpm run dev", "vite", "pnpm run dev --port 5180 --strictPort"),
    ("npm run dev", "next", "npm run dev -- -p 5180"),
    ("npm run start", "react-scripts", "npm run start"),
    ("uv run uvicorn app.main:app --reload --port 8000", "uvicorn", "uv run uvicorn app.main:app --reload --port 5180"),
    ("python manage.py runserver", "django", "python manage.py runserver 5180"),
])
def test_aplicar_porta(cmd, ferramenta, esperado):
    novo, env = portas.aplicar(cmd, ferramenta, 5180)
    assert novo == esperado and env == {"PORT": "5180"}


def test_escolher_porta_evita_reservadas_e_ocupadas():
    c = {"ferramenta": "vite", "porta": 5173}
    assert portas.escolher(c, set(), set()) == 5173
    assert portas.escolher(c, {5173}, {5174}) == 5175
    assert portas.escolher({"ferramenta": "uvicorn", "porta": 8000}, {8000}, set()) == 8001


def test_porta_fixa_aparece_no_projeto(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}, "devDependencies": {"vite": "5"}}))
    preferencias.reservar_porta(tmp_path.name, ".|npm run dev", 5190)
    c = projetos.detectar(tmp_path)["comandos"][0]
    assert c["porta"] == 5190 and c["porta_fixa"]


# --- proxy de nomes ---------------------------------------------------------

def test_rotas_do_proxy():
    from argos.app.proxy import calcular_rotas

    est = {"unidades": [{
        "categoria": "projeto", "projeto": "Meu App", "portas": [5174, 3000],
        "portas_tipo": {5174: "site", 3000: "api"}, "portas_hosts": {5174: ["::1"], 3000: ["127.0.0.1"]},
    }]}
    rotas = calcular_rotas(est)
    assert rotas["meu-app.localhost"] == ("::1", 5174)
    assert rotas["api.meu-app.localhost"] == ("127.0.0.1", 3000)
    assert rotas["3000.meu-app.localhost"] == ("127.0.0.1", 3000)


# --- .env -------------------------------------------------------------------

def test_env_faltando_e_completar(tmp_path):
    (tmp_path / ".env.example").write_text("DB_URL=postgres://\nAPI_KEY=\n# comentário\nPORT=3000\n")
    a = ambiente.analisar_pasta(tmp_path)
    assert a["sem_env"] and a["faltando"] == ["API_KEY", "DB_URL", "PORT"]
    ambiente.completar(str(tmp_path))
    assert (tmp_path / ".env").exists() and not ambiente.analisar_pasta(tmp_path)["faltando"]
    (tmp_path / ".env.example").write_text("DB_URL=x\nNOVA=1\n")
    ok, msg = ambiente.completar(str(tmp_path))
    assert ok and "NOVA=1" in (tmp_path / ".env").read_text()


def test_env_so_dentro_dos_projetos(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    assert ambiente.arquivo_valido(str(proj / ".env"), [str(tmp_path)])
    assert not ambiente.arquivo_valido(str(proj / "segredo.txt"), [str(tmp_path)])
    assert not ambiente.arquivo_valido(str(tmp_path.parent / ".env"), [str(tmp_path)])


# --- testes -----------------------------------------------------------------

def test_detectar_testes(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"test": "vitest"}}))
    back = tmp_path / "backend"
    (back / "tests").mkdir(parents=True)
    (back / "pyproject.toml").write_text("[tool.uv]\n")
    lista = testes.detectar(str(tmp_path))
    assert [(t["sub"], t["cmd"]) for t in lista] == [("", "npm test"), ("backend", "uv run pytest -q")]


def test_ignora_script_de_teste_padrao(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"test": "echo \"Error: no test specified\" && exit 1"}}))
    assert testes.detectar(str(tmp_path)) == []


# --- atualização ------------------------------------------------------------

def test_atualizacao_disponivel(tmp_path):
    from argos.config import Config

    cfg = Config(pastas_projetos=[str(tmp_path)], pasta_atualizacao=str(tmp_path), procurar_atualizacao=False)
    (tmp_path / "argos-1.0.0.zip").write_bytes(b"")
    assert atualizacao.disponivel(cfg) is None
    (tmp_path / "argos-99.0.0.zip").write_bytes(b"")
    assert atualizacao.disponivel(cfg)["versao"] == "99.0.0"


# --- MCP --------------------------------------------------------------------

def test_mcp_initialize_e_lista(monkeypatch):
    from argos import mcp

    saida = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(saida, encoding="utf-8"))
    mcp._tratar({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
    mcp._tratar({"jsonrpc": "2.0", "method": "notifications/initialized"})
    mcp._tratar({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    sys.stdout.flush()
    respostas = [json.loads(l) for l in saida.getvalue().decode().splitlines()]
    assert len(respostas) == 2
    assert respostas[0]["result"]["serverInfo"] == {"name": "argos", "version": __version__}
    nomes = {t["name"] for t in respostas[1]["result"]["tools"]}
    assert {"status", "logs", "iniciar", "reiniciar", "parar"} <= nomes


def test_copiar_texto_64_bits():
    # Handles de memória de 64 bits estouravam o ctypes (o botão Copiar não fazia nada)
    from argos.plataforma.windows import copiar_texto
    assert all(copiar_texto(f"https://exemplo-{i}.trycloudflare.com ção") for i in range(10))


def test_qr_svg_nitido_e_so_viewbox():
    from argos.core.celular import qr_svg
    s = qr_svg("https://feel-appropriate-consistently-municipal.trycloudflare.com")
    assert 'shape-rendering="crispEdges"' in s and "viewBox" in s and "width=" not in s.split(">")[0]


def test_ocultar_e_restaurar_comando_detectado(tmp_path):
    cmds = lambda: [{"rotulo": "npm run dev", "cmd": "npm run dev", "chave": ".|npm run dev", "sub": ""},
                    {"rotulo": "npm run preview", "cmd": "npm run preview", "chave": ".|npm run preview", "sub": ""}]
    preferencias.fixar("app", ".|npm run preview")
    preferencias.ocultar("app", ".|npm run preview")
    p = {"nome": "app", "comandos": cmds()}
    preferencias.aplicar(p)
    assert [c["chave"] for c in p["comandos"]] == [".|npm run dev"]
    assert p["ocultos"][0]["rotulo"] == "npm run preview"
    assert p["fixo"] is None  # o fixado escondido deixa de ser o principal

    preferencias.restaurar("app")
    p = {"nome": "app", "comandos": cmds()}
    preferencias.aplicar(p)
    assert len(p["comandos"]) == 2 and p["ocultos"] == []
