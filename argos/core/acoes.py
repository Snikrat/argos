"""Operações de alto nível, usadas tanto pelo CLI quanto pelo app.

Cada ação devolve um `Resultado`: ok, mensagem e se precisa de administrador.
"""

from __future__ import annotations

import os
import subprocess
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

import psutil

from argos.config import Config
from argos.core import ambiente, docker, portas, registro
from argos.core.coleta import Fotografia, rotulo_comando
from argos.plataforma import SEM_JANELA, ambiente_externo, encerrar_arvore


@dataclass
class Resultado:
    ok: bool
    msg: str = ""
    admin: bool = False          # falhou por falta de permissão
    conflito: dict | None = None  # porta ocupada ao iniciar
    extra: dict = field(default_factory=dict)

    def dict(self) -> dict:
        return asdict(self)


# --- coleta completa ------------------------------------------------------

def fotografar(cfg: Config) -> Fotografia:
    return Fotografia(cfg, registro.ativos_por_pid())


def estado(cfg: Config, com_docker: bool = True) -> dict:
    """Tudo que o painel e o `argos` mostram."""
    foto = fotografar(cfg)
    unidades = foto.unidades()

    dk = {"instalado": docker.instalado(), "ligado": False, "containers": [], "vmmem_mb": None}
    if com_docker and dk["instalado"]:
        dk["ligado"] = docker.ligado()
        if dk["ligado"]:
            dk["containers"] = docker.containers()
        dk["vmmem_mb"] = docker.vmmem_mb()

    portas = foto.portas_dev(unidades, dk["containers"])

    # Ferramentas (servidores MCP etc.), agrupadas para achar duplicados
    ferramentas: dict[str, dict] = {}
    for u in unidades:
        if u["categoria"] != "ferramenta":
            continue
        nome = foto.nome_ferramenta(u)
        f = ferramentas.setdefault(nome, {"nome": nome, "unidades": [], "ram_mb": 0, "orfas": 0})
        f["unidades"].append(u)
        f["ram_mb"] += u["ram_mb"]
        f["orfas"] += u["orfao"]
    for f in ferramentas.values():
        f["instancias"] = len(f["unidades"])

    # Projetos ativos: processos + containers rodando, agrupados por projeto
    ativos: dict[str, dict] = defaultdict(lambda: {"unidades": [], "containers": [], "pasta": ""})
    for u in unidades:
        if u["categoria"] == "ferramenta":
            continue
        a = ativos[u["projeto"] or ""]
        a["unidades"].append(u)
        a["pasta"] = a["pasta"] or (u["pasta"] if u["projeto"] else "")
    for c in dk["containers"]:
        if c["estado"] == "running":
            a = ativos[c["projeto"] or c["nome"]]
            a["containers"].append(c)
            a["pasta"] = a["pasta"] or c["pasta"]
    lista_ativos = []
    for nome, a in ativos.items():
        a["nome"] = nome
        a["portas"] = sorted({p for u in a["unidades"] for p in u["portas"]} |
                             {h for c in a["containers"] for h, _ in c["portas"]})
        a["orfaos"] = sum(u["orfao"] for u in a["unidades"])
        a["inicio"] = min([u["inicio"] for u in a["unidades"]] or [time.time()])
        lista_ativos.append(a)
    lista_ativos.sort(key=lambda a: (a["nome"] == "", a["nome"].lower()))

    parados = [e for e in registro.listar() if not e["vivo"]]
    for e in parados:
        e.pop("env", None)

    from argos.core import sessoes

    return {
        "momento": foto.momento,
        "sessao": sessoes.pendente(),
        "unidades": unidades,
        "portas": portas,
        "docker": dk,
        "ativos": lista_ativos,
        "ferramentas": sorted(ferramentas.values(), key=lambda f: f["nome"].lower()),
        "parados": parados,
        "resumo": {
            "processos": sum(1 for u in unidades if u["categoria"] != "ferramenta"),
            "containers": sum(1 for c in dk["containers"] if c["estado"] == "running"),
            "portas": len(portas),
            "orfaos": sum(1 for u in unidades if u["orfao"] and u["categoria"] != "ferramenta"),
            "ferramentas_orfas": sum(f["orfas"] for f in ferramentas.values()),
        },
    }


def pid_de_dev(cfg: Config, pid: int) -> int | None:
    """PID raiz do processo de desenvolvimento a que `pid` pertence; None se não for um.

    Usado onde quem pede não é o usuário olhando a tela (MCP): impede encerrar um
    programa qualquer da máquina pelo número.
    """
    for u in fotografar(cfg).unidades():
        if u["categoria"] != "ferramenta" and (pid == u["pid"] or pid in u["pids"]):
            return u["pid"]
    return None


# --- encerrar ---------------------------------------------------------------
def encerrar(pid: int) -> Resultado:
    try:
        nome = psutil.Process(pid).name()
    except psutil.NoSuchProcess:
        return Resultado(False, f"O processo {pid} não existe mais.")
    # Os iniciados pelo Argos têm console próprio: dá para pedir que fechem antes de forçar
    gentil = pid in registro.ativos_por_pid()
    registro.marcar_parada(pid)
    ok, negado = encerrar_arvore(pid, gentil=gentil)
    if ok:
        return Resultado(True, f"Encerrado: {nome} (PID {pid})")
    return Resultado(False, f"Não consegui encerrar {nome} (PID {pid}).", admin=negado)


def encerrar_porta(cfg: Config, porta: int) -> Resultado:
    foto = fotografar(cfg)
    pids = foto.porta_pids.get(porta)
    if not pids:
        return Resultado(False, f"Ninguém está usando a porta {porta}.")
    unidades = foto.unidades()
    por_pid = {p: u for u in unidades for p in u["pids"]}
    msgs, ok, admin = [], True, False
    for pid in pids:
        if foto.nome(pid).startswith(("com.docker", "wslrelay", "vpnkit", "docker")):
            for c in (docker.containers() if docker.ligado() else []):
                if any(h == porta for h, _ in c["portas"]):
                    r_ok, _ = docker.parar([c["id"]])
                    msgs.append(f"Container parado: {c['nome']}" if r_ok else f"Falhou ao parar {c['nome']}")
                    ok &= r_ok
            continue
        u = por_pid.get(pid)
        r = encerrar(u["pid"] if u else pid)
        msgs.append(r.msg)
        ok &= r.ok
        admin |= r.admin
    return Resultado(ok, "\n".join(msgs), admin=admin)


# --- reiniciar --------------------------------------------------------------

def _esperar_porta_livre(portas: list[int], segundos: float = 5) -> None:
    limite = time.time() + segundos
    while portas and time.time() < limite:
        ocupadas = {c.laddr.port for c in psutil.net_connections("tcp")
                    if c.status == psutil.CONN_LISTEN and c.laddr}
        if not ocupadas & set(portas):
            return
        time.sleep(0.2)


def reiniciar_pid(cfg: Config, pid: int) -> Resultado:
    foto = fotografar(cfg)
    if pid not in foto.procs:
        return Resultado(False, f"O processo {pid} não existe mais.")
    raiz = foto.raiz(pid)
    portas = sorted({p for x in [raiz, *foto.descendentes(raiz)] for p in foto.pid_portas.get(x, ())})

    ger = foto.gerenciado_de(raiz)
    if ger:
        registro.reiniciar(ger)
        return Resultado(True, f"Reiniciado: {ger['nome']}")

    # Processo aberto fora do argos: copia comando, pasta e variáveis do original
    try:
        p = psutil.Process(raiz)
        args, cwd, env = p.cmdline(), p.cwd(), p.environ()
    except psutil.AccessDenied:
        return Resultado(False, "Esse processo foi aberto como administrador.", admin=True)
    except psutil.NoSuchProcess:
        return Resultado(False, "O processo terminou antes de ser reiniciado.")
    if not args:
        return Resultado(False, "Não consegui ler o comando desse processo.")

    nome = rotulo_comando(args)
    proj = foto.projeto(raiz)
    ok, negado = encerrar_arvore(raiz)
    if not ok:
        return Resultado(False, f"Não consegui encerrar {nome}.", admin=negado)
    _esperar_porta_livre(portas)
    comando = subprocess.list2cmdline(args)
    try:
        registro.iniciar(comando, cwd, env, shell=False, nome=nome, projeto=proj[0] if proj else "")
    except (OSError, RuntimeError, subprocess.SubprocessError) as e:
        # O original já foi encerrado: sem isto o processo sumia sem explicação
        return Resultado(False, f"Encerrei {nome}, mas não consegui iniciar de novo ({e}). "
                                f"Para subir à mão, rode em {cwd}: {comando}", extra={"cmd": comando, "cwd": cwd})
    return Resultado(True, f"Reiniciado: {nome} (agora com logs no Argos)")


def reiniciar_gerenciado(id_: str) -> Resultado:
    e = registro.buscar(id_)
    if not e:
        return Resultado(False, "Esse processo não está mais no registro.")
    registro.reiniciar(e)
    return Resultado(True, f"Reiniciado: {e['nome']}")


def reiniciar_porta(cfg: Config, porta: int) -> Resultado:
    foto = fotografar(cfg)
    pids = foto.porta_pids.get(porta)
    if not pids:
        return Resultado(False, f"Ninguém está usando a porta {porta}.")
    pid = next(iter(pids))
    if foto.nome(pid).startswith(("com.docker", "wslrelay", "vpnkit", "docker")):
        alvos = [c for c in docker.containers() if any(h == porta for h, _ in c["portas"])]
        ok, _ = docker.reiniciar([c["id"] for c in alvos]) if alvos else (False, "")
        return Resultado(ok, f"Container reiniciado: {', '.join(c['nome'] for c in alvos)}" if ok else "Falhou.")
    return reiniciar_pid(cfg, pid)


# --- projetos ---------------------------------------------------------------

def _do_projeto(cfg: Config, nome: str) -> tuple[list[dict], list[dict]]:
    est = estado(cfg)
    alvo = nome.lower()
    unidades = [u for u in est["unidades"] if u["projeto"].lower() == alvo and u["categoria"] != "ferramenta"]
    containers = [c for c in est["docker"]["containers"] if c["estado"] == "running" and
                  (c["projeto"].lower() == alvo or Path(c["pasta"] or "/").name.lower() == alvo)]
    return unidades, containers


def parar_projeto(cfg: Config, nome: str) -> Resultado:
    unidades, containers = _do_projeto(cfg, nome)
    if not unidades and not containers:
        return Resultado(False, f"Nada rodando do projeto '{nome}'.")
    msgs, ok, admin = [], True, False
    if containers:
        c_ok, _ = docker.parar([c["id"] for c in containers])
        msgs.append(f"{len(containers)} container(s) parado(s)" if c_ok else "Falhou ao parar containers")
        ok &= c_ok
    for u in unidades:
        r = encerrar(u["pid"])
        msgs.append(r.msg)
        ok &= r.ok
        admin |= r.admin
    return Resultado(ok, "\n".join(msgs), admin=admin)


def reiniciar_projeto(cfg: Config, nome: str) -> Resultado:
    unidades, containers = _do_projeto(cfg, nome)
    if not unidades and not containers:
        return Resultado(False, f"Nada rodando do projeto '{nome}'.")
    msgs, ok, admin = [], True, False
    if containers:
        c_ok, _ = docker.reiniciar([c["id"] for c in containers])
        msgs.append(f"{len(containers)} container(s) reiniciado(s)" if c_ok else "Falhou ao reiniciar containers")
        ok &= c_ok
    for u in unidades:
        r = reiniciar_gerenciado(u["gerenciado"]) if u["gerenciado"] else reiniciar_pid(cfg, u["pid"])
        msgs.append(r.msg)
        ok &= r.ok
        admin |= r.admin
    return Resultado(ok, "\n".join(msgs), admin=admin)


def conflito_porta(cfg: Config, porta: int | None) -> dict | None:
    if not porta:
        return None
    foto = fotografar(cfg)
    pids = foto.porta_pids.get(porta)
    if not pids:
        return None
    pid = next(iter(pids))
    por_pid = {p: u for u in foto.unidades() for p in u["pids"]}
    u = por_pid.get(pid)
    return {"porta": porta, "pid": u["pid"] if u else pid,
            "dono": u["nome"] if u else foto.nome(pid), "projeto": (u or {}).get("projeto", "")}


def porta_ouvindo(porta: int) -> bool:
    return any(c.status == psutil.CONN_LISTEN and c.laddr and c.laddr.port == porta
               for c in psutil.net_connections("tcp"))


def esperar_pronto(spec: str, entrada: dict | None = None, timeout: float = 120) -> tuple[bool, str]:
    """Espera até `spec` ("porta:N", "http://..." ou "log:texto") ser verdade."""
    import urllib.error
    import urllib.request

    limite = time.time() + timeout
    while time.time() < limite:
        if entrada and not registro.vivo(entrada):
            return False, "o processo terminou antes de ficar pronto"
        if spec.startswith("porta:"):
            if porta_ouvindo(int(spec[6:])):
                return True, ""
        elif spec.startswith("http"):
            try:
                urllib.request.urlopen(spec, timeout=2)
                return True, ""
            except urllib.error.HTTPError as e:
                if e.code < 500:
                    return True, ""
            except (OSError, ValueError):
                pass
        elif spec.startswith("log:") and entrada:
            # Só a saída desta execução: o arquivo guarda também as anteriores, e o texto
            # de uma subida antiga fazia o serviço parecer pronto na hora
            try:
                with open(entrada["log"], "rb") as f:
                    f.seek(entrada.get("log_de", 0))
                    if spec[4:] in f.read().decode("utf-8", errors="replace"):
                        return True, ""
            except OSError:
                pass
        time.sleep(0.5)
    return False, f"não ficou pronto em {int(timeout)}s"


def subir_projeto(cfg: Config, projeto: dict, progresso=lambda msg: None, so: str | None = None) -> Resultado:
    """Sobe os serviços do argos.toml em ordem, esperando cada um ficar pronto.

    Com `so`, sobe só esse serviço e o que ele precisa (`depois`), sem tocar nos outros.
    """
    from argos.core import projetos as proj

    try:
        servicos = proj.carregar_grupo(projeto["pasta"])
    except proj.ErroGrupo as e:
        return Resultado(False, str(e))
    if so:
        por_nome = {s["nome"]: s for s in servicos}
        if so not in por_nome:
            return Resultado(False, f"O argos.toml de {projeto['nome']} não tem o serviço '{so}'.")
        precisa, fila = set(), [so]
        while fila:
            n = fila.pop()
            if n not in precisa:
                precisa.add(n)
                fila += por_nome[n]["depois"]
        servicos = [s for s in servicos if s["nome"] in precisa]
    # Duas subidas ao mesmo tempo (dois cliques, ou app e terminal) iniciariam tudo em dobro
    marca = _marca_subida(projeto["nome"])
    if marca is None:
        return Resultado(False, f"{projeto['nome']} já está subindo. Espere terminar.")
    try:
        return _subir_servicos(cfg, projeto, servicos, progresso)
    finally:
        marca.unlink(missing_ok=True)


def _marca_subida(nome: str) -> Path | None:
    """Arquivo que marca "este projeto está subindo". None se outra subida está em andamento."""
    from argos.config import PASTA_DADOS

    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    marca = PASTA_DADOS / f"subindo-{registro._slug(nome.lower())}.lock"
    for _ in range(2):
        try:
            os.close(os.open(marca, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return marca
        except FileExistsError:
            try:
                if time.time() - marca.stat().st_mtime < 20 * 60:
                    return None
                marca.unlink()  # sobrou de uma subida que foi interrompida
            except OSError:
                return None
    return None


def _subir_servicos(cfg: Config, projeto: dict, servicos: list[dict], progresso) -> Resultado:
    from argos.core import projetos as proj

    existentes = {e["nome"]: e for e in registro.listar() if e.get("projeto") == projeto["nome"]}
    for s in servicos:
        nome = s["nome"]
        pasta = str(Path(projeto["pasta"]) / s.get("pasta", "."))
        pronto = s.get("pronto")
        espera = float(s.get("espera", 120))

        anterior = existentes.get(nome)
        if anterior and anterior["vivo"]:
            progresso(f"{nome}: já está rodando")
            continue

        if s.get("docker"):
            if not docker.ligado():
                return Resultado(False, f"{nome}: o Docker está desligado. Ligue o Docker Desktop primeiro.")
            progresso(f"Subindo {nome} (Docker)…")
            alvo = None if s["docker"] == "*" else [s["docker"]]
            ok, texto = docker.compose_subir(pasta, alvo)
            if not ok:
                return Resultado(False, f"{nome}: {texto[-300:]}")
            entrada = None
        else:
            if pronto and pronto.startswith("porta:") and porta_ouvindo(int(pronto[6:])):
                c = conflito_porta(cfg, int(pronto[6:]))
                return Resultado(False, f"{nome}: a porta {pronto[6:]} já está em uso por {c['dono'] if c else 'outro programa'}.",
                                 conflito=c)
            progresso(f"Subindo {nome}…")
            # Ordem: ambiente do sistema, arquivo .env escolhido para a pasta, env do argos.toml
            env = {**os.environ, **ambiente.variaveis_escolhidas(projeto, s.get("pasta", "")),
                   **{k: str(v) for k, v in (s.get("env") or {}).items()}}
            entrada, _ = registro.iniciar(
                s["cmd"], pasta, env, shell=True, nome=nome, projeto=projeto["nome"],
                auto=bool(s.get("auto")), id_=anterior["id"] if anterior else None,
                log=anterior["log"] if anterior else None)

        if pronto:
            ok, motivo = esperar_pronto(pronto, entrada, espera)
            if not ok:
                return Resultado(False, f"{nome} {motivo}. Veja os logs.",
                                 extra={"id": entrada["id"] if entrada else None})
            progresso(f"{nome} pronto")
    return Resultado(True, f"{projeto['nome']} no ar: " + " → ".join(s["nome"] for s in servicos))


def _containers_do_servico(projeto: dict, s: dict, containers: list[dict]) -> list[dict]:
    pasta = os.path.normcase(os.path.normpath(str(Path(projeto["pasta"]) / s.get("pasta", "."))))
    return [c for c in containers
            if os.path.normcase(os.path.normpath(c["pasta"] or "")) == pasta and s["docker"] in ("*", c["servico"])]


def estado_servicos(cfg: Config, projeto: dict) -> list[dict]:
    """Serviços do argos.toml com o que está rodando de cada um."""
    from argos.core import projetos as proj

    try:
        servicos = proj.carregar_grupo(projeto["pasta"])
    except (proj.ErroGrupo, OSError):
        return []
    vivos = {e["nome"]: e for e in registro.listar() if e.get("projeto") == projeto["nome"] and e["vivo"]}
    tem_docker = any(s.get("docker") for s in servicos)
    containers = docker.containers() if tem_docker and docker.instalado() and docker.ligado() else []
    saida = []
    for s in servicos:
        item = {"nome": s["nome"], "depois": s["depois"], "tipo": "docker" if s.get("docker") else "processo",
                "rodando": False, "id": None, "pid": None, "containers": []}
        if s.get("docker"):
            meus = [c for c in _containers_do_servico(projeto, s, containers) if c["estado"] == "running"]
            item.update(rodando=bool(meus), containers=[c["id"] for c in meus])
        elif s["nome"] in vivos:
            e = vivos[s["nome"]]
            item.update(rodando=True, id=e["id"], pid=e["pid"])
        saida.append(item)
    return saida


def parar_servico(cfg: Config, projeto: dict, nome: str) -> Resultado:
    s = next((x for x in estado_servicos(cfg, projeto) if x["nome"] == nome), None)
    if not s:
        return Resultado(False, f"O argos.toml de {projeto['nome']} não tem o serviço '{nome}'.")
    if not s["rodando"]:
        return Resultado(True, f"{nome} já estava parado.")
    if s["tipo"] == "docker":
        ok, texto = docker.parar(s["containers"])
        return Resultado(ok, f"{nome} parado." if ok else texto[-300:])
    r = encerrar(s["pid"])
    return Resultado(r.ok, f"{nome} parado." if r.ok else r.msg, admin=r.admin)


def reiniciar_servico(cfg: Config, projeto: dict, nome: str, progresso=lambda msg: None) -> Resultado:
    r = parar_servico(cfg, projeto, nome)
    if not r.ok:
        return r
    return subir_projeto(cfg, projeto, progresso, so=nome)


def criar_grupo(projeto: dict) -> Resultado:
    from argos.core import projetos as proj

    if caminho := proj.arquivo_grupo(projeto["pasta"]):
        return Resultado(True, f"{caminho.name} já existe.", extra={"caminho": str(caminho)})
    caminho = Path(projeto["pasta"]) / proj.ARQUIVO_GRUPO
    caminho.write_text(proj.gerar_grupo(projeto["pasta"]), encoding="utf-8")
    return Resultado(True, f"Criado {caminho.name}: revise os comandos e portas.", extra={"caminho": str(caminho)})


def iniciar_comando(cfg: Config, projeto: dict, comando: dict, ignorar_conflito: bool = False) -> Resultado:
    from argos.core import preferencias

    # Cada comando roda na própria pasta (ex: frontend/ ou backend/)
    pasta = comando.get("pasta") or projeto["pasta"]
    nome = f"{comando['sub']}: {comando['rotulo']}" if comando.get("sub") else comando["rotulo"]
    if comando["tipo"] == "grupo":
        preferencias.registrar_uso(projeto["nome"], comando["chave"])
        return subir_projeto(cfg, projeto)
    if comando["tipo"] == "compose":
        if not docker.ligado():
            return Resultado(False, "O Docker está desligado. Ligue o Docker Desktop primeiro.")
        ok, texto = docker.compose_subir(pasta)
        if ok:
            preferencias.registrar_uso(projeto["nome"], comando["chave"])
        return Resultado(ok, "Containers iniciados." if ok else texto[-400:])

    if comando["tipo"] == "godot":
        subprocess.Popen(comando["cmd"], cwd=pasta, shell=True, creationflags=SEM_JANELA, env=ambiente_externo())
        preferencias.registrar_uso(projeto["nome"], comando["chave"])
        return Resultado(True, "Abrindo no Godot...")

    cmd, env = comando["cmd"], dict(os.environ)
    env.update(ambiente.variaveis_escolhidas(projeto, comando.get("sub", "")))
    if cfg.portas_fixas and comando.get("ferramenta"):
        porta = preferencias.porta_reservada(projeto["nome"], comando["chave"])
        if not porta:
            ocupadas = {c.laddr.port for c in psutil.net_connections("tcp")
                        if c.status == psutil.CONN_LISTEN and c.laddr}
            porta = portas.escolher(comando, set(preferencias.portas_reservadas().values()), ocupadas)
            preferencias.reservar_porta(projeto["nome"], comando["chave"], porta)
        cmd, extra = portas.aplicar(cmd, comando["ferramenta"], porta)
        env.update(extra)
        comando = {**comando, "porta": porta}

    if not ignorar_conflito:
        c = conflito_porta(cfg, comando.get("porta"))
        if c:
            return Resultado(False, f"A porta {c['porta']} já está em uso por {c['dono']}.", conflito=c)

    entrada, _ = registro.iniciar(cmd, pasta, env, shell=True, nome=nome, projeto=projeto["nome"])
    preferencias.registrar_uso(projeto["nome"], comando["chave"])
    porta_txt = f" na porta {comando['porta']}" if comando.get("porta") else ""
    return Resultado(True, f"Iniciado: {projeto['nome']} - {nome}{porta_txt}", extra={"id": entrada["id"]})


def iniciar_personalizado(projeto: dict, cmd: str, sub: str = "") -> Resultado:
    """Roda um comando digitado à mão (na raiz ou numa subpasta) e o guarda nos recentes."""
    from argos.core import preferencias

    pasta = str(Path(projeto["pasta"]) / sub) if sub else projeto["pasta"]
    if not Path(pasta).is_dir():
        return Resultado(False, f"A pasta '{sub}' não existe nesse projeto.")
    nome = f"{sub}: {cmd}" if sub else cmd
    env = {**os.environ, **ambiente.variaveis_escolhidas(projeto, sub)}
    entrada, _ = registro.iniciar(cmd, pasta, env, shell=True, nome=nome, projeto=projeto["nome"])
    chave = preferencias.adicionar_recente(projeto["nome"], cmd, pasta, sub)
    preferencias.registrar_uso(projeto["nome"], chave)
    return Resultado(True, f"Iniciado: {nome}", extra={"id": entrada["id"]})


# --- modo jogo --------------------------------------------------------------

def modo_jogo(cfg: Config, desligar_docker: bool = True, desligar_wsl: bool = False,
              lembrar: bool = True) -> Resultado:
    """Para tudo de desenvolvimento e libera RAM. Não mexe nas ferramentas do Claude.

    Com `lembrar`, salva uma sessão antes para retomar depois com um clique.
    """
    from argos.core import sessoes

    est = estado(cfg)
    msgs, ok, admin = [], True, False
    if lembrar:
        s = sessoes.salvar(est, "modo jogo")
        if s["itens"]:
            msgs.append(f"Sessão salva ({len(s['itens'])} itens): use Retomar para subir tudo de novo")
    for u in est["unidades"]:
        if u["categoria"] == "ferramenta":
            continue
        r = encerrar(u["pid"])
        ok &= r.ok
        admin |= r.admin
        if not r.ok:
            msgs.append(r.msg)
    n = sum(1 for u in est["unidades"] if u["categoria"] != "ferramenta")
    msgs.insert(0, f"{n} processo(s) encerrado(s)")

    rodando = [c["id"] for c in est["docker"]["containers"] if c["estado"] == "running"]
    if rodando:
        c_ok, _ = docker.parar(rodando)
        msgs.append(f"{len(rodando)} container(s) parado(s)" if c_ok else "Falhou ao parar containers")
        ok &= c_ok
    if desligar_docker and est["docker"]["instalado"] and (est["docker"]["ligado"] or est["docker"]["vmmem_mb"]):
        d_ok, _ = docker.desligar_desktop()
        msgs.append("Docker Desktop desligado" if d_ok else "Não consegui desligar o Docker Desktop")
    if desligar_wsl:
        w_ok, _ = docker.desligar_wsl()
        msgs.append("WSL desligado" if w_ok else "Não consegui desligar o WSL")
    return Resultado(ok, "\n".join(msgs), admin=admin)
