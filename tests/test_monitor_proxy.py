"""Monitor (quedas, reinício automático, limite de memória), proxy de nomes, MCP e ponte do painel."""
import http.client
import http.server
import socket
import threading
import time

import pytest

from argos import mcp
from argos.app import monitor as mon
from argos.app.api import Api
from argos.app.proxy import Proxy, calcular_rotas
from argos.config import Config
from argos.core import acoes


# --- monitor -----------------------------------------------------------------

@pytest.fixture
def m(monkeypatch):
    monitor = mon.Monitor(Config())
    reinicios = []
    monkeypatch.setattr(mon.registro, "reiniciar", lambda e, por_queda=False: reinicios.append(e["id"]))
    monkeypatch.setattr(mon.registro, "ultimas_linhas", lambda e, n=8: ["Error: porta em uso"])
    monitor.reinicios = reinicios
    return monitor


def _entrada(**campos):
    return {"id": "a", "pid": 10, "vivo": False, "nome": "api", "projeto": "loja", "reinicios": [], **campos}


def test_queda_sem_reinicio_automatico_so_avisa(m):
    m._vivos_antes = {"a": {"pid": 10}}
    m._quedas({"a": _entrada()})
    assert m.reinicios == [] and [e["tipo"] for e in m.eventos] == ["caiu"]
    assert "porta em uso" in m.eventos[0]["msg"]


def test_queda_com_auto_reinicia_e_desiste_na_terceira(m):
    m._vivos_antes = {"a": {"pid": 10}}
    m._quedas({"a": _entrada(auto=True)})
    assert m.reinicios == ["a"] and m.eventos[-1]["tipo"] == "reiniciado"
    m._vivos_antes = {"a": {"pid": 10}}
    agora = time.time()
    m._quedas({"a": _entrada(auto=True, reinicios=[agora - 30, agora - 20, agora - 10])})
    assert m.reinicios == ["a"] and m.eventos[-1]["tipo"] == "desisti"


def test_parada_pelo_usuario_ou_reinicio_nao_e_queda(m):
    m._vivos_antes = {"a": {"pid": 10}, "b": {"pid": 20}}
    m._quedas({"a": _entrada(manual=True), "b": _entrada(id="b", pid=21)})  # b reiniciou: PID novo
    assert not m.eventos and m.reinicios == []


def test_limite_de_memoria_avisa_uma_vez(m):
    m.cfg.limite_ram_mb = 500
    u = {"pid": 1, "inicio": 100.0, "nome": "web", "projeto": "loja", "categoria": "projeto", "ram_mb": 800, "gerenciado": "a"}
    m._limite_memoria(u, "1-100")
    m._limite_memoria(u, "1-100")
    assert len(m.eventos) == 1 and m.eventos[0]["acao"]["tipo"] == "reiniciar"
    m._limite_memoria({**u, "ram_mb": 300}, "2-100")
    assert len(m.eventos) == 1


def test_avisos_de_processos_mortos_sao_esquecidos(m):
    m._avisados = {"orfao:1-100", "longo:9-9", "ferr:mcp:2"}
    m._uso = {"1-100": 1.0, "9-9": 2.0}
    m._prontos = {"a:1", "z:2"}
    m._esquecer_mortos({"unidades": [{"pid": 1, "inicio": 100.0}]}, {"a": {}})
    assert m._avisados == {"orfao:1-100", "ferr:mcp:2"} and m._uso == {"1-100": 1.0} and m._prontos == {"a:1"}


def test_intervalo_invalido_nao_derruba_o_laco(m, monkeypatch):
    m.cfg.intervalo = "3s"
    voltas = []

    def estado(cfg):
        voltas.append(1)
        if len(voltas) == 2:
            raise SystemExit  # sai do laço na segunda volta
        return {"unidades": [], "ferramentas": [], "docker": {"containers": []}}

    monkeypatch.setattr(mon.acoes, "estado", estado)
    monkeypatch.setattr(mon.registro, "listar", lambda: [])
    m._acordar.wait = lambda t: None
    with pytest.raises(SystemExit):
        m._laco()
    assert len(voltas) == 2


# --- proxy -------------------------------------------------------------------

def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_rotas_por_tipo_de_porta():
    est = {"unidades": [
        {"categoria": "projeto", "projeto": "Minha Loja", "portas": [5173, 8000], "portas_tipo": {5173: "site", 8000: "api"},
         "portas_hosts": {5173: ["::1"], 8000: ["127.0.0.1"]}},
        {"categoria": "ferramenta", "projeto": "x", "portas": [9000], "portas_tipo": {}},
        {"categoria": "projeto", "projeto": "", "portas": [7000], "portas_tipo": {}},
    ]}
    rotas = calcular_rotas(est)
    assert rotas["minha-loja.localhost"] == ("::1", 5173)
    assert rotas["api.minha-loja.localhost"] == ("127.0.0.1", 8000)
    assert rotas["8000.minha-loja.localhost"] == ("127.0.0.1", 8000)
    assert not any("x." in h or h.startswith("7000") for h in rotas)


def test_proxy_encaminha_pelo_nome():
    class Servidor(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            corpo = f"ola de {self.headers['Host']}".encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *a):
            pass

    destino = http.server.HTTPServer(("127.0.0.1", 0), Servidor)
    threading.Thread(target=destino.serve_forever, daemon=True).start()
    proxy = Proxy(_porta_livre())
    proxy.rotas = {"loja.localhost": ("127.0.0.1", destino.server_address[1])}
    proxy.iniciar()
    for _ in range(100):
        if proxy.porta:
            break
        time.sleep(0.05)
    assert proxy.porta

    def pedir(host):
        c = http.client.HTTPConnection("127.0.0.1", proxy.porta, timeout=5)
        c.request("GET", "/", headers={"Host": host})
        r = c.getresponse()
        return r.status, r.read().decode()

    try:
        assert pedir("loja.localhost") == (200, "ola de loja.localhost")
        assert proxy.ultimo_uso.get(destino.server_address[1])
        status, corpo = pedir("nao-existe.localhost")
        assert status == 404 and "loja.localhost" in corpo
        assert pedir("localhost")[0] == 200
    finally:
        destino.shutdown()


# --- MCP e ponte do painel -----------------------------------------------------

def test_mcp_nao_encerra_pid_que_nao_e_de_desenvolvimento(monkeypatch):
    encerrados = []
    monkeypatch.setattr(acoes, "pid_de_dev", lambda cfg, pid: 77 if pid == 78 else None)
    monkeypatch.setattr(acoes, "encerrar", lambda pid: encerrados.append(pid) or acoes.Resultado(True, "ok"))
    assert "não é um processo de desenvolvimento" in mcp.t_parar({"pid": 4})
    assert encerrados == []
    mcp.t_parar({"pid": 78})  # filho de uma unidade: encerra a raiz dela
    assert encerrados == [77]


def test_ponte_so_abre_enderecos_e_pastas(tmp_path, monkeypatch):
    abertos = []
    monkeypatch.setattr("argos.app.api.abrir_url", abertos.append)
    monkeypatch.setattr("argos.app.api.abrir_pasta", abertos.append)
    api = Api(Config(), monitor=None)
    arquivo = tmp_path / "virus.exe"
    arquivo.write_bytes(b"")
    assert not api.abrir("url", str(arquivo))["ok"]
    assert not api.abrir("url", "file:///C:/Windows/System32/calc.exe")["ok"]
    assert not api.abrir("pasta", str(arquivo))["ok"]
    assert api.abrir("url", "http://localhost:5173")["ok"] and api.abrir("pasta", str(tmp_path))["ok"]
    assert abertos == ["http://localhost:5173", str(tmp_path)]


def test_ponte_limita_o_que_roda_como_administrador(monkeypatch):
    pedidos = []
    monkeypatch.setattr("argos.app.api.executar_como_admin", lambda args: pedidos.append(args) or True)
    api = Api(Config(), monitor=type("M", (), {"atualizar_agora": lambda self: None})())
    assert not api.admin(["rodar", "format", "c:"])["ok"]
    assert not api.admin(["matar", "1 & calc"])["ok"]
    assert api.admin(["matar", "1234"])["ok"] and pedidos == [["matar", "1234", "-f"]]
