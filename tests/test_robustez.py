"""Encerramento gracioso, variáveis cifradas, sessões com falha, subida dupla e config inválido."""
import json
import sys
import time

import pytest

from argos import config
from argos.core import acoes, arquivo, historico, registro, segredo, sessoes

SERVIDOR = """
import pathlib, signal, sys, time
def sair(*_):
    pathlib.Path(sys.argv[1]).write_text("fechou direito")
    sys.exit(0)
signal.signal(signal.SIGBREAK, sair)
pathlib.Path(sys.argv[2]).write_text("pronto")
while True:
    time.sleep(0.05)
"""


@pytest.fixture
def dados(tmp_path, monkeypatch):
    """Registro, logs e sessões numa pasta temporária."""
    monkeypatch.setattr(registro, "ARQUIVO_REGISTRO", tmp_path / "registro.json")
    monkeypatch.setattr(registro, "PASTA_LOGS", tmp_path / "logs")
    monkeypatch.setattr(registro, "PASTA_DADOS", tmp_path)
    monkeypatch.setattr(sessoes, "ARQUIVO", tmp_path / "sessoes.json")
    return tmp_path


def _esperar(condicao, segundos=10):
    limite = time.time() + segundos
    while time.time() < limite:
        if condicao():
            return True
        time.sleep(0.05)
    return False


def test_parar_deixa_o_servidor_fechar_sozinho(dados):
    script, fechou, pronto = dados / "servidor.py", dados / "fechou.txt", dados / "pronto.txt"
    script.write_text(SERVIDOR, encoding="utf-8")
    e, _ = registro.iniciar(f'"{sys.executable}" "{script}" "{fechou}" "{pronto}"', str(dados), dict(__import__("os").environ),
                            shell=True, nome="servidor de teste")
    try:
        assert _esperar(pronto.exists), "o servidor de teste não subiu"
        r = acoes.encerrar(e["pid"])
        assert r.ok, r.msg
        assert fechou.exists() and fechou.read_text() == "fechou direito"  # com kill direto o arquivo não existiria
        assert not registro.vivo(e)
    finally:
        registro.encerrar_arvore(e["pid"])


def test_variaveis_ficam_cifradas_no_disco(dados):
    registro._gravar([{"id": "a1", "pid": 1, "criado": 0, "nome": "x", "log": "", "env": {"API_KEY": "segredo-123", "A": "1"}}])
    bruto = (dados / "registro.json").read_text(encoding="utf-8")
    assert "segredo-123" not in bruto and "API_KEY" not in bruto and "env_p" in bruto
    assert registro._ler()[0]["env"] == {"API_KEY": "segredo-123", "A": "1"}


def test_registro_antigo_em_texto_puro_ainda_abre(dados):
    (dados / "registro.json").write_text(json.dumps([{"id": "a1", "pid": 1, "criado": 0, "env": {"A": "1"}}]), encoding="utf-8")
    assert registro._ler()[0]["env"] == {"A": "1"}


def test_variaveis_da_sessao_do_assistente_nao_vao_para_os_projetos():
    env = registro._limpar_env({"CLAUDE_CODE_MESSAGING_TOKEN": "t", "CLAUDECODE": "1", "ANTHROPIC_API_KEY": "do-projeto", "A": "1"})
    assert env == {"ANTHROPIC_API_KEY": "do-projeto", "A": "1"}
    assert segredo.abrir("isto-nao-e-cifrado") == {}


def test_sessao_com_falha_continua_pendente(dados, monkeypatch):
    est = {"unidades": [], "docker": {"containers": [{"estado": "running", "id": "abc", "nome": "banco", "projeto": "loja"}]}}
    monkeypatch.setattr(sessoes.docker, "instalado", lambda: False)
    monkeypatch.setattr(sessoes.docker, "iniciar", lambda ids: (False, "sumiu"))
    s = sessoes.salvar(est, "modo jogo")
    ok, msg = sessoes.retomar()
    assert not ok and "banco" in msg
    p = sessoes.pendente()
    assert p and p["id"] == s["id"] and p["falhas"] == ["banco"]
    monkeypatch.setattr(sessoes.docker, "iniciar", lambda ids: (True, ""))
    assert sessoes.retomar()[0] and sessoes.pendente() is None


def test_perfil_com_nome_fica_guardado_e_e_substituido(dados):
    est = {"unidades": [], "docker": {"containers": [{"estado": "running", "id": "abc", "nome": "banco", "projeto": "loja"}]}}
    sessoes.salvar(est, "manual", "Trabalho")
    for _ in range(sessoes.MANTER + 3):
        sessoes.salvar(est, "modo jogo")
    sessoes.salvar(est, "manual", "trabalho")
    lista = sessoes.listar()
    assert [s["nome"] for s in lista if s["nome"]] == ["trabalho"]
    assert sum(not s["nome"] for s in lista) == sessoes.MANTER
    assert sessoes.pendente()["nome"] == ""
    assert sessoes.apagar(next(s["id"] for s in lista if s["nome"]))


def test_subir_o_mesmo_projeto_duas_vezes_e_recusado(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PASTA_DADOS", tmp_path)
    primeira = acoes._marca_subida("Loja")
    assert primeira and acoes._marca_subida("loja") is None
    primeira.unlink()
    assert acoes._marca_subida("loja")


def test_trava_nao_segue_sem_trava(tmp_path, monkeypatch):
    monkeypatch.setattr(arquivo, "ESPERA_MAXIMA", 0.3)
    alvo = tmp_path / "x.json"
    with arquivo.trava(alvo):
        with pytest.raises(arquivo.TravaOcupada):
            with arquivo.trava(alvo):
                pass
    with arquivo.trava(alvo):  # liberada depois de sair
        arquivo.gravar(alvo, {"a": 1})
    assert arquivo.ler(alvo, None) == {"a": 1}


def test_config_editado_a_mao_com_tipo_errado_usa_o_padrao(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PASTA_ANTIGA", tmp_path / "nao-existe")
    monkeypatch.setattr(config, "ARQUIVO_CONFIG", tmp_path / "config.json")
    (tmp_path / "config.json").write_text(json.dumps(
        {"intervalo": "3s", "alerta_horas": "2.5", "proxy": "sim", "pastas_projetos": "C:\\x", "git_fetch_minutos": -5,
         "ocioso_horas": 1}), encoding="utf-8")
    cfg = config.carregar()
    padrao = config.Config()
    assert cfg.intervalo == padrao.intervalo and cfg.proxy is True and cfg.pastas_projetos == padrao.pastas_projetos
    assert cfg.alerta_horas == 2.5 and cfg.git_fetch_minutos == padrao.git_fetch_minutos and cfg.ocioso_horas == 1.0


def test_historico_semanal_nao_conta_em_dobro(tmp_path, monkeypatch):
    monkeypatch.setattr(historico, "ARQUIVO_HISTORICO", tmp_path / "h.jsonl")
    monkeypatch.setattr(historico, "PASTA_DADOS", tmp_path)
    agora = time.time()
    back = {"pid": 1, "nome": "api", "projeto": "loja", "inicio": agora - 3600}
    front = {"pid": 2, "nome": "web", "projeto": "loja", "inicio": agora - 1800}
    for u in (back, front):
        historico.registrar("inicio", u, quando=u["inicio"])
        historico.registrar("inicio", u, quando=u["inicio"])  # repetido, como acontecia a cada abertura
    historico.registrar("fim", back, quando=agora - 600)
    assert set(historico.abertos()) == {historico.chave(front)}
    semana = historico.da_semana([front])
    assert len(semana) == 1 and semana[0]["projeto"] == "loja"
    assert 3500 < semana[0]["total"] < 3700  # 1h corrida, e não 1h + 30min somados
    historico.podar()
    assert len((tmp_path / "h.jsonl").read_text(encoding="utf-8").splitlines()) == 3
