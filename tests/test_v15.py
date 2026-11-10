"""1.5: serviço avulso do argos.toml, perfil de comandos, .env escolhido, busca em logs, exportar/importar."""
import json

import pytest

from argos import config
from argos.config import Config
from argos.core import acoes, ambiente, preferencias, registro, sessoes, transporte

GRUPO = """
[[servico]]
nome = "db"
cmd = "db"

[[servico]]
nome = "api"
cmd = "api"
depois = ["db"]

[[servico]]
nome = "web"
cmd = "web"
depois = ["api"]

[[servico]]
nome = "docs"
cmd = "docs"
"""


@pytest.fixture
def dados(tmp_path, monkeypatch):
    monkeypatch.setattr(registro, "ARQUIVO_REGISTRO", tmp_path / "registro.json")
    monkeypatch.setattr(registro, "PASTA_LOGS", tmp_path / "logs")
    monkeypatch.setattr(registro, "PASTA_DADOS", tmp_path)
    monkeypatch.setattr(sessoes, "ARQUIVO", tmp_path / "sessoes.json")
    monkeypatch.setattr(preferencias, "ARQUIVO", tmp_path / "prefs.json")
    monkeypatch.setattr(config, "PASTA_DADOS", tmp_path)
    monkeypatch.setattr(config, "ARQUIVO_CONFIG", tmp_path / "config.json")
    return tmp_path


@pytest.fixture
def projeto(tmp_path):
    pasta = tmp_path / "projetos" / "loja"
    pasta.mkdir(parents=True)
    (pasta / "argos.toml").write_text(GRUPO, encoding="utf-8")
    return {"nome": "loja", "pasta": str(pasta)}


def test_subir_um_servico_sobe_so_ele_e_o_que_ele_precisa(dados, projeto, monkeypatch):
    iniciados = []

    def iniciar(cmd, cwd, env, **k):
        iniciados.append(k["nome"])
        return {"id": k["nome"], "pid": 1, "log": ""}, None

    monkeypatch.setattr(registro, "iniciar", iniciar)
    r = acoes.subir_projeto(Config(), projeto, so="api")
    assert r.ok and iniciados == ["db", "api"]  # nem "web" (depende dele) nem "docs" (sem relação)
    assert not acoes.subir_projeto(Config(), projeto, so="nao-existe").ok


def test_estado_e_parada_de_um_servico(dados, projeto, monkeypatch):
    monkeypatch.setattr(registro, "listar", lambda: [{"id": "x1", "nome": "api", "projeto": "loja", "vivo": True, "pid": 4321}])
    estado = {s["nome"]: s for s in acoes.estado_servicos(Config(), projeto)}
    assert estado["api"]["rodando"] and estado["api"]["pid"] == 4321 and not estado["db"]["rodando"]
    assert estado["web"]["depois"] == ["api"]
    parados = []
    monkeypatch.setattr(acoes, "encerrar", lambda pid: parados.append(pid) or acoes.Resultado(True, "ok"))
    assert acoes.parar_servico(Config(), projeto, "api").ok and parados == [4321]
    assert acoes.parar_servico(Config(), projeto, "db").msg == "db já estava parado."


def test_arquivo_env_escolhido_vai_no_ambiente(dados, projeto):
    back = pytest.importorskip("pathlib").Path(projeto["pasta"]) / "backend"
    back.mkdir()
    (back / ".env").write_text("API=dev\nSO_DEV=1\n", encoding="utf-8")
    (back / ".env.staging").write_text("API=staging\n", encoding="utf-8")
    (back / ".env.example").write_text("API=\nSO_DEV=\nFALTA=\n", encoding="utf-8")
    a = ambiente.analisar_pasta(back, "backend")
    assert [f["nome"] for f in a["arquivos"]] == [".env", ".env.staging"] and a["faltando"] == ["FALTA"]
    assert ambiente.variaveis_escolhidas(projeto, "backend") == {}
    preferencias.definir_arquivo_env("loja", "backend", ".env.staging")
    assert ambiente.variaveis_escolhidas(projeto, "backend") == {"API": "staging"}
    assert ambiente.variaveis_escolhidas(projeto, "") == {}  # a escolha é por pasta
    preferencias.definir_arquivo_env("loja", "backend", None)
    assert ambiente.variaveis_escolhidas(projeto, "backend") == {}
    assert ambiente.arquivo_valido(str(back / ".env.staging"), [str(back.parent.parent)])
    assert not ambiente.arquivo_valido(str(back / "segredos.txt"), [str(back.parent.parent)])


def test_busca_nos_logs_do_projeto(dados):
    logs = dados / "logs"
    logs.mkdir()
    (logs / "a.log").write_bytes(b"ok\n\x1b[31mError: conexao recusada\x1b[0m\nok\n")
    (logs / "b.log").write_bytes(b"tudo certo\n")
    (logs / "c.log").write_bytes(b"ERROR de outro projeto\n")
    registro._gravar([
        {"id": "a", "nome": "api", "projeto": "Loja", "pid": 1, "criado": 0, "log": str(logs / "a.log"), "parado_em": 9e12},
        {"id": "b", "nome": "web", "projeto": "loja", "pid": 1, "criado": 0, "log": str(logs / "b.log"), "parado_em": 9e12},
        {"id": "c", "nome": "x", "projeto": "outro", "pid": 1, "criado": 0, "log": str(logs / "c.log"), "parado_em": 9e12}])
    achados = registro.buscar_nos_logs("loja", "error")
    assert [(s["nome"], s["linhas"]) for s in achados] == [("api", ["Error: conexao recusada"])]
    assert registro.buscar_nos_logs("loja", "  ") == []


def test_perfil_de_comandos_inicia_pelos_projetos(dados, monkeypatch):
    from argos.core import projetos as proj

    p = {"nome": "loja", "pasta": "x", "comandos": [{"chave": "web|npm run dev", "rotulo": "npm run dev", "sub": "web", "tipo": "processo"}]}
    monkeypatch.setattr(proj, "buscar", lambda cfg, nome: p if nome == "loja" else None)
    iniciados = []
    monkeypatch.setattr(acoes, "iniciar_comando", lambda cfg, pr, c: iniciados.append(c["chave"]) or acoes.Resultado(True, "ok"))
    sessoes.criar_perfil("Trabalho", [{"projeto": "loja", "chave": "web|npm run dev", "nome": "web: npm run dev"},
                                      {"projeto": "sumiu", "chave": ".|x", "nome": "x"}])
    perfil = sessoes.listar()[0]
    assert perfil["nome"] == "Trabalho" and perfil["processos"] == 2 and sessoes.pendente() is None
    ok, msg = sessoes.retomar("trabalho")
    assert not ok and iniciados == ["web|npm run dev"] and "não existe mais" in msg
    # Já rodando: não inicia de novo
    monkeypatch.setattr(registro, "listar", lambda: [{"vivo": True, "projeto": "loja", "nome": "web: npm run dev"}])
    sessoes.retomar("trabalho")
    assert iniciados == ["web|npm run dev"]


def test_exportar_e_importar_sem_variaveis(dados, tmp_path):
    preferencias.fixar("loja", "web|npm run dev")
    preferencias.reservar_porta("loja", "web|npm run dev", 5180)
    sessoes.criar_perfil("trabalho", [{"projeto": "loja", "chave": "web|npm run dev", "nome": "web"}])
    est = {"unidades": [], "docker": {"containers": [{"estado": "running", "id": "c1", "nome": "db", "projeto": "loja"}]}}
    sessoes.salvar(est, "manual", "capturado")
    cfg = Config(pastas_projetos=[str(tmp_path)], intervalo=7, limite_ram_mb=900)
    arq = tmp_path / "argos-config.json"
    assert transporte.gravar(cfg, str(arq))[0]
    exportado = json.loads(arq.read_text(encoding="utf-8"))
    assert [p["nome"] for p in exportado["perfis"]] == ["trabalho"]  # o capturado depende desta máquina
    assert "env" not in arq.read_text(encoding="utf-8") and exportado["opcoes"]["intervalo"] == 7

    # "outra máquina": dados vazios
    (dados / "prefs.json").unlink()
    (dados / "sessoes.json").unlink()
    novo = Config(pastas_projetos=["C:\\nao-existe"])
    ok, msg = transporte.importar(novo, str(arq))
    assert ok, msg
    assert novo.intervalo == 7 and novo.limite_ram_mb == 900 and str(tmp_path) in novo.pastas_projetos
    assert preferencias.porta_reservada("loja", "web|npm run dev") == 5180
    assert [s["nome"] for s in sessoes.listar()] == ["trabalho"]
    assert not transporte.importar(novo, str(dados / "registro.json"))[0]
