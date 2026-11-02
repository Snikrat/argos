import json

from argos.config import Config
from argos.core import projetos
from argos.core.coleta import projeto_da_pasta, rotulo_comando


def test_rotulo_npm():
    args = [r"C:\Program Files\nodejs\node.exe", r"C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js", "run", "dev"]
    assert rotulo_comando(args) == "npm run dev"


def test_rotulo_cmd_c():
    assert rotulo_comando(["C:\\Windows\\system32\\cmd.exe", "/d", "/s", "/c", "vite --port 4000"]) == "vite --port 4000"


def test_rotulo_python_script():
    assert rotulo_comando([r"C:\x\python.exe", r"C:\proj\app\main.py", "--debug"]) == "python main.py --debug"


def test_rotulo_url_nao_encurta():
    assert rotulo_comando(["node", "server.js", "http://a/b"]) == "node server.js http://a/b"


def test_projeto_da_pasta():
    cfg = Config(pastas_projetos=[r"C:\Users\x\Desktop\projetos"])
    assert projeto_da_pasta(r"C:\Users\x\Desktop\projetos\loja\src", cfg) == ("loja", r"C:\Users\x\Desktop\projetos\loja")
    assert projeto_da_pasta(r'"c:\users\x\desktop\projetos\loja\a.py"', cfg)[0] == "loja"
    assert projeto_da_pasta(r"C:\outro\lugar", cfg) is None


def test_porta_explicita():
    assert projetos.porta_explicita("vite --port 4000") == 4000
    assert projetos.porta_explicita("next dev -p 3001") == 3001
    assert projetos.porta_explicita("cross-env PORT=8081 node s.js") == 8081
    assert projetos.porta_explicita("python manage.py runserver 0.0.0.0:9000") == 9000
    assert projetos.porta_explicita("vite") is None


def test_detectar_node_vite(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "scripts": {"dev": "vite", "preview": "vite preview", "build": "vite build"},
        "devDependencies": {"vite": "^5"},
    }))
    (tmp_path / "pnpm-lock.yaml").write_text("")
    p = projetos.detectar(tmp_path)
    assert p["tipos"] == ["node"]
    assert [(c["cmd"], c["porta"]) for c in p["comandos"]] == [("pnpm run dev", 5173), ("pnpm run preview", 4173)]


def test_detectar_env_port(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"start": "node index.js"}}))
    (tmp_path / ".env").write_text("PORT=4500\n")
    assert projetos.detectar(tmp_path)["comandos"][0]["porta"] == 4500


def test_detectar_compose_e_django(tmp_path):
    (tmp_path / "docker-compose.yml").write_text("services:\n  db:\n    ports:\n      - \"5433:5432\"\n")
    (tmp_path / "manage.py").write_text("")
    p = projetos.detectar(tmp_path)
    assert set(p["tipos"]) == {"docker", "python"}
    tipos = {c["tipo"]: c for c in p["comandos"]}
    assert tipos["compose"]["porta"] == 5433
    assert any(c["porta"] == 8000 for c in p["comandos"])


def test_env_do_devs_nao_vaza_para_projetos():
    from argos.config import PASTA_DADOS
    from argos.core.registro import _limpar_env

    vazado = {"UV_PROJECT_ENVIRONMENT": str(PASTA_DADOS / "venv-dev"), "PATH": "x"}
    assert _limpar_env(vazado) == {"PATH": "x"}
    proprio = {"UV_PROJECT_ENVIRONMENT": r"D:\minha\venv"}
    assert _limpar_env(proprio) == proprio


def test_tamanho_pasta(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.bin").write_bytes(b"0" * 1000)
    (tmp_path / "y.bin").write_bytes(b"0" * 24)
    assert projetos.tamanho_pasta(str(tmp_path)) == 1024
