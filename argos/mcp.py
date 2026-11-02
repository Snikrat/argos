"""Servidor MCP do Argos (`argos mcp`): deixa o Claude ver e controlar o que está rodando.

Protocolo MCP via stdio (JSON-RPC 2.0, uma mensagem por linha). Só stdout carrega
o protocolo; qualquer outra saída vai para stderr.
"""

from __future__ import annotations

import io
import json
import re
import sys
import time
import traceback
from contextlib import redirect_stdout

from argos import __version__, config

_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

FERRAMENTAS = [
    {"name": "status", "description": "O que está rodando agora: processos de dev por projeto (com portas site/API e se respondem), containers Docker, processos órfãos e sessão salva.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "projetos", "description": "Lista os projetos e os comandos para iniciar cada um (com a chave de cada comando), Git e testes.",
     "inputSchema": {"type": "object", "properties": {"projeto": {"type": "string", "description": "Filtrar por nome (opcional)"}}}},
    {"name": "logs", "description": "Últimas linhas do log de um processo iniciado pelo Argos ou de um container.",
     "inputSchema": {"type": "object", "properties": {
         "alvo": {"type": "string", "description": "Projeto, porta, PID, id do Argos ou nome do container"},
         "linhas": {"type": "integer", "default": 80}}, "required": ["alvo"]}},
    {"name": "iniciar", "description": "Inicia um comando de um projeto (use 'projetos' para ver as chaves). Sem comando, usa o principal.",
     "inputSchema": {"type": "object", "properties": {
         "projeto": {"type": "string"}, "comando": {"type": "string", "description": "Chave ou rótulo do comando"}},
         "required": ["projeto"]}},
    {"name": "reiniciar", "description": "Reinicia por porta, PID, id do Argos ou projeto inteiro (mantém pasta e variáveis).",
     "inputSchema": {"type": "object", "properties": {"alvo": {"type": "string"}}, "required": ["alvo"]}},
    {"name": "parar", "description": "Para tudo de um projeto (processos e containers) ou um processo pelo PID.",
     "inputSchema": {"type": "object", "properties": {"projeto": {"type": "string"}, "pid": {"type": "integer"}}}},
    {"name": "subir", "description": "Sobe o projeto inteiro em ordem conforme o argos.toml.",
     "inputSchema": {"type": "object", "properties": {"projeto": {"type": "string"}}, "required": ["projeto"]}},
    {"name": "testar", "description": "Roda os testes de um projeto e devolve o resultado.",
     "inputSchema": {"type": "object", "properties": {"projeto": {"type": "string"}}, "required": ["projeto"]}},
]


def _cfg():
    return config.carregar()


def t_status(_a) -> str:
    from argos.core import acoes

    est = acoes.estado(_cfg())
    linhas = []
    if est["sessao"]:
        s = est["sessao"]
        linhas.append(f"Sessão salva ({s['motivo']}, {time.strftime('%d/%m %H:%M', time.localtime(s['quando']))}): "
                      f"{s['processos']} processo(s), {s['containers']} container(s) — pode ser retomada no app.")
    for a in est["ativos"]:
        linhas.append(f"\n## {a['nome'] or 'Sem projeto'}" + (f"  ({a['pasta']})" if a["pasta"] else ""))
        for u in a["unidades"]:
            portas = ", ".join(f"{p} {u['portas_tipo'].get(p, '')}".strip() for p in u["portas"]) or "sem porta"
            linhas.append(f"- {u['nome']} · PID {u['pid']} · {portas} · aberto por {u['origem']}"
                          + (" · ÓRFÃO (terminal fechado)" if u["orfao"] else "")
                          + (f" · logs: id {u['gerenciado']}" if u["gerenciado"] else " · iniciado fora do Argos (sem logs)"))
        for c in a["containers"]:
            linhas.append(f"- container {c['nome']} ({c['imagem']}) · {c['status']}")
    if not est["ativos"]:
        linhas.append("Nada de desenvolvimento rodando.")
    dk = est["docker"]
    linhas.append(f"\nDocker: {'ligado' if dk['ligado'] else 'desligado' if dk['instalado'] else 'não instalado'}"
                  + (f", WSL usando {dk['vmmem_mb']} MB" if dk["vmmem_mb"] else ""))
    parados = est["parados"]
    if parados:
        linhas.append("Parados recentemente: " + "; ".join(f"{e['projeto'] or '-'}/{e['nome']} (id {e['id']})" for e in parados[:8]))
    return "\n".join(linhas)


def t_projetos(a) -> str:
    from argos.core import projetos, testes

    filtro = (a.get("projeto") or "").lower()
    linhas = []
    for p in projetos.listar(_cfg()):
        if filtro and filtro not in p["nome"].lower():
            continue
        g = p.get("git")
        git = f" · git {g['branch']}, {g['alteracoes']} alteração(ões), {g['a_enviar']} a enviar, {g['a_receber']} a receber" if g else ""
        t = testes.resumo(p["nome"])
        tt = f" · testes: {'ok' if t['ok'] else f'{t['falhas']} falha(s)'}" if t else ""
        linhas.append(f"\n## {p['nome']} ({', '.join(p['tipos']) or '-'}){git}{tt}\n{p['pasta']}")
        for c in p["comandos"]:
            onde = f"{c['sub']}/ " if c.get("sub") else ""
            porta = f" :{c['porta']}" if c.get("porta") else ""
            linhas.append(f"- [{c['chave']}] {onde}{c['rotulo']}{porta}")
    return "\n".join(linhas) or "Nenhum projeto encontrado."


def t_logs(a) -> str:
    from argos.core import acoes, docker, registro

    alvo = str(a["alvo"])
    n = int(a.get("linhas") or 80)
    e = registro.buscar(alvo)
    if not e:
        est = acoes.estado(_cfg())
        if alvo.isdigit():
            num = int(alvo)
            u = next((u for u in est["unidades"] if num == u["pid"] or num in u["pids"] or num in u["portas"]), None)
            if u and not u["gerenciado"]:
                return f"'{u['nome']}' foi iniciado fora do Argos, então não há logs. Reinicie pelo Argos para capturar."
            e = registro.buscar(u["gerenciado"]) if u else None
        else:
            candidatos = [x for x in registro.listar() if x["projeto"].lower() == alvo.lower()]
            candidatos.sort(key=lambda x: (not x["vivo"], -x["inicio"]))
            if candidatos:
                partes = []
                for x in candidatos[:4]:
                    partes.append(f"=== {x['nome']} ({'rodando' if x['vivo'] else 'parado'}, id {x['id']}) ===\n"
                                  + "\n".join(registro.ultimas_linhas(x, n)))
                return "\n\n".join(partes)
            for c in (docker.containers() if docker.ligado() else []):
                if alvo in (c["nome"], c["id"]) or c["projeto"].lower() == alvo.lower():
                    return _ANSI.sub("", docker.logs(c["id"], n))
    if not e:
        return (f"Não há logs de '{alvo}'. Logs só existem para o que foi iniciado pelo Argos (nas últimas 24h) "
                "ou para containers Docker. Use 'status' para ver o que está rodando.")
    return f"=== {e['nome']} ({'rodando' if e['vivo'] else 'parado'}) ===\n" + "\n".join(registro.ultimas_linhas(e, n))


def t_iniciar(a) -> str:
    from argos.core import acoes, projetos

    cfg = _cfg()
    p = projetos.buscar(cfg, a["projeto"])
    if not p or not p["comandos"]:
        return f"Projeto '{a['projeto']}' não encontrado ou sem comandos."
    pedido = (a.get("comando") or "").strip()
    c = p["comandos"][0] if not pedido else (
        projetos.buscar_comando(p, pedido)
        or next((x for x in p["comandos"] if pedido.lower() in f"{x.get('sub', '')} {x['rotulo']}".lower()), None))
    if not c:
        return f"Comando '{pedido}' não encontrado. Opções: " + "; ".join(x["chave"] for x in p["comandos"])
    r = acoes.iniciar_comando(cfg, p, c)
    return r.msg + (f" (logs: id {r.extra['id']})" if r.extra.get("id") else "")


def t_reiniciar(a) -> str:
    from argos.core import acoes, registro

    cfg, alvo = _cfg(), str(a["alvo"])
    if alvo.isdigit():
        n = int(alvo)
        foto = acoes.fotografar(cfg)
        r = acoes.reiniciar_porta(cfg, n) if n in foto.porta_pids else acoes.reiniciar_pid(cfg, n)
    elif registro.buscar(alvo):
        r = acoes.reiniciar_gerenciado(alvo)
    else:
        r = acoes.reiniciar_projeto(cfg, alvo)
    return r.msg


def t_parar(a) -> str:
    from argos.core import acoes

    if a.get("pid"):
        return acoes.encerrar(int(a["pid"])).msg
    if a.get("projeto"):
        return acoes.parar_projeto(_cfg(), a["projeto"]).msg
    return "Diga o projeto ou o PID."


def t_subir(a) -> str:
    from argos.core import acoes, projetos

    cfg = _cfg()
    p = projetos.buscar(cfg, a["projeto"])
    if not p:
        return f"Projeto '{a['projeto']}' não encontrado."
    etapas = []
    r = acoes.subir_projeto(cfg, p, progresso=etapas.append)
    return "\n".join(etapas + [r.msg])


def t_testar(a) -> str:
    from argos.core import projetos, testes

    p = projetos.buscar(_cfg(), a["projeto"])
    if not p:
        return f"Projeto '{a['projeto']}' não encontrado."
    lista = testes.detectar(p["pasta"])
    if not lista:
        return "Não encontrei testes nesse projeto."
    saida = []
    for t in lista:
        r = testes.rodar(p["nome"], t)
        onde = f"{t['sub']}/ " if t["sub"] else ""
        saida.append(f"{'PASSOU' if r['ok'] else 'FALHOU'}: {onde}{t['cmd']} — {r['resumo']} ({r['duracao']:.0f}s)")
        if not r["ok"]:
            log = _ANSI.sub("", open(r["log"], encoding="utf-8", errors="replace").read())
            saida.append("Últimas linhas:\n" + "\n".join(log.strip().splitlines()[-40:]))
    return "\n".join(saida)


EXECUTORES = {"status": t_status, "projetos": t_projetos, "logs": t_logs, "iniciar": t_iniciar,
              "reiniciar": t_reiniciar, "parar": t_parar, "subir": t_subir, "testar": t_testar}


def _responder(id_, resultado=None, erro=None) -> None:
    msg = {"jsonrpc": "2.0", "id": id_}
    if erro:
        msg["error"] = erro
    else:
        msg["result"] = resultado
    sys.stdout.buffer.write((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def _tratar(msg: dict) -> None:
    metodo, id_ = msg.get("method"), msg.get("id")
    if id_ is None:  # notificação (ex: notifications/initialized): sem resposta
        return
    if metodo == "initialize":
        versao = (msg.get("params") or {}).get("protocolVersion") or "2025-06-18"
        _responder(id_, {"protocolVersion": versao, "capabilities": {"tools": {}},
                         "serverInfo": {"name": "argos", "version": __version__},
                         "instructions": "Ferramentas do argos: veja o que está rodando no PC do usuário (projetos, "
                                         "portas, Docker), leia logs de erro e inicie/reinicie/pare servidores."})
    elif metodo == "ping":
        _responder(id_, {})
    elif metodo == "tools/list":
        _responder(id_, {"tools": FERRAMENTAS})
    elif metodo == "tools/call":
        params = msg.get("params") or {}
        nome, args = params.get("name"), params.get("arguments") or {}
        f = EXECUTORES.get(nome)
        if not f:
            _responder(id_, erro={"code": -32602, "message": f"Ferramenta desconhecida: {nome}"})
            return
        try:
            # Garante que nada impresso pelo código do Argos suje o protocolo
            with redirect_stdout(io.StringIO()):
                texto = f(args)
            _responder(id_, {"content": [{"type": "text", "text": texto}], "isError": False})
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            _responder(id_, {"content": [{"type": "text", "text": f"Erro: {e}"}], "isError": True})
    else:
        _responder(id_, erro={"code": -32601, "message": f"Método não suportado: {metodo}"})


def main() -> None:
    for linha in sys.stdin.buffer:
        linha = linha.strip()
        if not linha:
            continue
        try:
            msg = json.loads(linha)
        except ValueError:
            continue
        for m in msg if isinstance(msg, list) else [msg]:
            _tratar(m)
