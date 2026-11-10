"""Funções chamadas pelo painel (JavaScript) via pywebview.

Atributos públicos são expostos ao JS pelo pywebview, por isso o estado
interno fica em atributos com `_`.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from argos import config
from argos.core import acoes, docker, historico, projetos, registro
from argos.plataforma import (
    abrir_pasta, abrir_terminal, abrir_url, abrir_vscode, copiar_texto, executar_como_admin,
    pasta_inicializacao,
)

LOG_INICIAL = 200_000  # bytes mostrados ao abrir um log


def _r(res: acoes.Resultado) -> dict:
    return res.dict()


class Api:
    def __init__(self, cfg: config.Config, monitor):
        self._cfg = cfg
        self._monitor = monitor
        self._janela = None
        self._sair = lambda: None
        self._conectado = False
        self._maximizada = False
        self._ao_esconder = lambda: None
        self._ao_mostrar = lambda: None

    def _pronto(self, res) -> dict:
        self._monitor.atualizar_agora()
        return _r(res) if isinstance(res, acoes.Resultado) else res

    # --- leitura ---------------------------------------------------------

    def estado(self, desde_evento: int = -1) -> dict:
        """Estado atual. `desde_evento` devolve também os avisos novos (-1 = só o número do último)."""
        est = self._monitor.estado
        for _ in range(50):
            if est:
                break
            time.sleep(0.1)
            est = self._monitor.estado
        eventos = self._monitor.eventos_desde(desde_evento) if desde_evento >= 0 else []
        return {"estado": est, "saude": {str(k): v for k, v in self._monitor.saude.items()},
                "eventos": eventos, "ultimo_evento": self._monitor._seq}

    def atualizar(self) -> bool:
        self._monitor.atualizar_agora()
        return True

    def projetos(self) -> list[dict]:
        from argos.core import ambiente, testes

        lista = projetos.listar(self._cfg)
        for p in lista:
            p["env_faltando"] = ambiente.total_faltando(p["pasta"])
            p["testes"] = testes.resumo(p["nome"])
            p["tem_testes"] = bool(testes.detectar(p["pasta"]))
        return lista

    def dependencias(self, pasta: str) -> list[dict]:
        return projetos.dependencias(pasta)

    def historico(self) -> list[dict]:
        est = self._monitor.estado or {"unidades": []}
        return historico.do_dia([u for u in est["unidades"] if u["categoria"] != "ferramenta"])

    def historico_semana(self) -> list[dict]:
        est = self._monitor.estado or {"unidades": []}
        return historico.da_semana([u for u in est["unidades"] if u["categoria"] != "ferramenta"])

    def logs(self, tipo: str, alvo: str, desde: int = -1) -> dict:
        if tipo == "container":
            return {"texto": docker.logs(alvo, 500), "fim": 0, "vivo": True, "substituir": True}
        if tipo == "arquivo":
            # Só arquivos de log do próprio Argos (ex: resultado de testes)
            p = Path(alvo).resolve()
            if config.PASTA_LOGS.resolve() not in p.parents or not p.is_file():
                return {"texto": "", "fim": 0, "vivo": False, "erro": "Arquivo de log inválido."}
            return {"texto": p.read_text(encoding="utf-8", errors="replace")[-LOG_INICIAL:], "fim": 0,
                    "vivo": False, "arquivo": str(p), "substituir": True}
        e = registro.buscar(alvo)
        if not e:
            return {"texto": "", "fim": 0, "vivo": False, "erro": "Esse processo não está mais no registro."}
        try:
            tamanho = Path(e["log"]).stat().st_size
        except OSError:
            return {"texto": "", "fim": 0, "vivo": e["vivo"], "erro": "Arquivo de log não encontrado."}
        if desde < 0 or desde > tamanho:
            desde = max(0, tamanho - LOG_INICIAL)
        with open(e["log"], "rb") as f:
            f.seek(desde)
            dados = f.read(2_000_000)
        return {"texto": dados.decode("utf-8", errors="replace"), "fim": desde + len(dados),
                "vivo": e["vivo"], "arquivo": e["log"], "substituir": False}

    def docker_disco(self) -> list[dict]:
        return docker.disco() if docker.ligado() else []

    # --- processos -------------------------------------------------------

    def encerrar(self, pid: int) -> dict:
        return self._pronto(acoes.encerrar(int(pid)))

    def encerrar_porta(self, porta: int) -> dict:
        return self._pronto(acoes.encerrar_porta(self._cfg, int(porta)))

    def reiniciar(self, pid: int, gerenciado: str | None = None) -> dict:
        if gerenciado:
            return self._pronto(acoes.reiniciar_gerenciado(gerenciado))
        return self._pronto(acoes.reiniciar_pid(self._cfg, int(pid)))

    def reiniciar_gerenciado(self, id_: str) -> dict:
        return self._pronto(acoes.reiniciar_gerenciado(id_))

    def esquecer(self, id_: str) -> dict:
        registro.esquecer(id_)
        return self._pronto({"ok": True, "msg": "Removido da lista."})

    def parar_projeto(self, nome: str) -> dict:
        return self._pronto(acoes.parar_projeto(self._cfg, nome))

    def reiniciar_projeto(self, nome: str) -> dict:
        return self._pronto(acoes.reiniciar_projeto(self._cfg, nome))

    def iniciar(self, nome: str, chave: str, ignorar_conflito: bool = False) -> dict:
        """Inicia pelo identificador do comando (a ordem da lista muda com o uso)."""
        p = projetos.buscar(self._cfg, nome)
        c = projetos.buscar_comando(p, chave) if p else None
        if not c:
            return {"ok": False, "msg": "Projeto ou comando não encontrado."}
        if c["tipo"] == "grupo":
            from argos.core import preferencias
            preferencias.registrar_uso(p["nome"], c["chave"])
            return self.subir(nome)
        return self._pronto(acoes.iniciar_comando(self._cfg, p, c, ignorar_conflito))

    def fixar(self, nome: str, chave: str | None) -> dict:
        from argos.core import preferencias
        preferencias.fixar(nome, chave or None)
        return {"ok": True, "msg": "Comando fixado como principal." if chave else "Voltou a usar o último comando."}

    def esquecer_recente(self, nome: str, chave: str) -> dict:
        from argos.core import preferencias
        preferencias.esquecer_recente(nome, chave)
        return {"ok": True, "msg": "Removido dos recentes."}

    def ocultar_comando(self, nome: str, chave: str) -> dict:
        from argos.core import preferencias
        preferencias.ocultar(nome, chave)
        return {"ok": True, "msg": "Comando apagado da lista."}

    def restaurar_comandos(self, nome: str, chave: str = "") -> dict:
        from argos.core import preferencias
        preferencias.restaurar(nome, chave or None)
        return {"ok": True, "msg": "Comando restaurado." if chave else "Comandos detectados restaurados."}

    def subir(self, nome: str) -> dict:
        """Sobe o argos.toml em segundo plano; o progresso chega como avisos."""
        p = projetos.buscar(self._cfg, nome)
        if not p:
            return {"ok": False, "msg": "Projeto não encontrado."}
        m = self._monitor

        def trabalho():
            def progresso(msg):
                m.emitir("progresso", p["nome"], msg, windows=False)
                m.atualizar_agora()
            r = acoes.subir_projeto(self._cfg, p, progresso)
            m.emitir("subiu" if r.ok else "falhou", p["nome"], r.msg, nivel="info" if r.ok else "erro",
                     id_=r.extra.get("id"), windows=None)
            m.atualizar_agora()

        threading.Thread(target=trabalho, daemon=True, name=f"subir-{nome}").start()
        return {"ok": True, "msg": f"Subindo {p['nome']}…", "em_andamento": True}

    def servicos(self, nome: str) -> list[dict]:
        """Serviços do argos.toml do projeto, com o que está rodando."""
        p = projetos.buscar(self._cfg, nome)
        return acoes.estado_servicos(self._cfg, p) if p else []

    def servico(self, nome: str, servico: str, op: str) -> dict:
        """Inicia, para ou reinicia um serviço só (iniciar sobe também o que ele precisa)."""
        p = projetos.buscar(self._cfg, nome)
        if not p or op not in ("iniciar", "parar", "reiniciar"):
            return {"ok": False, "msg": "Projeto ou operação inválida."}
        if op == "parar":
            return self._pronto(acoes.parar_servico(self._cfg, p, servico))
        m = self._monitor

        def trabalho(progresso):
            f = acoes.reiniciar_servico if op == "reiniciar" else lambda c, pr, s, prog: acoes.subir_projeto(c, pr, prog, so=s)
            r = f(self._cfg, p, servico, progresso)
            return r.ok, r.msg, {"id_": r.extra.get("id")}

        self._em_segundo_plano(f"{p['nome']} · {servico}", trabalho)
        return {"ok": True, "msg": f"{'Reiniciando' if op == 'reiniciar' else 'Subindo'} {servico}…", "em_andamento": True}

    def buscar_logs(self, nome: str, texto: str) -> list[dict]:
        """Procura `texto` nos logs de todos os processos e containers do projeto."""
        p = projetos.buscar(self._cfg, nome)
        if not p or not texto.strip():
            return []
        achados = registro.buscar_nos_logs(p["nome"], texto)
        alvo = texto.lower().strip()
        for c in ((self._monitor.estado or {}).get("docker", {}).get("containers", []) if self._monitor else []):
            if c["estado"] == "running" and c["projeto"].lower() == p["nome"].lower():
                linhas = [l for l in registro._ANSI.sub("", docker.logs(c["id"], 800)).splitlines() if alvo in l.lower()]
                if linhas:
                    achados.append({"id": c["id"], "nome": c["nome"], "vivo": True, "tipo": "container",
                                    "total": len(linhas), "linhas": linhas[-40:]})
        return achados

    def criar_perfil(self, nome: str, comandos: list[dict]) -> dict:
        from argos.core import sessoes
        comandos = [c for c in comandos or [] if isinstance(c, dict) and c.get("projeto") and c.get("chave")]
        if not nome.strip() or not comandos:
            return {"ok": False, "msg": "Dê um nome ao perfil e escolha pelo menos um comando."}
        s = sessoes.criar_perfil(nome, comandos)
        return {"ok": True, "msg": f"Perfil '{s['nome']}' salvo com {len(s['itens'])} comando(s)."}

    def exportar_config(self) -> dict:
        """Abre o diálogo de salvar e grava a configuração para levar a outra máquina."""
        import webview

        from argos.core import transporte
        escolha = self._janela.create_file_dialog(webview.SAVE_DIALOG, save_filename="argos-config.json",
                                                  file_types=("Configuração do Argos (*.json)",)) if self._janela else None
        if not escolha:
            return {"ok": False, "msg": ""}
        ok, msg = transporte.gravar(self._cfg, escolha if isinstance(escolha, str) else escolha[0])
        return {"ok": ok, "msg": msg}

    def importar_config(self) -> dict:
        import webview

        from argos.core import transporte
        escolha = self._janela.create_file_dialog(webview.OPEN_DIALOG,
                                                  file_types=("Configuração do Argos (*.json)",)) if self._janela else None
        if not escolha:
            return {"ok": False, "msg": ""}
        ok, msg = transporte.importar(self._cfg, escolha if isinstance(escolha, str) else escolha[0])
        return self._pronto({"ok": ok, "msg": msg})

    def criar_grupo(self, nome: str) -> dict:
        p = projetos.buscar(self._cfg, nome)
        if not p:
            return {"ok": False, "msg": "Projeto não encontrado."}
        r = acoes.criar_grupo(p)
        if r.ok:
            caminho = r.extra["caminho"]
            if not abrir_vscode(caminho):
                os.startfile(caminho)
        return _r(r)

    def auto(self, id_: str, ativo: bool) -> dict:
        registro.definir_auto(id_, ativo)
        return self._pronto({"ok": True, "msg": "Reinício automático ligado." if ativo else "Reinício automático desligado."})

    def celular(self, porta: int) -> dict:
        from argos.core import celular
        return celular.info(self._cfg, int(porta))

    def copiar(self, texto: str) -> dict:
        ok = copiar_texto(texto)
        return {"ok": ok, "msg": "" if ok else "Não consegui copiar."}


    def iniciar_personalizado(self, nome: str, cmd: str, sub: str = "") -> dict:
        p = projetos.buscar(self._cfg, nome)
        if not p or not cmd.strip():
            return {"ok": False, "msg": "Projeto ou comando inválido."}
        return self._pronto(acoes.iniciar_personalizado(p, cmd.strip(), sub.strip().strip("\\/")))

    def subpastas(self, nome: str) -> list[str]:
        """Subpastas onde dá para rodar um comando personalizado."""
        p = projetos.buscar(self._cfg, nome)
        return [r for r, _ in projetos.subpastas_app(Path(p["pasta"]))] if p else []

    def apagar_dependencia(self, caminho: str) -> dict:
        # resolve(): sem isso, "projetos\x\..\..\outro\node_modules" passava como "dentro"
        p = Path(caminho).resolve()
        dentro = any(Path(r).resolve() in p.parents for r in self._cfg.pastas_projetos)
        if p.name not in projetos.PASTAS_DEPENDENCIAS or not dentro or not p.is_dir():
            return {"ok": False, "msg": "Só apago node_modules/.venv/venv/.godot dentro dos projetos."}
        shutil.rmtree(p, ignore_errors=True)
        return {"ok": not p.exists(), "msg": f"Apagado: {p.parent.name}\\{p.name}" if not p.exists()
                else "Alguns arquivos estão em uso. Pare o projeto e tente de novo."}

    # --- docker ----------------------------------------------------------

    def container(self, acao: str, id_: str) -> dict:
        f = {"parar": docker.parar, "iniciar": docker.iniciar, "reiniciar": docker.reiniciar}[acao]
        ok, texto = f([id_])
        return self._pronto({"ok": ok, "msg": {"parar": "Container parado.", "iniciar": "Container iniciado.",
                                               "reiniciar": "Container reiniciado."}[acao] if ok else texto})

    def docker_limpar(self, volumes: bool = False) -> dict:
        ok, texto = docker.limpar(volumes)
        return self._pronto({"ok": ok, "msg": texto})

    def docker_ligar(self) -> dict:
        ok, texto = docker.ligar_desktop()
        return self._pronto({"ok": ok, "msg": "Docker Desktop ligado." if ok else texto})

    def docker_desligar(self) -> dict:
        ok, texto = docker.desligar_desktop()
        return self._pronto({"ok": ok, "msg": "Docker Desktop desligado." if ok else texto})

    def modo_jogo(self, desligar_docker: bool = True, wsl: bool = False, lembrar: bool = True) -> dict:
        return self._pronto(acoes.modo_jogo(self._cfg, desligar_docker, wsl, lembrar))

    # --- sessões ---------------------------------------------------------

    def _em_segundo_plano(self, titulo: str, trabalho) -> None:
        """Roda `trabalho(progresso)` numa thread e manda o resultado como aviso."""
        m = self._monitor

        def rodar():
            def progresso(msg):
                m.emitir("progresso", titulo, msg, windows=False)
                m.atualizar_agora()
            try:
                ok, msg, extra = trabalho(progresso)
            except Exception as e:
                ok, msg, extra = False, f"Falhou: {e}", {}
            m.emitir("concluido" if ok else "falhou", titulo, msg, nivel="info" if ok else "erro", **extra)
            m.atualizar_agora()

        threading.Thread(target=rodar, daemon=True).start()

    def sessoes(self) -> list[dict]:
        from argos.core import sessoes
        return sessoes.listar()

    def salvar_sessao(self, nome: str = "") -> dict:
        from argos.core import sessoes
        s = sessoes.salvar(self._monitor.estado or acoes.estado(self._cfg), "manual", nome or "")
        rotulo = f"Perfil '{s['nome']}'" if s["nome"] else "Sessão"
        return self._pronto({"ok": bool(s["itens"]), "msg": f"{rotulo} salvo com {len(s['itens'])} item(ns)."
                             if s["itens"] else "Nada rodando para salvar."})

    def apagar_sessao(self, id_: str) -> dict:
        from argos.core import sessoes
        ok = sessoes.apagar(id_)
        return self._pronto({"ok": ok, "msg": "Sessão apagada." if ok else "Sessão não encontrada."})

    def retomar(self, id_: str | None = None) -> dict:
        from argos.core import sessoes
        self._em_segundo_plano("Retomando", lambda prog: (*sessoes.retomar(id_, prog), {}))
        return {"ok": True, "msg": "Retomando a sessão…", "em_andamento": True}

    def descartar_sessao(self, id_: str) -> dict:
        from argos.core import sessoes
        sessoes.descartar(id_)
        return self._pronto({"ok": True, "msg": "Sessão descartada."})

    # --- portas fixas ----------------------------------------------------

    def definir_porta(self, nome: str, chave: str, porta: int | None) -> dict:
        from argos.core import preferencias
        porta = int(porta) if porta else None
        if porta and not 1 <= porta <= 65535:
            return {"ok": False, "msg": "Porta inválida."}
        dono = next((k for k, v in preferencias.portas_reservadas().items()
                     if v == porta and k != f"{nome.lower()}|{chave}"), None)
        if dono:
            return {"ok": False, "msg": f"A porta {porta} já está reservada para {dono.split('|')[0]}."}
        preferencias.reservar_porta(nome, chave, porta)
        return {"ok": True, "msg": f"Porta fixa: {porta}. Vale na próxima vez que iniciar." if porta
                else "Porta liberada: será escolhida de novo ao iniciar."}

    # --- .env ------------------------------------------------------------

    def ambiente(self, nome: str) -> list[dict]:
        from argos.core import ambiente, preferencias
        p = projetos.buscar(self._cfg, nome)
        analise = ambiente.analisar(p["pasta"]) if p else []
        for a in analise:
            a["usar"] = preferencias.arquivo_env(p["nome"], a["sub"]) or ""
        return analise

    def escolher_env(self, nome: str, sub: str, arquivo: str) -> dict:
        """Arquivo .env cujas variáveis vão no ambiente ao iniciar comandos dessa pasta ("" = padrão)."""
        from argos.core import ambiente, preferencias
        p = projetos.buscar(self._cfg, nome)
        if not p or (arquivo and (not (arquivo == ".env" or arquivo.startswith(".env.")) or ambiente.e_exemplo(arquivo)
                                  or "/" in arquivo or "\\" in arquivo)):
            return {"ok": False, "msg": "Arquivo inválido."}
        preferencias.definir_arquivo_env(p["nome"], sub, arquivo or None)
        return {"ok": True, "msg": f"Os comandos de {sub + '/' if sub else 'raiz'} vão iniciar com {arquivo}." if arquivo
                else "Voltou ao padrão do projeto. Vale na próxima vez que iniciar."}

    def ler_env(self, caminho: str) -> dict:
        from argos.core import ambiente
        if not ambiente.arquivo_valido(caminho, self._cfg.pastas_projetos):
            return {"ok": False, "msg": "Arquivo inválido."}
        return {"ok": True, "texto": Path(caminho).read_text(encoding="utf-8", errors="replace")}

    def salvar_env(self, caminho: str, texto: str) -> dict:
        from argos.core import ambiente
        if not ambiente.arquivo_valido(caminho, self._cfg.pastas_projetos):
            return {"ok": False, "msg": "Arquivo inválido."}
        ambiente.gravar(Path(caminho), texto)
        return {"ok": True, "msg": f"{Path(caminho).name} salvo. Reinicie o servidor para valer."}

    def completar_env(self, pasta: str) -> dict:
        from argos.core import ambiente
        if not any(Path(r).resolve() in Path(pasta).resolve().parents or Path(r).resolve() == Path(pasta).resolve()
                   for r in self._cfg.pastas_projetos):
            return {"ok": False, "msg": "Pasta inválida."}
        ok, msg = ambiente.completar(pasta)
        return {"ok": ok, "msg": msg}

    # --- git -------------------------------------------------------------

    def git_branches(self, nome: str) -> dict:
        from argos.core import git
        p = projetos.buscar(self._cfg, nome)
        return git.branches(p["pasta"]) if p else {"atual": "", "locais": [], "remotas": []}

    def git(self, nome: str, op: str, arg: str = "") -> dict:
        from argos.core import git
        p = projetos.buscar(self._cfg, nome)
        if not p:
            return {"ok": False, "msg": "Projeto não encontrado."}
        com_arg = {"checkout": git.checkout, "checkout_remota": git.checkout_remota, "criar": git.criar}
        sem_arg = {"fetch": git.fetch, "pull": git.pull, "push": git.push}
        if op in com_arg:
            ok, msg = com_arg[op](p["pasta"], arg)
        elif op in sem_arg:
            ok, msg = sem_arg[op](p["pasta"])
        else:
            ok, msg = False, "Operação desconhecida."
        # Com o projeto rodando, o código da outra branch só entra depois de reiniciar
        rodando = op in com_arg and ok and any(a["nome"].lower() == p["nome"].lower() for a in (self._monitor.estado or {}).get("ativos", []))
        return {"ok": ok, "msg": f"{p['nome']}: {msg}", "rodando": rodando}

    # --- testes ----------------------------------------------------------

    def testes(self, nome: str) -> dict:
        from argos.core import testes
        p = projetos.buscar(self._cfg, nome)
        return {"lista": testes.detectar(p["pasta"]), "resultados": testes.resultados(p["nome"])} if p else {}

    def testar(self, nome: str, chave: str | None = None) -> dict:
        from argos.core import testes
        p = projetos.buscar(self._cfg, nome)
        lista = [t for t in testes.detectar(p["pasta"]) if not chave or t["chave"] == chave] if p else []
        if not lista:
            return {"ok": False, "msg": "Nenhum teste encontrado."}

        def trabalho(progresso):
            falhas, ultimo = 0, None
            for t in lista:
                progresso(f"Testando {t['sub'] + '/ ' if t['sub'] else ''}{t['cmd']}…")
                ultimo = testes.rodar(p["nome"], t)
                falhas += not ultimo["ok"]
            msg = (f"Testes passaram ({len(lista)})" if not falhas else f"{falhas} de {len(lista)} falharam") \
                + (f": {ultimo['resumo']}" if ultimo and len(lista) == 1 else "")
            acao = {"rotulo": "Ver log", "tipo": "log-arquivo", "caminho": ultimo["log"]} if falhas else None
            return not falhas, msg, {"acao": acao, "windows": None}

        self._em_segundo_plano(f"Testes · {p['nome']}", trabalho)
        return {"ok": True, "msg": f"Rodando os testes de {p['nome']}…", "em_andamento": True}

    # --- túnel -----------------------------------------------------------

    def tuneis(self) -> list[dict]:
        from argos.core import tunel
        return tunel.ativos()

    def tunel(self, porta: int) -> dict:
        from argos.core import tunel
        from argos.core.coleta import Fotografia
        foto = Fotografia(self._cfg)
        porta = int(porta)
        if porta not in foto.porta_pids:
            return {"ok": False, "msg": f"Nada está usando a porta {porta}."}
        proj = foto.projeto(next(iter(foto.porta_pids[porta])))
        r = tunel.abrir(porta, foto.hosts_teste(porta)[0], proj[0] if proj else "")
        if r.get("url"):
            from argos.core import celular
            r["svg"] = celular.qr_svg(r["url"])
        self._monitor.atualizar_agora()
        return r

    def instalar_cloudflared(self) -> dict:
        from argos.core import tunel
        ok, msg = tunel.instalar()
        return {"ok": ok, "msg": msg}

    # --- Claude (MCP) ----------------------------------------------------

    def instalar_mcp(self) -> dict:
        """Registra o Argos como servidor MCP no Claude Code (`argos mcp --instalar`)."""
        from argos.plataforma import SEM_JANELA, comando_proprio
        r = subprocess.run(comando_proprio() + ["mcp", "--instalar"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60, creationflags=SEM_JANELA)
        saida = (r.stdout + r.stderr).strip().splitlines()
        return {"ok": r.returncode == 0, "msg": saida[0].strip() if saida else "Pronto."}

    # --- atualização -----------------------------------------------------

    def atualizar(self) -> dict:
        from argos.core import atualizacao
        nova = atualizacao.disponivel(self._cfg)
        if not nova:
            return {"ok": True, "msg": "Você já está na versão mais nova."}
        ok, msg = atualizacao.aplicar(nova)
        return {"ok": ok, "msg": msg}

    # --- abrir -----------------------------------------------------------

    def abrir(self, tipo: str, alvo: str) -> dict:
        # O alvo vem da página. Abrir "qualquer coisa" com o Windows executaria um .exe:
        # só endereços http(s) e pastas que existem.
        if tipo == "url" and not str(alvo).lower().startswith(("http://", "https://")):
            return {"ok": False, "msg": "Endereço inválido."}
        if tipo in ("pasta", "vscode", "terminal") and not Path(str(alvo)).is_dir():
            return {"ok": False, "msg": "Essa pasta não existe mais."}
        try:
            if tipo == "url":
                abrir_url(alvo)
            elif tipo == "pasta":
                abrir_pasta(alvo)
            elif tipo == "vscode":
                if not abrir_vscode(alvo):
                    return {"ok": False, "msg": "VS Code não encontrado (comando 'code')."}
            elif tipo == "terminal":
                abrir_terminal(alvo)
            elif tipo == "logs":
                abrir_pasta(str(config.PASTA_LOGS))
        except OSError as e:
            return {"ok": False, "msg": str(e)}
        return {"ok": True}

    def admin(self, args: list[str]) -> dict:
        # Só as ações que o painel oferece repetir como administrador, com alvos simples
        args = [str(a) for a in args or []]
        if not args or args[0] not in ("matar", "porta", "parar", "reiniciar") or len(args) != 2 \
                or not all(c.isalnum() or c in "._-" for c in args[1]):
            return {"ok": False, "msg": "Ação não permitida como administrador."}
        ok = executar_como_admin([*args, "-f"])
        return self._pronto({"ok": ok, "msg": "Executando como administrador..." if ok else "Permissão negada."})

    # --- configuração ----------------------------------------------------

    def _atalho_inicializacao(self) -> Path:
        return pasta_inicializacao() / "argos.lnk"

    def config(self) -> dict:
        from dataclasses import asdict

        from argos import __version__
        if not self._conectado:
            self._conectado = True
            logging.info("painel conectado")
        return {**asdict(self._cfg), "inicializacao": self._atalho_inicializacao().exists(),
                "pasta_dados": str(config.PASTA_DADOS), "versao": __version__}

    def salvar_config(self, dados: dict) -> dict:
        for k in ("pastas_projetos", "intervalo", "alerta_horas", "alerta_orfaos", "atalho", "ignorar",
                  "portas_fixas", "proxy", "ocioso_horas", "git_fetch_minutos", "limite_ram_mb",
                  "procurar_atualizacao"):
            if k in dados:
                setattr(self._cfg, k, config._ajustar(k, dados[k], getattr(self._cfg, k)))
        config.salvar(self._cfg)
        if "inicializacao" in dados:
            self._definir_inicializacao(bool(dados["inicializacao"]))
        return self._pronto({"ok": True, "msg": "Configurações salvas."})

    def _definir_inicializacao(self, ativar: bool) -> None:
        atalho = self._atalho_inicializacao()
        if not ativar:
            atalho.unlink(missing_ok=True)
            return
        if getattr(sys, "frozen", False):
            alvo, args = sys.executable, "--oculto"
        else:
            pyw = Path(sys.executable).with_name("pythonw.exe")
            alvo, args = str(pyw if pyw.exists() else sys.executable), "-m argos.app.principal --oculto"
        script = (
            "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:ARGOS_LNK);"
            "$s.TargetPath=$env:ARGOS_ALVO;$s.Arguments=$env:ARGOS_ARGS;$s.Description='Argos';$s.Save()"
        )
        env = {**os.environ, "ARGOS_LNK": str(atalho), "ARGOS_ALVO": alvo, "ARGOS_ARGS": args}
        subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env,
                       creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)

    # --- janela ----------------------------------------------------------

    def esconder(self) -> bool:
        if self._janela:
            self._janela.hide()
        self._ao_esconder()
        return True

    def em_foco(self) -> bool:
        """A janela voltou (ex: restaurada da barra de tarefas): avisos voltam para o painel."""
        self._ao_mostrar()
        return True

    def minimizar(self) -> bool:
        if self._janela:
            self._janela.minimize()
        self._ao_esconder()
        return True

    def maximizar(self) -> bool:
        """Alterna entre maximizada e o tamanho anterior (botão verde)."""
        if self._janela:
            if self._maximizada:
                self._janela.restore()
            else:
                self._janela.maximize()
            self._maximizada = not self._maximizada
        return self._maximizada

    def redimensionar(self, largura: int, altura: int) -> bool:
        """Sem a borda do Windows, o redimensionamento vem das alças do HTML."""
        if self._janela and not self._maximizada:
            self._janela.resize(max(720, int(largura)), max(480, int(altura)))
        return True

    def sair(self) -> bool:
        self._sair()
        return True

    def reiniciar_app(self) -> bool:
        """Abre uma instância nova (que espera esta fechar) e sai. Para valer o atalho e o proxy."""
        from argos.plataforma import ambiente_externo
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--reinicio"]
        else:
            pyw = Path(sys.executable).with_name("pythonw.exe")
            cmd = [str(pyw if pyw.exists() else sys.executable), "-m", "argos.app.principal", "--reinicio"]
        subprocess.Popen(cmd, env=ambiente_externo(), close_fds=True,
                         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        threading.Timer(0.3, self._sair).start()
        return True
