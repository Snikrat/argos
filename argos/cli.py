"""argos - o que está rodando de desenvolvimento, no terminal."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from argos import __version__, config
from argos.core import acoes, docker, projetos, registro
from argos.core.coleta import projeto_da_pasta
from argos.plataforma import comando_proprio, encerrar_arvore, executar_como_admin, habilitar_cores_terminal

# --- saída ------------------------------------------------------------------

COR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def c(texto, cod: str) -> str:
    return f"\x1b[{cod}m{texto}\x1b[0m" if COR else str(texto)


def titulo(t: str) -> None:
    print("\n" + c(f"== {t} ==", "1;36"))


def info(t: str) -> None:
    print("  " + c(t, "2"))


def aviso(t: str) -> None:
    print("  " + c(t, "33"))


def sucesso(t: str) -> None:
    for linha in t.splitlines():
        print("  " + c(linha, "32"))


def erro(t: str) -> None:
    for linha in t.splitlines():
        print("  " + c(linha, "31"))


def tabela(linhas: list[dict], colunas: list[str]) -> None:
    if not linhas:
        return
    larg = {k: max(len(k), *(len(str(l.get(k, ""))) for l in linhas)) for k in colunas}
    print("  " + c("  ".join(k.upper().ljust(larg[k]) for k in colunas), "2"))
    for l in linhas:
        cor = l.get("_cor")
        texto = "  ".join(str(l.get(k, "")).ljust(larg[k]) for k in colunas)
        print("  " + (c(texto, cor) if cor else texto))


def desde(ts: float) -> str:
    d = datetime.fromtimestamp(ts)
    return d.strftime("%H:%M") if d.date() == datetime.now().date() else d.strftime("%d/%m %H:%M")


def duracao(seg: float) -> str:
    h, m = int(seg // 3600), int(seg % 3600 // 60)
    return f"{h}h{m:02d}" if h else f"{m}min"


def ram(mb: int | None) -> str:
    if mb is None:
        return "-"
    return f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb} MB"


def confirmar(msg: str, forcar: bool) -> bool:
    if forcar:
        return True
    try:
        return input(f"  {msg} (s/N) ").strip().lower().startswith("s")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def mostrar_resultado(r: acoes.Resultado, forcar: bool) -> int:
    (sucesso if r.ok else erro)(r.msg)
    if r.admin and confirmar("Precisa de administrador. Tentar como admin?", False):
        args = [a for a in sys.argv[1:] if a not in ("-f", "--forcar")] + ["-f"]
        if executar_como_admin(args):
            info("Abrindo como administrador...")
        else:
            erro("Permissão negada.")
    return 0 if r.ok else 1


# --- status -----------------------------------------------------------------

def cmd_status(cfg: config.Config, a) -> int:
    est = acoes.estado(cfg)
    dk = est["docker"]

    titulo("DOCKER")
    if not dk["instalado"]:
        info("Docker não instalado.")
    elif not dk["ligado"]:
        extra = f" (mas o WSL ainda segura {ram(dk['vmmem_mb'])} de RAM)" if dk["vmmem_mb"] else ""
        info("Docker desligado - nenhum container rodando." + extra)
    else:
        info(f"Ligado - RAM da VM do Docker/WSL: {ram(dk['vmmem_mb'])}")
        if dk["containers"]:
            tabela([{
                "projeto": x["projeto"] or "-", "container": x["nome"], "estado": x["estado"],
                "status": x["status"], "portas": ", ".join(f"{h}->{p}" for h, p in x["portas"]),
                "_cor": None if x["estado"] == "running" else "2",
            } for x in dk["containers"]], ["projeto", "container", "estado", "status", "portas"])
        else:
            info("Nenhum container.")

    titulo("PROCESSOS DE DEV")
    unidades = [u for u in est["unidades"] if u["categoria"] != "ferramenta" or a.tudo]
    if unidades:
        tabela([{
            "pid": u["pid"], "projeto": u["projeto"] or "-", "comando": u["nome"],
            "portas": ", ".join(f"{p}" + (f" {u['portas_tipo'][p]}" if u["portas_tipo"].get(p) else "")
                                for p in sorted(u["portas"], key=lambda p: (u["portas_tipo"].get(p) != "site", p))),
            "aberto por": u["origem"],
            "desde": desde(u["inicio"]), "ram": ram(u["ram_mb"]), "logs": "sim" if u["gerenciado"] else "",
            "_cor": "33" if u["orfao"] else None,
        } for u in sorted(unidades, key=lambda u: (u["projeto"] == "", u["projeto"], u["inicio"]))],
            ["pid", "projeto", "comando", "portas", "aberto por", "desde", "ram", "logs"])
    else:
        info("Nenhum processo de desenvolvimento rodando.")

    titulo("PORTAS ABERTAS")
    portas = [p for p in est["portas"] if p["tipo"] != "ferramenta" or a.tudo]
    if portas:
        tabela([{
            "porta": p["porta"], "dono": p["dono"], "projeto": p["projeto"] or "-",
            "acesso": p["acesso"], "endereço": f"http://localhost:{p['porta']}",
        } for p in portas], ["porta", "dono", "projeto", "acesso", "endereço"])
    else:
        info("Nenhuma porta de desenvolvimento aberta.")

    if est["parados"]:
        titulo("PARADOS (iniciados pelo Argos)")
        tabela([{"id": e["id"], "projeto": e["projeto"] or "-", "comando": e["nome"],
                 "parou": desde(e["parado_em"])} for e in est["parados"]],
               ["id", "projeto", "comando", "parou"])
        info("argos reiniciar <id> para subir de novo")

    fs = est["ferramentas"]
    if fs:
        titulo("FERRAMENTAS (Claude, MCP...)")
        for f in fs:
            linha = f"  {f['nome']}: {f['instancias']} instância(s), {ram(f['ram_mb'])}"
            if f["orfas"]:
                linha += c(f"  - {f['orfas']} órfã(s), provavelmente vazada(s)", "33")
            print(linha)
        if not a.tudo:
            info("argos --tudo mostra os processos de cada uma")

    r = est["resumo"]
    if r["orfaos"]:
        print()
        aviso(f"{r['orfaos']} processo(s) órfão(s) (em amarelo): o terminal que os abriu já foi fechado.")
    print("\n" + c("  argos ajuda  -  rodar, reiniciar, logs, parar, porta, iniciar, modo-jogo, app", "2") + "\n")
    return 0


# --- alvos ------------------------------------------------------------------

def _eh_porta(n: int) -> bool:
    foto = acoes.fotografar(config.carregar())
    return n in foto.porta_pids


def cmd_porta(cfg, a) -> int:
    porta = int(a.porta)
    c_ = acoes.conflito_porta(cfg, porta)
    if not c_:
        info(f"Ninguém está usando a porta {porta}.")
        return 0
    if not confirmar(f"Encerrar {c_['dono']} (PID {c_['pid']}, projeto {c_['projeto'] or '-'})?", a.forcar):
        return 1
    return mostrar_resultado(acoes.encerrar_porta(cfg, porta), a.forcar)


def cmd_matar(cfg, a) -> int:
    foto = acoes.fotografar(cfg)
    pid = int(a.pid)
    if pid not in foto.procs:
        erro(f"O processo {pid} não existe.")
        return 1
    proj = foto.projeto(pid)
    if not confirmar(f"Encerrar {foto.nome(pid)} (PID {pid}, projeto {proj[0] if proj else '-'}) e os filhos?", a.forcar):
        return 1
    return mostrar_resultado(acoes.encerrar(pid), a.forcar)


def cmd_parar(cfg, a) -> int:
    unidades, containers = acoes._do_projeto(cfg, a.projeto)
    if not unidades and not containers:
        info(f"Nada rodando do projeto '{a.projeto}'.")
        return 0
    print(f"  Projeto '{a.projeto}': {len(containers)} container(s), {len(unidades)} processo(s).")
    if not confirmar("Parar tudo?", a.forcar):
        return 1
    return mostrar_resultado(acoes.parar_projeto(cfg, a.projeto), a.forcar)


def cmd_reiniciar(cfg, a) -> int:
    alvo = a.alvo
    if alvo.isdigit():
        n = int(alvo)
        r = acoes.reiniciar_porta(cfg, n) if n < 65536 and _eh_porta(n) else acoes.reiniciar_pid(cfg, n)
    elif registro.buscar(alvo):
        r = acoes.reiniciar_gerenciado(alvo)
    else:
        r = acoes.reiniciar_projeto(cfg, alvo)
    return mostrar_resultado(r, a.forcar)


# --- rodar e logs -----------------------------------------------------------

def seguir_log(caminho: str, inicio: int = 0, proc: subprocess.Popen | None = None,
               pid_vivo=None) -> int | None:
    """Mostra o log desde `inicio` e continua acompanhando. Retorna o código de saída se souber."""
    sys.stdout.flush()
    saida = sys.stdout.buffer
    with open(caminho, "rb") as f:
        f.seek(inicio)
        while True:
            bloco = f.read(65536)
            if bloco:
                saida.write(bloco)
                saida.flush()
                continue
            if proc is not None and proc.poll() is not None:
                resto = f.read()
                saida.write(resto)
                saida.flush()
                return proc.returncode
            if pid_vivo is not None and not pid_vivo():
                return None
            time.sleep(0.15)


def cmd_rodar(cfg, a) -> int:
    if not a.comando:
        erro("Diga o comando: argos rodar npm run dev")
        return 1
    cwd = os.getcwd()
    proj = projeto_da_pasta(cwd, cfg)
    nome = subprocess.list2cmdline(a.comando)
    entrada, proc = registro.iniciar(nome, cwd, dict(os.environ), shell=True, nome=nome,
                                     projeto=proj[0] if proj else "", junto=a.junto, auto=a.auto)
    print(c(f"▶ {nome}", "1;32") + c(f"   [id {entrada['id']}{' · ' + proj[0] if proj else ''}]", "2"))
    if a.junto:
        info("Modo junto: fechar este terminal encerra o processo.")
    else:
        info("Fechar este terminal NÃO para o processo (ele continua no Argos). Ctrl+C para parar.")
    if a.auto:
        info("Reinício automático ligado: se cair, o app do Argos sobe de novo.")
    print()

    if not a.junto and hasattr(signal, "SIGBREAK"):
        # Fechar a janela: só sai do acompanhamento, o processo continua
        signal.signal(signal.SIGBREAK, lambda *_: os._exit(0))
    try:
        codigo = seguir_log(entrada["log"], 0, proc=proc, pid_vivo=lambda: registro.vivo(entrada))
    except KeyboardInterrupt:
        registro.marcar_parada(entrada["pid"])
        encerrar_arvore(entrada["pid"])
        print("\n" + c("■ parado", "33"))
        return 130
    if codigo is None:
        print("\n" + c("■ terminou", "2"))
        return 0
    print("\n" + c(f"■ terminou (código {codigo})", "2" if codigo == 0 else "31"))
    return codigo


def cmd_logs(cfg, a) -> int:
    alvo = a.alvo
    e = registro.buscar(alvo)
    est = None
    if not e:
        est = acoes.estado(cfg)
        # PID ou porta de um processo gerenciado
        if alvo.isdigit():
            n = int(alvo)
            u = next((u for u in est["unidades"] if n == u["pid"] or n in u["pids"] or n in u["portas"]), None)
            if u and u["gerenciado"]:
                e = registro.buscar(u["gerenciado"])
            elif u:
                erro(f"'{u['nome']}' foi iniciado fora do Argos, então não tenho os logs dele.")
                info(f"Reinicie pelo Argos para passar a capturar: argos reiniciar {u['pid']}")
                return 1
        else:
            candidatos = [x for x in registro.listar() if x["projeto"].lower() == alvo.lower()]
            if len(candidatos) == 1:
                e = candidatos[0]
            elif len(candidatos) > 1:
                info(f"O projeto '{alvo}' tem {len(candidatos)} processos. Escolha pelo id:")
                tabela([{"id": x["id"], "comando": x["nome"], "rodando": "sim" if x["vivo"] else "não"}
                        for x in candidatos], ["id", "comando", "rodando"])
                return 1

    if e:
        info(f"{e['nome']}  ·  {e['log']}")
        try:
            tamanho = Path(e["log"]).stat().st_size
        except OSError:
            erro("Arquivo de log não encontrado.")
            return 1
        inicio = max(0, tamanho - a.bytes)
        if a.sem_seguir:
            sys.stdout.flush()
            with open(e["log"], "rb") as f:
                f.seek(inicio)
                sys.stdout.buffer.write(f.read())
            return 0
        try:
            seguir_log(e["log"], inicio)
        except KeyboardInterrupt:
            print()
        return 0

    # Container?
    if docker.ligado():
        cont = next((x for x in docker.containers() if alvo in (x["nome"], x["id"]) or
                     x["projeto"].lower() == alvo.lower()), None)
        if cont:
            args = ["docker", "logs", "--tail", "200"] + ([] if a.sem_seguir else ["-f"]) + [cont["id"]]
            if cont["projeto"].lower() == alvo.lower() and cont["nome"] != alvo:
                args = ["docker", "compose", "-p", cont["projeto"], "logs", "--tail", "200"] + ([] if a.sem_seguir else ["-f"])
            try:
                return subprocess.call(args)
            except KeyboardInterrupt:
                return 0
    erro(f"Não achei '{alvo}' (id, PID, porta, projeto ou container).")
    return 1


# --- projetos ---------------------------------------------------------------

def resumo_git(g: dict | None) -> str:
    if not g:
        return ""
    partes = [g["branch"]]
    if g["alteracoes"]:
        partes.append(c(f"{g['alteracoes']} alteração(ões)", "33"))
    if g["a_enviar"]:
        partes.append(c(f"{g['a_enviar']} a enviar", "36"))
    if g["a_receber"]:
        partes.append(c(f"{g['a_receber']} a receber", "35"))
    return " · ".join(partes)


def cmd_projetos(cfg, a) -> int:
    lista = projetos.listar(cfg)
    titulo("PROJETOS")
    for p in lista:
        tipos = ", ".join(p["tipos"]) or "-"
        git = resumo_git(p.get("git"))
        print(f"  {c(p['nome'], '1')}  {c(tipos, '2')}" + (f"  {c('git:', '2')} {git}" if git else ""))
        if p["erro_grupo"]:
            erro(f"   argos.toml: {p['erro_grupo']}")
        for i, cm in enumerate(p["comandos"], 1):
            porta = f"  (porta {cm['porta']})" if cm.get("porta") else ""
            detalhe = f"  ({cm['detalhe']})" if cm["tipo"] == "grupo" else ""
            marca = "  ★ fixo" if cm["chave"] == p["fixo"] else "  · recente" if cm.get("recente") else ""
            pasta = c(f"{cm['sub']}/ ", "36") if cm.get("sub") else ""
            print(f"     {i}. {pasta}{cm['rotulo']}{c(porta + detalhe + marca, '2')}")
    print("\n" + c("  argos iniciar <projeto> [número] [--fixar]  ·  argos subir <projeto> (argos.toml)", "2") + "\n")
    return 0


def cmd_subir(cfg, a) -> int:
    p = projetos.buscar(cfg, a.projeto)
    if not p:
        erro(f"Projeto '{a.projeto}' não encontrado. Veja: argos projetos")
        return 1
    if a.criar:
        r = acoes.criar_grupo(p)
        sucesso(f"{r.msg}  ({r.extra['caminho']})")
        return 0
    if not p["grupo"] and not p["erro_grupo"]:
        erro(f"'{p['nome']}' não tem argos.toml. Crie um modelo com: argos subir {p['nome']} --criar")
        return 1
    r = acoes.subir_projeto(cfg, p, progresso=lambda msg: print("  " + c("›", "36") + " " + msg))
    code = mostrar_resultado(r, a.forcar)
    if not r.ok and r.extra.get("id"):
        info(f"Logs: argos logs {r.extra['id']}")
    return code


def cmd_celular(cfg, a) -> int:
    from argos.core import celular

    porta = a.porta
    if porta is None:
        # Prefere uma porta de site (front-end): é o que se abre no celular
        est = acoes.estado(cfg, com_docker=False)
        candidatas = [(u["portas_tipo"].get(p) != "site", u["portas_tipo"].get(p) == "api", p)
                      for u in est["unidades"] if u["categoria"] != "ferramenta" for p in u["portas"]]
        if not candidatas:
            erro("Nenhum servidor rodando. Diga a porta: argos celular 5173")
            return 1
        porta = sorted(candidatas)[0][2]
    r = celular.info(cfg, porta)
    if not r["ok"]:
        erro(r["msg"])
        return 1
    print()
    celular.qr_terminal(r["url"])
    print("\n  " + c(r["url"], "1;36") + c("   (aponte a câmera do celular, na mesma rede Wi-Fi)", "2"))
    if r["so_local"]:
        aviso(f"Esse servidor só aceita conexões deste PC: {r['dica']}.")
    info("Se não abrir, permita o programa no Firewall do Windows (redes privadas).")
    print()
    return 0


def cmd_iniciar(cfg, a) -> int:
    p = projetos.buscar(cfg, a.projeto)
    if not p:
        erro(f"Projeto '{a.projeto}' não encontrado. Veja: argos projetos")
        return 1
    if not p["comandos"]:
        erro(f"Não sei como iniciar '{p['nome']}'. Entre na pasta e use: argos rodar <comando>")
        return 1
    if a.numero < 1 or a.numero > len(p["comandos"]):
        erro(f"Número inválido. '{p['nome']}' tem {len(p['comandos'])} comando(s).")
        return 1
    cm = p["comandos"][a.numero - 1]
    if a.fixar:
        from argos.core import preferencias
        preferencias.fixar(p["nome"], cm["chave"])
        info(f"'{cm['rotulo']}' fixado como comando principal de {p['nome']}.")
    r = acoes.iniciar_comando(cfg, p, cm, ignorar_conflito=a.forcar)
    if r.conflito:
        k = r.conflito
        aviso(f"A porta {k['porta']} já está em uso por {k['dono']} (PID {k['pid']}).")
        if confirmar("Encerrar e iniciar mesmo assim?", False):
            acoes.encerrar(k["pid"])
            r = acoes.iniciar_comando(cfg, p, cm, ignorar_conflito=True)
        else:
            return 1
    code = mostrar_resultado(r, a.forcar)
    if r.ok and r.extra.get("id"):
        info(f"Logs: argos logs {r.extra['id']}")
    return code


# --- docker e modo jogo -----------------------------------------------------

def cmd_docker(cfg, a) -> int:
    if not docker.instalado():
        info("Docker não instalado.")
        return 0
    if a.acao == "ligar":
        info("Ligando o Docker Desktop...")
        ok, t = docker.ligar_desktop()
        (sucesso if ok else erro)("Ligado." if ok else t)
        return 0 if ok else 1
    if a.acao == "desligar":
        ok, t = docker.desligar_desktop()
        (sucesso if ok else erro)("Docker Desktop desligado." if ok else t)
        return 0 if ok else 1
    if not docker.ligado():
        info(f"Docker desligado. RAM do WSL: {ram(docker.vmmem_mb())}")
        return 0
    titulo("DOCKER - DISCO")
    tabela(docker.disco(), ["tipo", "total", "ativos", "tamanho", "recuperavel"])
    info(f"RAM da VM do Docker/WSL: {ram(docker.vmmem_mb())}")
    if a.acao == "limpar":
        print()
        aviso("Remove containers parados, imagens sem uso, redes sem uso e cache de build.")
        if a.volumes:
            aviso("E TAMBÉM volumes sem uso (dados de bancos parados são apagados!)")
        if confirmar("Limpar?", a.forcar):
            ok, t = docker.limpar(volumes=a.volumes)
            (sucesso if ok else erro)(t)
    else:
        info("argos docker limpar  ·  argos docker desligar  ·  argos docker ligar")
    print()
    return 0


def cmd_modo_jogo(cfg, a) -> int:
    est = acoes.estado(cfg)
    n = est["resumo"]["processos"]
    k = est["resumo"]["containers"]
    print(f"  Modo jogo: encerrar {n} processo(s), parar {k} container(s)"
          + (", desligar o Docker Desktop" if not a.manter_docker else "")
          + (" e desligar o WSL" if a.wsl else "") + ".")
    info("As ferramentas do Claude (MCP) não são tocadas.")
    if not confirmar("Continuar?", a.forcar):
        return 1
    return mostrar_resultado(acoes.modo_jogo(cfg, desligar_docker=not a.manter_docker, desligar_wsl=a.wsl,
                                             lembrar=not a.sem_lembrar), a.forcar)


def cmd_retomar(cfg, a) -> int:
    from argos.core import sessoes

    ok, msg = sessoes.retomar(a.id, progresso=lambda m: print("  " + c("›", "36") + " " + m))
    (sucesso if ok else erro)(msg)
    return 0 if ok else 1


def cmd_sessao(cfg, a) -> int:
    from argos.core import sessoes

    if a.acao == "salvar":
        s = sessoes.salvar(acoes.estado(cfg), "manual", a.nome or "")
        rotulo = f"Perfil '{s['nome']}'" if s["nome"] else f"Sessão {s['id']}"
        (sucesso if s["itens"] else info)(f"{rotulo} salvo com {len(s['itens'])} item(ns)." if s["itens"]
                                          else "Nada rodando para salvar.")
        return 0
    if a.acao == "apagar":
        if not a.nome:
            erro("Diga o id ou o nome: argos sessao apagar <id|nome>")
            return 1
        alvo = next((s for s in sessoes.listar() if a.nome.lower() in (s["id"], s["nome"].lower())), None)
        if not alvo or not sessoes.apagar(alvo["id"]):
            erro(f"Sessão '{a.nome}' não encontrada.")
            return 1
        sucesso("Sessão apagada.")
        return 0
    lista = sessoes.listar()
    if not lista:
        info("Nenhuma sessão salva. O modo jogo salva uma automaticamente.")
        return 0
    titulo("SESSÕES")
    tabela([{"id": s["id"], "perfil": s["nome"] or "-", "quando": desde(s["quando"]), "motivo": s["motivo"],
             "itens": s["processos"] + s["containers"], "projetos": ", ".join(s["projetos"]) or "-",
             "estado": "perfil" if s["nome"] else f"{len(s['falhas'])} falha(s)" if s["falhas"] else "retomada" if s["retomada"] else "pendente",
             "_cor": "2" if s["retomada"] and not s["nome"] else None}
            for s in lista], ["id", "perfil", "quando", "motivo", "itens", "projetos", "estado"])
    info("argos retomar [id|perfil]  ·  argos sessao salvar [perfil]  ·  argos sessao apagar <id|perfil>")
    print()
    return 0


def cmd_tunel(cfg, a) -> int:
    from argos.core import tunel

    if a.porta is None:
        ativos = tunel.ativos()
        if not ativos:
            info("Nenhum túnel aberto. Use: argos tunel <porta>")
        for t in ativos:
            print(f"  :{t['porta']}  →  {c(t['url'] or '(conectando…)', '1;36')}   {c('PID ' + str(t['pid']), '2')}")
        return 0
    if not tunel.cloudflared():
        aviso("O cloudflared (gratuito, da Cloudflare) não está instalado.")
        if not confirmar("Instalar agora pelo winget?", a.forcar):
            return 1
        ok, msg = tunel.instalar()
        (sucesso if ok else erro)(msg)
        if not ok:
            return 1
    foto = acoes.fotografar(cfg)
    if a.porta not in foto.porta_pids:
        erro(f"Nada está usando a porta {a.porta}.")
        return 1
    info("Abrindo o túnel…")
    proj = foto.projeto(next(iter(foto.porta_pids[a.porta])))
    r = tunel.abrir(a.porta, foto.hosts_teste(a.porta)[0], proj[0] if proj else "")
    if not r["ok"]:
        erro(r["msg"])
        return 1
    print("\n  " + c(r["url"], "1;36") + c("   (qualquer pessoa com o link acessa enquanto o túnel estiver aberto)", "2"))
    info(f"Para fechar: argos matar {r['pid']}")
    print()
    return 0


def cmd_testar(cfg, a) -> int:
    from argos.core import testes

    p = projetos.buscar(cfg, a.projeto)
    if not p:
        erro(f"Projeto '{a.projeto}' não encontrado.")
        return 1
    lista = testes.detectar(p["pasta"])
    if not lista:
        info("Não encontrei testes nesse projeto (script test, pytest, go test, cargo test...).")
        return 0
    falhas = 0
    for t in lista:
        onde = f"{t['sub']}/ " if t["sub"] else ""
        print(f"  {c('›', '36')} {onde}{t['cmd']} …", flush=True)
        r = testes.rodar(p["nome"], t)
        falhas += not r["ok"]
        (sucesso if r["ok"] else erro)(f"{'passou' if r['ok'] else 'falhou'}: {r['resumo']} ({r['duracao']:.0f}s)")
        if not r["ok"]:
            info(f"log: {r['log']}")
    return 1 if falhas else 0


def cmd_atualizar(cfg, a) -> int:
    from argos.core import atualizacao

    nova = atualizacao.disponivel(cfg)
    if not nova:
        sucesso(f"Você já está na versão mais nova ({__version__}).")
        return 0
    print(f"  Versão {nova['versao']} disponível (instalada: {nova['atual']}).")
    if not confirmar("Atualizar agora?", a.forcar):
        return 1
    ok, msg = atualizacao.aplicar(nova)
    (sucesso if ok else erro)(msg)
    return 0 if ok else 1


def cmd_mcp(cfg, a) -> int:
    """Registra o Argos como servidor MCP no Claude Code."""
    import shutil

    claude = shutil.which("claude")
    if not claude:
        erro("CLI do Claude Code ('claude') não encontrado.")
        return 1
    cmd = comando_proprio() + ["mcp"]
    # "devs" é o nome de antes de o app virar Argos
    for nome in ("argos", "devs"):
        subprocess.run([claude, "mcp", "remove", "--scope", "user", nome], capture_output=True)
    r = subprocess.run([claude, "mcp", "add", "--scope", "user", "argos", "--", *cmd],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        erro((r.stdout + r.stderr).strip()[-400:])
        return 1
    sucesso("Argos registrado como servidor MCP do Claude Code (vale para novas conversas).")
    info("Comando: " + subprocess.list2cmdline(cmd))
    return 0


def cmd_app(cfg, a) -> int:
    if getattr(sys, "frozen", False):
        args = [str(Path(sys.executable).with_name("argos-app.exe"))]
    else:
        base = comando_proprio()[0]
        pyw = Path(base).with_name("pythonw.exe")
        args = [str(pyw if pyw.exists() else base), "-m", "argos.app.principal"]
    subprocess.Popen(args, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                     close_fds=True)
    sucesso("Painel aberto (ícone perto do relógio).")
    return 0


def cmd_config(cfg, a) -> int:
    config.salvar(cfg)
    info(str(config.ARQUIVO_CONFIG))
    os.startfile(config.ARQUIVO_CONFIG)
    return 0


AJUDA = """
  argos                        mostra Docker, processos, portas e ferramentas
  argos --tudo                 inclui os processos das ferramentas (MCP do Claude...)

  argos rodar <comando>        roda com logs; fechar o terminal não para o processo
                              ex: argos rodar npm run dev      (--junto: para junto com o terminal)
                              --auto: o app reinicia sozinho se cair
  argos subir <projeto>        sobe tudo do argos.toml em ordem (--criar gera um modelo)
  argos celular [porta]        QR code para abrir o servidor no celular
  argos logs <alvo>            acompanha os logs (id, PID, porta, projeto ou container)
  argos reiniciar <alvo>       reinicia (porta, PID, id ou projeto) mantendo pasta e variáveis
  argos parar <projeto>        para containers e processos do projeto
  argos porta <n>              encerra quem está usando a porta
  argos matar <PID>            encerra o processo e os filhos

  argos projetos               lista seus projetos e como iniciar cada um
  argos iniciar <projeto> [n]  inicia o projeto (comando n da lista)

  argos docker [limpar]        disco e RAM do Docker; limpar libera espaço
  argos docker ligar|desligar  liga ou desliga o Docker Desktop
  argos modo-jogo              para tudo, salva a sessão e desliga o Docker (--wsl, --sem-lembrar)
  argos retomar [id|perfil]    sobe de novo o que estava rodando (sessão ou perfil salvo)
  argos sessao [salvar nome]   lista as sessões; com nome, salva um perfil (apagar <id|nome> remove)

  argos tunel <porta>          link público temporário (https://...trycloudflare.com)
  argos testar <projeto>       roda os testes do projeto
  argos atualizar              instala a versão nova do Argos, se houver
  argos mcp --instalar         registra o Argos como ferramenta do Claude Code

  argos app                    abre o painel (ícone perto do relógio)
  argos config                 abre o arquivo de configuração

  -f                          não pede confirmação
"""


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["_lancar"]:
        registro.lancar(argv[1])
        return
    if argv[:1] == ["_interromper"]:  # processo descartável que manda Ctrl+Break a outro console
        from argos.plataforma import interromper_console
        interromper_console(int(argv[1]))
        return
    if argv == ["mcp"]:  # servidor MCP: stdout é só do protocolo
        from argos import mcp
        mcp.main()
        return
    habilitar_cores_terminal()
    p = argparse.ArgumentParser(prog="argos", add_help=False)
    p.add_argument("-f", "--forcar", action="store_true")
    p.add_argument("--tudo", action="store_true")
    p.add_argument("-v", "--versao", action="version", version=f"argos {__version__}")
    sub = p.add_subparsers(dest="cmd")

    def novo(nome, func, *aliases):
        s = sub.add_parser(nome, aliases=list(aliases), add_help=False)
        s.add_argument("-f", "--forcar", action="store_true", default=argparse.SUPPRESS)
        s.set_defaults(func=func)
        return s

    novo("porta", cmd_porta).add_argument("porta", type=int)
    novo("matar", cmd_matar).add_argument("pid", type=int)
    novo("parar", cmd_parar).add_argument("projeto")
    novo("reiniciar", cmd_reiniciar).add_argument("alvo")
    s = novo("subir", cmd_subir)
    s.add_argument("projeto")
    s.add_argument("--criar", action="store_true")
    novo("celular", cmd_celular).add_argument("porta", type=int, nargs="?")
    s = novo("rodar", cmd_rodar)
    s.add_argument("--junto", action="store_true")
    s.add_argument("--auto", action="store_true")
    s.add_argument("comando", nargs=argparse.REMAINDER)
    s = novo("logs", cmd_logs)
    s.add_argument("alvo")
    s.add_argument("--sem-seguir", action="store_true")
    s.add_argument("--bytes", type=int, default=8000)
    novo("projetos", cmd_projetos)
    s = novo("iniciar", cmd_iniciar)
    s.add_argument("projeto")
    s.add_argument("numero", type=int, nargs="?", default=1)
    s.add_argument("--fixar", action="store_true")
    s = novo("docker", cmd_docker)
    s.add_argument("acao", nargs="?", choices=["limpar", "ligar", "desligar"])
    s.add_argument("--volumes", action="store_true")
    s = novo("modo-jogo", cmd_modo_jogo)
    s.add_argument("--wsl", action="store_true")
    s.add_argument("--manter-docker", action="store_true")
    s.add_argument("--sem-lembrar", action="store_true")
    novo("retomar", cmd_retomar).add_argument("id", nargs="?")
    s = novo("sessao", cmd_sessao, "sessoes")
    s.add_argument("acao", nargs="?", choices=["salvar", "listar", "apagar"], default="listar")
    s.add_argument("nome", nargs="?")
    novo("tunel", cmd_tunel, "túnel").add_argument("porta", type=int, nargs="?")
    novo("testar", cmd_testar, "testes").add_argument("projeto")
    novo("atualizar", cmd_atualizar)
    s = novo("mcp", cmd_mcp)
    s.add_argument("--instalar", action="store_true")
    novo("app", cmd_app)
    novo("config", cmd_config)
    novo("ajuda", lambda cfg, a: print(AJUDA) or 0, "help")

    a = p.parse_args(argv)
    cfg = config.carregar()
    func = getattr(a, "func", cmd_status)
    try:
        sys.exit(func(cfg, a) or 0)
    except KeyboardInterrupt:
        print()
        sys.exit(130)
