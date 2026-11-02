"""O app se chamava "devs": arquivos e dados antigos continuam valendo."""
import json

from argos import config
from argos.core import projetos

GRUPO = '[[servico]]\nnome = "web"\ncmd = "npm run dev"\n'


def test_devs_toml_antigo_ainda_funciona(tmp_path):
    (tmp_path / "devs.toml").write_text(GRUPO, encoding="utf-8")
    assert projetos.arquivo_grupo(tmp_path).name == "devs.toml"
    assert [s["nome"] for s in projetos.carregar_grupo(tmp_path)] == ["web"]


def test_argos_toml_tem_preferencia(tmp_path):
    (tmp_path / "devs.toml").write_text("lixo = ", encoding="utf-8")
    (tmp_path / "argos.toml").write_text(GRUPO, encoding="utf-8")
    assert projetos.arquivo_grupo(tmp_path).name == "argos.toml"
    assert projetos.carregar_grupo(tmp_path)[0]["nome"] == "web"


def test_migra_pasta_antiga(tmp_path, monkeypatch):
    antiga, nova = tmp_path / "devs", tmp_path / "argos"
    (antiga / "logs").mkdir(parents=True)
    (antiga / "app").mkdir()
    (antiga / "app" / "devs.exe").write_bytes(b"")
    log = antiga / "logs" / "x.log"
    log.write_text("ola", encoding="utf-8")
    (antiga / "config.json").write_text('{"intervalo": 7}', encoding="utf-8")
    (antiga / "registro.json").write_text(json.dumps([{"id": "x", "log": str(log)}]), encoding="utf-8")
    monkeypatch.setattr(config, "PASTA_DADOS", nova)
    monkeypatch.setattr(config, "PASTA_ANTIGA", antiga)
    monkeypatch.setattr(config, "ARQUIVO_CONFIG", nova / "config.json")

    assert config.carregar().intervalo == 7
    assert (nova / "logs" / "x.log").read_text(encoding="utf-8") == "ola"
    assert not (nova / "app").exists()  # o app antigo fica para o instalador remover
    reg = json.loads((nova / "registro.json").read_text(encoding="utf-8"))
    assert reg[0]["log"] == str(nova / "logs" / "x.log")
    # Só migra uma vez
    (antiga / "config.json").write_text('{"intervalo": 99}', encoding="utf-8")
    assert config.carregar().intervalo == 7


def test_env_dos_projetos_sem_restos_do_app():
    from argos.config import PASTA_ANTIGA, PASTA_DADOS
    from argos.core.registro import _limpar_env
    env = _limpar_env({"_PYI_ARCHIVE_FILE": "x", "Path": f"C:\\Windows;{PASTA_ANTIGA}\\app;{PASTA_DADOS}\\app;C:\\node", "A": "1"})
    assert env == {"Path": "C:\\Windows;C:\\node", "A": "1"}
