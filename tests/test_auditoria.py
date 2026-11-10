"""Regressões dos problemas comprovados na auditoria."""
import os

import psutil

from argos.app.api import Api
from argos.config import Config
from argos.core import acoes, ambiente


def _entrada(log, log_de):
    return {"pid": os.getpid(), "criado": psutil.Process().create_time(), "log": str(log), "log_de": log_de}


def test_pronto_por_log_ignora_execucoes_anteriores(tmp_path):
    log = tmp_path / "api.log"
    log.write_bytes(b"execucao antiga\nApplication startup complete\n")
    e = _entrada(log, log.stat().st_size)
    ok, _ = acoes.esperar_pronto("log:Application startup complete", e, timeout=1.2)
    assert not ok  # o texto só existe na execução anterior
    with open(log, "ab") as f:
        f.write(b"subindo de novo\nApplication startup complete\n")
    assert acoes.esperar_pronto("log:Application startup complete", e, timeout=2)[0]


def test_salvar_env_mantem_o_fim_de_linha(tmp_path):
    lf, crlf, novo = tmp_path / ".env", tmp_path / ".env.local", tmp_path / ".env.development"
    lf.write_bytes(b"A=1\nB=2\n")
    crlf.write_bytes(b"A=1\r\nB=2\r\n")
    ambiente.gravar(lf, "A=1\nB=3\n")
    ambiente.gravar(crlf, "A=1\nB=3\n")
    ambiente.gravar(novo, "A=1\r\nB=3\n")
    assert lf.read_bytes() == b"A=1\nB=3\n"
    assert crlf.read_bytes() == b"A=1\r\nB=3\r\n"
    assert novo.read_bytes() == b"A=1\nB=3\n"


def test_completar_env_mantem_o_fim_de_linha(tmp_path):
    (tmp_path / ".env.example").write_bytes(b"A=\nB=\nC=padrao\n")
    ok, _ = ambiente.completar(str(tmp_path))
    assert ok and (tmp_path / ".env").read_bytes() == b"A=\nB=\nC=padrao\n"
    (tmp_path / ".env").write_bytes(b"A=1\nB=2\n")
    ambiente.completar(str(tmp_path))
    conteudo = (tmp_path / ".env").read_bytes()
    assert b"\r" not in conteudo and conteudo.startswith(b"A=1\nB=2\n") and conteudo.endswith(b"C=padrao\n")


def test_apagar_dependencia_recusa_caminho_que_sai_dos_projetos(tmp_path):
    projetos, fora = tmp_path / "projetos", tmp_path / "outro"
    (projetos / "app" / "node_modules").mkdir(parents=True)
    (fora / "node_modules").mkdir(parents=True)
    api = Api(Config(pastas_projetos=[str(projetos)]), monitor=None)
    r = api.apagar_dependencia(str(projetos / "app" / ".." / ".." / "outro" / "node_modules"))
    assert not r["ok"] and (fora / "node_modules").is_dir()
    assert api.apagar_dependencia(str(projetos / "app" / "node_modules"))["ok"]
    assert not (projetos / "app" / "node_modules").exists()
