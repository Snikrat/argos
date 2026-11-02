"""Coleta em segundo plano: estado, saúde das URLs, histórico, memória e avisos."""

from __future__ import annotations

import http.client
import logging
import threading
import time
from collections import deque
from typing import Callable

from argos.config import Config
from argos.core import acoes, historico, registro

log = logging.getLogger("argos")

# Não fazem sentido receber uma requisição HTTP
SEM_HTTP = {"postgres", "mysqld", "redis-server", "mongod"}

MAX_REINICIOS = 3            # reinícios automáticos...
JANELA_REINICIOS = 600       # ...dentro de 10 minutos
AMOSTRA_RAM = 15             # segundos entre amostras de memória
PONTOS_RAM = 120             # 30 minutos de histórico
PRONTO_ATE = 600             # só avisa "pronto" nos primeiros 10 min


def testar_http(porta: int, hosts: list[str] | None = None) -> tuple[str, str]:
    """(estado, conteúdo).

    estado: 'ok' (respondeu HTTP), 'erro' (HTTP 5xx), 'tcp' (aberta mas não é HTTP) ou 'off'.
    conteúdo: 'site' (respondeu HTML), 'api' (respondeu JSON) ou ''.
    Só testa os endereços onde a porta escuta: nos outros o Windows pode demorar até dar timeout.
    """
    for host in hosts or ["127.0.0.1", "::1"]:
        conn = http.client.HTTPConnection(host, porta, timeout=2)
        try:
            conn.request("GET", "/", headers={"User-Agent": "argos-saude", "Accept": "text/html,*/*",
                                               "Host": f"localhost:{porta}"})
            r = conn.getresponse()
            tipo = (r.getheader("Content-Type") or "").lower()
            conteudo = "site" if "html" in tipo else "api" if "json" in tipo else ""
            return ("erro" if r.status >= 500 else "ok"), conteudo
        except (ConnectionRefusedError, TimeoutError):
            continue
        except OSError as e:
            if getattr(e, "winerror", None) in (10061, 10049):
                continue
            return "tcp", ""
        except http.client.HTTPException:
            return "tcp", ""
        finally:
            conn.close()
    return "off", ""


def vazando(pontos: list[int], idade: float) -> bool:
    """Memória só subindo: o final da série bem acima do começo, há pelo menos 20 min."""
    if idade < 20 * 60 or len(pontos) < 40:
        return False
    terco = len(pontos) // 3
    inicio, meio, fim = (sum(p) / len(p) for p in (pontos[:terco], pontos[terco:2 * terco], pontos[2 * terco:]))
    return inicio <= meio <= fim and fim > inicio * 1.5 and fim - inicio > 300


class Monitor:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.estado: dict | None = None
        self.saude: dict[int, str] = {}
        self.conteudo: dict[int, str] = {}
        self.ao_mudar: Callable[[dict], None] = lambda est: None
        self.notificar: Callable[[str, str], None] = lambda titulo, msg: None
        self.janela_visivel: Callable[[], bool] = lambda: False
        self.eventos: deque[dict] = deque(maxlen=60)
        self._seq = 0
        self._acordar = threading.Event()
        self._vistos: dict[str, dict] = {}
        self._avisados: set[str] = set()
        self._vivos_antes: dict[str, dict] = {}
        self._prontos: set[str] = set()
        self._ram: dict[str, deque] = {}
        self._ultima_amostra = 0.0
        self._primeira = True
        self.proxy = None                     # Proxy de nomes (app)
        self._uso: dict[str, float] = {}       # unidade -> último uso visto
        self._inicio = time.time()
        self._git_receber: dict[str, int] = {}
        self.atualizacao: dict | None = None

    def iniciar(self) -> None:
        historico.podar()
        threading.Thread(target=self._laco, daemon=True, name="monitor").start()
        threading.Thread(target=self._laco_saude, daemon=True, name="saude").start()
        threading.Thread(target=self._laco_git, daemon=True, name="git-fetch").start()
        threading.Thread(target=self._laco_atualizacao, daemon=True, name="atualizacao").start()

    def atualizar_agora(self) -> None:
        self._acordar.set()

    def emitir(self, tipo: str, titulo: str, msg: str, *, nivel: str = "info", url: str | None = None,
               id_: str | None = None, windows: bool | None = None, acao: dict | None = None) -> None:
        """Evento para o painel (aviso com botão) e, se a janela estiver escondida, para o Windows.

        `acao` vira um botão no aviso, ex: {"rotulo": "Parar", "tipo": "encerrar", "pid": 123}.
        """
        self._seq += 1
        self.eventos.append({"seq": self._seq, "tipo": tipo, "titulo": titulo, "msg": msg, "acao": acao,
                             "nivel": nivel, "url": url, "id": id_, "ts": time.time()})
        if windows if windows is not None else not self.janela_visivel():
            self.notificar(titulo, msg)

    def eventos_desde(self, seq: int) -> list[dict]:
        return [e for e in self.eventos if e["seq"] > seq]

    # --- laço principal ----------------------------------------------------

    def _laco(self) -> None:
        while True:
            try:
                est = acoes.estado(self.cfg)
                self._tipos_portas(est)
                regs = {e["id"]: e for e in registro.listar()}
                self._quedas(regs)
                self._pronto(est, regs)
                self._memoria(est)
                self._ociosos(est)
                self._historico(est)
                self._avisos(est)
                for u in est["unidades"]:
                    if u["gerenciado"] in regs:
                        u["auto"] = bool(regs[u["gerenciado"]].get("auto"))
                if self.proxy:
                    from argos.app.proxy import calcular_rotas
                    self.proxy.rotas = calcular_rotas(est)
                    est["proxy"] = {"porta": self.proxy.porta,
                                    "rotas": {h: p for h, (_, p) in self.proxy.rotas.items()}}
                est["atualizacao"] = self.atualizacao
                est["ultimo_evento"] = self._seq
                self.estado = est
                self.ao_mudar(est)
            except Exception:
                log.exception("falha na coleta")
            self._primeira = False
            self._acordar.wait(max(1, self.cfg.intervalo))
            self._acordar.clear()

    def _laco_saude(self) -> None:
        while True:
            est = self.estado
            if est:
                alvos = {p: u["portas_hosts"].get(p) for u in est["unidades"]
                         if u["categoria"] != "ferramenta" and u["programa"] not in SEM_HTTP for p in u["portas"]}
                saude, conteudo = {}, {}
                for p, hosts in sorted(alvos.items()):
                    saude[p], conteudo[p] = testar_http(p, hosts)
                self.saude, self.conteudo = saude, conteudo
            time.sleep(8)

    def _tipos_portas(self, est: dict) -> None:
        """Completa o tipo (site/api) das portas sem pista no comando com o que elas responderam."""
        for u in est["unidades"]:
            for p in u["portas"]:
                if not u["portas_tipo"].get(p):
                    u["portas_tipo"][p] = self.conteudo.get(p, "")
            # Site primeiro: é o que se abre no navegador e no celular
            u["portas"].sort(key=lambda p: (u["portas_tipo"].get(p) != "site", p))

    # --- quedas e reinício automático --------------------------------------

    def _quedas(self, regs: dict[str, dict]) -> None:
        vivos = {i: e for i, e in regs.items() if e["vivo"]}
        for id_, antes in self._vivos_antes.items():
            if id_ in vivos:
                continue
            e = regs.get(id_)
            # Sumiu do registro, foi reiniciado (PID novo) ou o usuário parou: não é queda
            if not e or e.get("manual") or e["pid"] != antes["pid"]:
                continue
            linhas = registro.ultimas_linhas(e, 6)
            resumo = linhas[-1] if linhas else "sem saída no log"
            if e.get("auto"):
                recentes = [t for t in e.get("reinicios", []) if time.time() - t < JANELA_REINICIOS]
                if len(recentes) < MAX_REINICIOS:
                    try:
                        registro.reiniciar(e, por_queda=True)
                        self.emitir("reiniciado", f"{e['nome']} caiu e foi reiniciado",
                                    f"{e['projeto'] or 'sem projeto'}: {resumo}", nivel="aviso", id_=id_)
                        continue
                    except Exception:
                        log.exception("falha no reinício automático")
                self.emitir("desisti", f"{e['nome']} caiu {MAX_REINICIOS}x seguidas",
                            f"Parei de reiniciar. Último erro: {resumo}", nivel="erro", id_=id_, windows=True)
                continue
            self.emitir("caiu", f"{e['nome']} caiu", f"{e['projeto'] or 'sem projeto'}: {resumo}",
                        nivel="erro", id_=id_, windows=True)
        self._vivos_antes = vivos

    # --- "pronto em localhost:5173" ------------------------------------------

    def _pronto(self, est: dict, regs: dict[str, dict]) -> None:
        agora = time.time()
        for u in est["unidades"]:
            e = regs.get(u["gerenciado"] or "")
            if not e or not u["portas"]:
                continue
            chave = f"{e['id']}:{int(e['inicio'])}"
            if chave in self._prontos:
                continue
            self._prontos.add(chave)
            if agora - e["inicio"] > PRONTO_ATE or self._primeira:
                continue
            porta = u["portas"][0]
            url = f"http://localhost:{porta}"
            self.emitir("pronto", f"{e['nome']} pronto", f"{e['projeto'] or 'sem projeto'} em localhost:{porta}",
                        url=url, id_=e["id"])

    # --- memória ------------------------------------------------------------

    def _memoria(self, est: dict) -> None:
        agora = time.time()
        amostrar = agora - self._ultima_amostra >= AMOSTRA_RAM
        if amostrar:
            self._ultima_amostra = agora
        vivos = set()
        for u in est["unidades"]:
            chave = historico.chave(u)
            vivos.add(chave)
            serie = self._ram.setdefault(chave, deque(maxlen=PONTOS_RAM))
            if amostrar or not serie:
                serie.append(u["ram_mb"])
            u["ram_hist"] = list(serie)
            u["vazando"] = vazando(u["ram_hist"], agora - u["inicio"])
            if u["vazando"] and u["categoria"] != "ferramenta" and f"vaz:{chave}" not in self._avisados:
                self._avisados.add(f"vaz:{chave}")
                self.emitir("memoria", "Memória só subindo",
                            f"{u['nome']} ({u['projeto'] or 'sem projeto'}) já usa {u['ram_mb']} MB e não para de crescer.",
                            nivel="aviso", windows=True)
        for chave in list(self._ram):
            if chave not in vivos:
                del self._ram[chave]

    # --- servidores esquecidos (sem uso) -------------------------------------

    def _ociosos(self, est: dict) -> None:
        """Sem nenhuma conexão (aba aberta, requisição, proxy) há horas: sugere parar."""
        agora = time.time()
        for u in est["unidades"]:
            if u["categoria"] == "ferramenta" or not u["portas"]:
                continue
            k = historico.chave(u)
            ultimo = self._uso.get(k, max(u["inicio"], self._inicio))
            if self.proxy:
                ultimo = max([ultimo] + [self.proxy.ultimo_uso.get(p, 0) for p in u["portas"]])
            if u.get("conexoes") or (self.proxy and any(self.proxy.em_uso(p) for p in u["portas"])):
                ultimo = agora
            self._uso[k] = ultimo
            u["sem_uso_ha"] = agora - ultimo
            horas = self.cfg.ocioso_horas
            if horas and u["sem_uso_ha"] > horas * 3600 and f"ocioso:{k}" not in self._avisados:
                self._avisados.add(f"ocioso:{k}")
                h = int(u["sem_uso_ha"] // 3600)
                self.emitir("ocioso", "Servidor sem uso",
                            f"{u['nome']} ({u['projeto'] or 'sem projeto'}) está há {h}h sem nenhum acesso e usa {u['ram_mb']} MB.",
                            nivel="aviso", windows=True,
                            acao={"rotulo": "Parar", "tipo": "encerrar", "pid": u["pid"], "nome": u["nome"]})

    # --- Git: buscar novidades em segundo plano ------------------------------

    def _laco_git(self) -> None:
        from argos.core import git, projetos

        time.sleep(90)
        while True:
            minutos = self.cfg.git_fetch_minutos
            if minutos:
                try:
                    for p in projetos.listar(self.cfg, com_git=False):
                        if not p["tem_git"]:
                            continue
                        git.fetch(p["pasta"])
                        info = projetos.git_info(p["pasta"])
                        if not info:
                            continue
                        antes = self._git_receber.get(p["nome"])
                        self._git_receber[p["nome"]] = info["a_receber"]
                        if antes is not None and info["a_receber"] > antes:
                            self.emitir("git", f"{p['nome']}: novidades no Git",
                                        f"{info['a_receber']} commit(s) novo(s) na branch {info['branch']} para baixar.",
                                        windows=True, acao={"rotulo": "Pull", "tipo": "git", "projeto": p["nome"], "op": "pull"})
                except Exception:
                    log.exception("falha no git fetch automático")
            time.sleep(max(5, minutos or 15) * 60)

    # --- versão nova do Argos ------------------------------------------------

    def _laco_atualizacao(self) -> None:
        from argos.core import atualizacao

        avisada = None
        while True:
            try:
                self.atualizacao = atualizacao.disponivel(self.cfg)
                if self.atualizacao and self.atualizacao["versao"] != avisada:
                    avisada = self.atualizacao["versao"]
                    self.emitir("atualizacao", "Versão nova do Argos",
                                f"A versão {avisada} está disponível (você tem a {self.atualizacao['atual']}).",
                                windows=True, acao={"rotulo": "Atualizar", "tipo": "atualizar"})
            except Exception:
                log.exception("falha ao procurar atualização")
            time.sleep(6 * 3600)

    # --- histórico e outros avisos ------------------------------------------

    def _historico(self, est: dict) -> None:
        atuais = {historico.chave(u): u for u in est["unidades"] if u["categoria"] != "ferramenta"}
        for k, u in atuais.items():
            if k not in self._vistos:
                historico.registrar("inicio", u, quando=u["inicio"])
        for k, u in self._vistos.items():
            if k not in atuais:
                historico.registrar("fim", u)
        self._vistos = atuais

    def _avisos(self, est: dict) -> None:
        agora = time.time()
        orfaos_novos = []
        for u in est["unidades"]:
            if u["categoria"] == "ferramenta":
                continue
            k = historico.chave(u)
            if u["orfao"] and self.cfg.alerta_orfaos and f"orfao:{k}" not in self._avisados:
                self._avisados.add(f"orfao:{k}")
                orfaos_novos.append(u)
            horas = self.cfg.alerta_horas
            if horas and agora - u["inicio"] > horas * 3600 and f"longo:{k}" not in self._avisados:
                self._avisados.add(f"longo:{k}")
                if not self._primeira:
                    h = int((agora - u["inicio"]) // 3600)
                    self.emitir("longo", "Rodando há muito tempo",
                                f"{u['nome']} ({u['projeto'] or 'sem projeto'}) está rodando há {h}h.", windows=True)
        if orfaos_novos:
            if len(orfaos_novos) == 1:
                u = orfaos_novos[0]
                self.emitir("orfao", "Processo órfão", f"{u['nome']} ({u['projeto'] or 'sem projeto'}) continua rodando, "
                                                       "mas o terminal que o abriu foi fechado.", nivel="aviso", windows=True)
            else:
                self.emitir("orfao", "Processos órfãos",
                            f"{len(orfaos_novos)} processos continuam rodando sem o terminal que os abriu.",
                            nivel="aviso", windows=True)

        for f in est["ferramentas"]:
            if not f["orfas"]:
                continue
            k = f"ferr:{f['nome']}:{f['orfas']}"
            if k not in self._avisados:
                self._avisados.add(k)
                self.emitir("ferramenta", "Ferramenta vazada",
                            f"{f['nome']}: {f['orfas']} instância(s) sem dono, gastando memória à toa.",
                            nivel="aviso", windows=True)
