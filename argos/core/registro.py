"""Processos iniciados pelo argos: comando, pasta, variáveis e log de cada um.

Fica em %LOCALAPPDATA%\\argos\\registro.json e é compartilhado entre o CLI e o app.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

import psutil

from argos.config import ARQUIVO_REGISTRO, PASTA_DADOS, PASTA_LOGS
from argos.plataforma import encerrar_arvore, flags_processo

LOG_MAXIMO = 5 * 2**20      # ao passar disso, o log é cortado...
LOG_MANTER = 1 * 2**20      # ...mantendo só o final
ESQUECER_APOS = 24 * 3600   # entradas paradas somem depois de 1 dia


@contextlib.contextmanager
def _trava():
    """Trava simples entre processos (CLI e app podem escrever ao mesmo tempo)."""
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    caminho = ARQUIVO_REGISTRO.with_suffix(".lock")
    for _ in range(100):
        try:
            fd = os.open(caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                if time.time() - caminho.stat().st_mtime > 10:
                    caminho.unlink()
            except OSError:
                pass
            time.sleep(0.05)
    else:
        fd = None
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
            with contextlib.suppress(OSError):
                caminho.unlink()


def _ler() -> list[dict]:
    try:
        return json.loads(ARQUIVO_REGISTRO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _gravar(entradas: list[dict]) -> None:
    tmp = ARQUIVO_REGISTRO.with_suffix(".tmp")
    tmp.write_text(json.dumps(entradas, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, ARQUIVO_REGISTRO)


def vivo(e: dict) -> bool:
    """O processo da entrada ainda existe (e não é outro que herdou o PID)?"""
    try:
        return abs(psutil.Process(e["pid"]).create_time() - e["criado"]) < 2
    except (psutil.Error, KeyError):
        return False


def listar() -> list[dict]:
    """Entradas do registro, com `vivo` calculado. Remove as paradas há muito tempo."""
    with _trava():
        entradas = _ler()
        agora = time.time()
        mantidas = []
        mudou = False
        for e in entradas:
            e["vivo"] = vivo(e)
            if e["vivo"] and "parado_em" in e:
                del e["parado_em"]
                mudou = True
            elif not e["vivo"] and "parado_em" not in e:
                e["parado_em"] = agora
                mudou = True
            if e["vivo"] or agora - e["parado_em"] < ESQUECER_APOS:
                mantidas.append(e)
            else:
                mudou = True
        if mudou:
            _gravar([{k: v for k, v in e.items() if k != "vivo"} for e in mantidas])
    return mantidas


def buscar(chave: str) -> dict | None:
    for e in listar():
        if e["id"] == chave:
            return e
    return None


def ativos_por_pid() -> dict[int, dict]:
    return {e["pid"]: e for e in listar() if e["vivo"]}


def esquecer(id_: str) -> None:
    with _trava():
        _gravar([e for e in _ler() if e["id"] != id_])


def _slug(texto: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", texto).strip("-")[:40] or "processo"


def _preparar_log(caminho: Path, cabecalho: str):
    PASTA_LOGS.mkdir(parents=True, exist_ok=True)
    try:
        if caminho.stat().st_size > LOG_MAXIMO:
            with open(caminho, "rb") as f:
                f.seek(-LOG_MANTER, os.SEEK_END)
                final = f.read()
            caminho.write_bytes(final)
    except OSError:
        pass
    f = open(caminho, "ab")
    f.write(f"\n\x1b[2m=== {cabecalho} — {time.strftime('%d/%m %H:%M:%S')} ===\x1b[0m\n".encode())
    f.flush()
    return f


def _limpar_env(env: dict) -> dict:
    """Tira variáveis do ambiente de desenvolvimento do próprio Argos.

    Os scripts de compilação apontam o uv para a venv do Argos; se isso vazar
    para os projetos, um `uv run` neles usaria (e alteraria) a venv errada.
    O app empacotado (PyInstaller) também deixa variáveis _PYI_* e pastas próprias
    no PATH, que não têm nada a ver com os projetos.
    """
    from argos.config import PASTA_ANTIGA

    env = {k: v for k, v in env.items() if not k.upper().startswith("_PYI_")}
    venv = env.get("UV_PROJECT_ENVIRONMENT", "")
    if venv and str(PASTA_DADOS).lower() in venv.lower():
        del env["UV_PROJECT_ENVIRONMENT"]
    proprias = (str(PASTA_DADOS).lower(), str(PASTA_ANTIGA).lower())
    for chave in [k for k in env if k.upper() == "PATH"]:
        env[chave] = ";".join(p for p in env[chave].split(";") if not p.lower().startswith(proprias))
    return env


def _popen(cmd: str, cwd: str, env: dict, shell: bool, log: str, junto: bool) -> subprocess.Popen:
    env_filho = _limpar_env(env)
    env_filho.setdefault("FORCE_COLOR", "1")
    env_filho["PYTHONUNBUFFERED"] = "1"
    with open(log, "ab") as saida:
        kwargs = dict(shell=shell, cwd=cwd, env=env_filho, stdout=saida,
                      stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        try:
            return subprocess.Popen(cmd, creationflags=flags_processo(junto), **kwargs)
        except OSError:
            # Alguns ambientes não deixam o processo "escapar" do grupo do terminal
            return subprocess.Popen(cmd, creationflags=flags_processo(junto) & ~0x01000000, **kwargs)


def lancar(arquivo_spec: str) -> None:
    """Lançador intermediário (`argos _lancar`): inicia o processo e sai na hora.

    Assim o processo fica sem pai e quem fechar o terminal derrubando a árvore
    de processos não chega até ele.
    """
    spec = json.loads(Path(arquivo_spec).read_text(encoding="utf-8"))
    Path(arquivo_spec).unlink(missing_ok=True)
    proc = _popen(spec["cmd"], spec["cwd"], spec["env"], spec["shell"], spec["log"], False)
    print(proc.pid, flush=True)


def _iniciar_desacoplado(cmd: str, cwd: str, env: dict, shell: bool, log: str) -> int:
    from argos.plataforma import SEM_JANELA, comando_proprio

    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    spec = PASTA_DADOS / f"lancar-{uuid.uuid4().hex[:8]}.json"
    spec.write_text(json.dumps({"cmd": cmd, "cwd": cwd, "env": env, "shell": shell, "log": log}),
                    encoding="utf-8")
    r = subprocess.run(comando_proprio() + ["_lancar", str(spec)], capture_output=True, text=True,
                       creationflags=SEM_JANELA, timeout=30)
    spec.unlink(missing_ok=True)
    try:
        return int(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError(f"falha ao iniciar: {r.stderr.strip()[-300:]}") from None


def iniciar(cmd: str, cwd: str, env: dict[str, str], *, shell: bool, nome: str,
            projeto: str = "", junto: bool = False, id_: str | None = None,
            log: str | None = None, auto: bool = False,
            reinicios: list[float] | None = None) -> tuple[dict, subprocess.Popen | None]:
    """Inicia um processo gerenciado, com a saída indo para um arquivo de log.

    Com `junto=True` o processo é filho direto (e o Popen é devolvido); senão ele
    é lançado desacoplado e o Popen é None. Com `auto=True` o app reinicia o
    processo se ele cair.
    """
    id_ = id_ or uuid.uuid4().hex[:6]
    caminho_log = Path(log) if log else PASTA_LOGS / f"{_slug(projeto or nome)}-{id_}.log"
    _preparar_log(caminho_log, f"argos: {nome}").close()
    # O log é reaproveitado entre execuções: daqui em diante é a saída desta
    try:
        log_de = caminho_log.stat().st_size
    except OSError:
        log_de = 0

    proc = None
    if junto:
        proc = _popen(cmd, cwd, env, shell, str(caminho_log), True)
        pid = proc.pid
    else:
        pid = _iniciar_desacoplado(cmd, cwd, env, shell, str(caminho_log))

    try:
        criado = psutil.Process(pid).create_time()
    except psutil.Error:
        criado = time.time()

    entrada = {
        "id": id_, "nome": nome, "projeto": projeto, "cmd": cmd, "shell": shell,
        "cwd": cwd, "env": env, "pid": pid, "criado": criado, "junto": junto,
        "log": str(caminho_log), "log_de": log_de, "inicio": time.time(), "auto": auto,
        "manual": False, "reinicios": reinicios or [],
    }
    with _trava():
        entradas = [e for e in _ler() if e["id"] != id_]
        entradas.append(entrada)
        _gravar(entradas)
    return entrada, proc


def _alterar(filtro, **campos) -> None:
    with _trava():
        entradas = _ler()
        for e in entradas:
            if filtro(e):
                e.update(campos)
        _gravar(entradas)


def marcar_parada(pid: int) -> None:
    """Quem parou foi o usuário (não é uma queda): o app não avisa nem reinicia."""
    _alterar(lambda e: e["pid"] == pid, manual=True)


def definir_auto(id_: str, ativo: bool) -> None:
    _alterar(lambda e: e["id"] == id_, auto=bool(ativo))


def reiniciar(e: dict, por_queda: bool = False) -> tuple[dict, subprocess.Popen | None]:
    if vivo(e):
        marcar_parada(e["pid"])
        encerrar_arvore(e["pid"])
    agora = time.time()
    # Guarda os reinícios automáticos recentes, para não entrar em loop
    reinicios = [t for t in e.get("reinicios", []) if agora - t < 600] + ([agora] if por_queda else [])
    return iniciar(e["cmd"], e["cwd"], e["env"], shell=e["shell"], nome=e["nome"],
                   projeto=e.get("projeto", ""), junto=False, id_=e["id"], log=e["log"],
                   auto=e.get("auto", False), reinicios=reinicios)


_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b[\]()][^\x07\x1b]*(\x07|\x1b\\)?")


def ultimas_linhas(e: dict, n: int = 8) -> list[str]:
    """Últimas linhas do log, sem cores (para avisos de queda)."""
    try:
        with open(e["log"], "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 16384))
            texto = f.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    linhas = [_ANSI.sub("", l).split("\r")[-1].rstrip() for l in texto.splitlines()]
    return [l for l in linhas if l.strip() and not l.startswith("=== argos:")][-n:]
