"""Fotografia do que está rodando: processos de dev agrupados em "unidades", portas e origem.

Uma *unidade* é a raiz de uma árvore de processos de desenvolvimento. Um
`npm run dev` vira node(npm) -> cmd /c -> node(vite); tudo isso é uma unidade
só, cuja raiz é o node do npm. É ela que se encerra ou reinicia.
"""

from __future__ import annotations

import fnmatch
import ntpath
import os
import re
import subprocess
import time
from collections import defaultdict
from pathlib import PureWindowsPath

import psutil

from argos.config import Config
from argos.plataforma import listar_processos

# Programas considerados "de desenvolvimento"
RUNTIMES = {
    "node", "python", "pythonw", "java", "javaw", "dotnet", "go", "deno", "bun", "ruby",
    "php", "php-cgi", "nginx", "httpd", "caddy", "postgres", "mysqld", "redis-server",
    "mongod", "uvicorn", "air", "hugo", "flask", "gunicorn",
}

# Lançadores que só repassam o comando: a raiz da unidade sobe através deles
LANCADORES = {"uv", "uvx", "npx", "pnpm", "yarn", "bunx"}

# Donos de porta que são ruído (Windows, fabricantes, jogos, chat...)
IGNORAR_PORTAS = [
    "system", "idle", "svchost", "lsass", "wininit", "services", "spoolsv", "asus*",
    "armoury*", "rog*", "discord*", "steam*", "epic*", "onedrive*", "msedge*", "chrome*",
    "firefox*", "spotify*", "nvidia*", "nvcontainer", "claude", "code", "explorer",
    "league*", "riot*", "battle.net*", "argos-app", "utweb", "utorrent*", "qbittorrent*", "zoom*",
    "ms-teams*", "teams*", "slack*", "figma*", "adobe*", "creative cloud*", "dropbox*", "googledrive*",
    "whatsapp*", "telegram*", "obs64", "nordvpn*", "parsec*", "anydesk*", "teamviewer*",
]

# Donos de porta que representam containers do Docker
DOCKER_PORTAS = ["com.docker*", "wslrelay", "vpnkit*", "docker*"]

# Quem abriu: nomes de ancestrais reconhecidos
ORIGENS = [
    ("claude", "Claude"), ("code", "VS Code"), ("codex*", "Codex"), ("cursor", "Cursor"),
    ("windowsterminal", "Terminal"), ("pwsh", "Terminal"), ("powershell", "Terminal"),
    ("explorer", "Windows"), ("services", "serviço"), ("argos-app", "Argos"),
]

# Assistentes de código: os servidores MCP que eles abrem são ferramentas, não projetos
ASSISTENTES = ("Claude", "Codex", "Cursor")

PORTA_EFEMERA = 49152

# Pistas, na linha de comando de quem abriu a porta, de que ela é o site (front) ou uma API
PASTAS_SITE = ("\\frontend\\", "\\front\\", "\\web\\", "\\client\\", "\\site\\", "\\app-web\\")
PASTAS_API = ("\\backend\\", "\\back\\", "\\api\\", "\\server\\", "\\servidor\\")
FERRAMENTAS_SITE = ("vite", "next", "react-scripts", "webpack", "astro", "nuxt", "ng serve", "@angular",
                    "svelte", "parcel", "remix", "gatsby", "http.server", "live-server", "storybook")
FERRAMENTAS_API = ("uvicorn", "fastapi", "flask", "manage.py", "gunicorn", "hypercorn", "@nestjs", "nest start",
                   "express", "json-server", "rails", "artisan", "nodemon")


def classificar_porta(cmd: str) -> str:
    """'site', 'api' ou '' (sem pista) a partir da linha de comando."""
    c = cmd.lower().replace("/", "\\")
    if any(p in c for p in PASTAS_SITE):
        return "site"
    if any(p in c for p in PASTAS_API):
        return "api"
    if any(f in c for f in FERRAMENTAS_SITE):
        return "site"
    if any(f in c for f in FERRAMENTAS_API):
        return "api"
    return ""


def nome_curto(nome: str) -> str:
    return re.sub(r"\.exe$", "", nome or "", flags=re.I).lower()


def combina(nome: str, padroes) -> bool:
    return any(fnmatch.fnmatch(nome, p) for p in padroes)


def rotulo_comando(args: list[str]) -> str:
    """Transforma uma linha de comando longa num rótulo legível (ex: 'npm run dev')."""
    if not args:
        return "?"
    a = list(args)
    exe = nome_curto(ntpath.basename(a[0]))
    resto = a[1:]
    # node .../npm-cli.js run dev  ->  npm run dev
    if exe == "node" and resto:
        script = ntpath.basename(resto[0]).lower()
        for marca, nome in (("npm-cli.js", "npm"), ("npx-cli.js", "npx"), ("pnpm.cjs", "pnpm"),
                            ("pnpm.js", "pnpm"), ("yarn.js", "yarn"), ("yarn.cjs", "yarn")):
            if script == marca:
                return _juntar([nome, *resto[1:]])
    # cmd /d /s /c "vite"  ->  vite
    if exe == "cmd":
        for i, x in enumerate(resto):
            if x.lower() == "/c":
                return _juntar(resto[i + 1:])
    return _juntar([exe, *resto])


def _juntar(partes: list[str]) -> str:
    curtas = []
    for p in partes:
        if ("\\" in p or "/" in p) and not p.startswith("-") and not p.startswith("http"):
            p = ntpath.basename(p.rstrip("\\/")) or p
        curtas.append(p)
    texto = " ".join(curtas).strip()
    return texto if len(texto) <= 70 else texto[:67] + "..."


def projeto_da_pasta(caminho: str, cfg: Config) -> tuple[str, str] | None:
    """Se `caminho` está dentro de uma pasta de projetos, retorna (nome, pasta_do_projeto)."""
    if not caminho:
        return None
    alvo = caminho.lower()
    for raiz in cfg.pastas_projetos:
        r = str(PureWindowsPath(raiz)).rstrip("\\").lower() + "\\"
        i = alvo.find(r)
        if i >= 0:
            depois = caminho[i + len(r):]
            nome = re.split(r'[\\/"]', depois)[0]
            if nome:
                return nome, str(PureWindowsPath(raiz) / nome)
    return None


class Fotografia:
    """Estado de todos os processos e portas num instante."""

    def __init__(self, cfg: Config, gerenciados: dict[int, dict] | None = None):
        self.cfg = cfg
        self.momento = time.time()
        # pid -> entrada do registro (processos iniciados pelo Argos)
        self.gerenciados = gerenciados or {}
        self.procs: dict[int, dict] = {}
        self.filhos: dict[int, list[int]] = defaultdict(list)
        self._args: dict[int, list[str]] = {}
        self._cwd: dict[int, str] = {}
        self._ram: dict[int, int] = {}
        self._criado: dict[int, float] = {}

        # create_time é lido só quando preciso: em processos protegidos do
        # sistema o psutil cai num caminho lento (segundos para a lista toda)
        for pid, ppid, nome in listar_processos():
            self.procs[pid] = {"nome": nome_curto(nome), "ppid": ppid}
        for pid, d in self.procs.items():
            if d["ppid"] in self.procs and d["ppid"] != pid:
                self.filhos[d["ppid"]].append(pid)

        # porta -> {pids}, porta -> {enderecos}
        self.porta_pids: dict[int, set[int]] = defaultdict(set)
        self.porta_ips: dict[int, set[str]] = defaultdict(set)
        self.pid_portas: dict[int, set[int]] = defaultdict(set)
        try:
            conexoes = psutil.net_connections("tcp")
        except psutil.Error:
            conexoes = []
        # Conexões abertas em cada porta: mostram se o servidor está sendo usado.
        # As do próprio Argos (verificação de saúde) não contam.
        self.conexoes_porta: dict[int, list[int]] = defaultdict(list)
        portas_proprias: set[int] = set()
        proprio = os.getpid()
        for c in conexoes:
            if c.status == psutil.CONN_ESTABLISHED and c.laddr and c.raddr:
                if c.pid == proprio:
                    portas_proprias.add(c.laddr.port)
                else:
                    self.conexoes_porta[c.laddr.port].append(c.raddr.port)
                continue
            if c.status != psutil.CONN_LISTEN or not c.laddr:
                continue
            self.porta_pids[c.laddr.port].add(c.pid or 0)
            self.porta_ips[c.laddr.port].add(c.laddr.ip)
            if c.pid:
                self.pid_portas[c.pid].add(c.laddr.port)
        for porta, clientes in self.conexoes_porta.items():
            self.conexoes_porta[porta] = [p for p in clientes if p not in portas_proprias]

    # --- acesso preguiçoso (ler linha de comando é caro) ------------------

    def nome(self, pid: int) -> str:
        return self.procs.get(pid, {}).get("nome", "?")

    def args(self, pid: int) -> list[str]:
        if pid not in self._args:
            try:
                self._args[pid] = psutil.Process(pid).cmdline()
            except psutil.Error:
                self._args[pid] = []
        return self._args[pid]

    def cmdline(self, pid: int) -> str:
        return subprocess.list2cmdline(self.args(pid))

    def cwd(self, pid: int) -> str:
        if pid not in self._cwd:
            try:
                self._cwd[pid] = psutil.Process(pid).cwd()
            except psutil.Error:
                self._cwd[pid] = ""
        return self._cwd[pid]

    def criado(self, pid: int) -> float:
        if pid not in self._criado:
            try:
                self._criado[pid] = psutil.Process(pid).create_time()
            except psutil.Error:
                self._criado[pid] = 0.0
        return self._criado[pid]

    def ram(self, pid: int) -> int:
        if pid not in self._ram:
            try:
                self._ram[pid] = psutil.Process(pid).memory_info().rss
            except psutil.Error:
                self._ram[pid] = 0
        return self._ram[pid]

    # --- árvore -----------------------------------------------------------

    def pai(self, pid: int) -> int | None:
        """PID do pai real. O Windows reaproveita PIDs, então o pai precisa ser mais velho."""
        d = self.procs.get(pid)
        if not d:
            return None
        pp = d["ppid"]
        if pp not in self.procs or pp == pid or self.criado(pp) > self.criado(pid) + 1:
            return None
        return pp

    def descendentes(self, pid: int) -> list[int]:
        saida, pilha = [], [f for f in self.filhos.get(pid, []) if self.pai(f) == pid]
        while pilha:
            f = pilha.pop()
            saida.append(f)
            pilha.extend(x for x in self.filhos.get(f, []) if self.pai(x) == f)
        return saida

    def _sobe_para(self, pid: int) -> bool:
        """O pai `pid` faz parte da mesma unidade?"""
        n = self.nome(pid)
        if n in RUNTIMES or n in LANCADORES:
            return True
        if n == "cmd":
            return bool(re.search(r"(^|\s)/[cC](\s|$)", self.cmdline(pid)))
        return False

    def raiz(self, pid: int) -> int:
        atual = pid
        for _ in range(12):
            if atual in self.gerenciados:
                return atual
            pai = self.pai(atual)
            if not pai or not self._sobe_para(pai):
                return atual
            atual = pai
        return atual

    def gerenciado_de(self, pid: int) -> dict | None:
        atual = pid
        for _ in range(12):
            if atual in self.gerenciados:
                return self.gerenciados[atual]
            atual = self.pai(atual)
            if not atual:
                return None
        return None

    def origem(self, raiz: int) -> tuple[str, bool]:
        """(quem abriu, órfão?)"""
        if raiz in self.gerenciados:
            return "Argos", False
        pai = self.pai(raiz)
        if not pai:
            return "órfão", True
        # Um app (Claude, VS Code...) em qualquer ponto da cadeia vence o terminal
        # que ele usa por baixo; o terminal vence o Windows.
        achados = []
        atual = pai
        for _ in range(12):
            n = self.nome(atual)
            achados += [rotulo for padrao, rotulo in ORIGENS if fnmatch.fnmatch(n, padrao)]
            atual = self.pai(atual)
            if not atual:
                break
        for preferido in ("Claude", "VS Code", "Codex", "Cursor", "Argos", "Terminal"):
            if preferido in achados:
                return preferido, False
        return (achados[0] if achados else self.nome(pai)), False

    def projeto(self, pid: int) -> tuple[str, str] | None:
        atual = pid
        for _ in range(4):
            for texto in (self.cwd(atual), self.cmdline(atual)):
                achado = projeto_da_pasta(texto, self.cfg)
                if achado:
                    return achado
            atual = self.pai(atual)
            if not atual:
                break
        return None

    def categoria(self, pid: int, projeto, origem: str = "") -> str:
        # Olha também os filhos: um lançador "python -c ..." pode esconder a ferramenta real
        cmd = " ".join(self.cmdline(x) for x in [pid, *self.descendentes(pid)[:6]]).lower()
        if re.search(r"\\uv\\(cache|tools)\\|\\_npx\\|\\npm-cache\\|\\\.cache\\", cmd):
            return "ferramenta"
        if "mcp" in cmd:
            # Servidor MCP aberto por um assistente é ferramenta dele. Mas um projeto seu pode
            # ter "mcp" no nome, ou ser um servidor MCP que você está desenvolvendo e rodou
            # do terminal: aí é projeto. O nome da pasta do projeto, sozinho, não conta.
            fora_do_nome = "mcp" in (cmd.replace(projeto[1].lower(), "") if projeto else cmd)
            if not projeto or (fora_do_nome and origem in ASSISTENTES):
                return "ferramenta"
            if not fora_do_nome and origem in ASSISTENTES and re.search(r"\\\.venv\\|\\node_modules\\", cmd):
                return "ferramenta"
        if projeto:
            return "projeto"
        if re.search(r"\\appdata\\|\\\.cache\\|\\program files", cmd):
            return "ferramenta"
        return "outro"

    # --- unidades ---------------------------------------------------------

    def unidades(self) -> list[dict]:
        grupos: dict[int, list[int]] = defaultdict(list)
        for pid, d in self.procs.items():
            if d["nome"] in RUNTIMES or pid in self.gerenciados:
                grupos[self.raiz(pid)].append(pid)
        # Binários compilados (Go, Rust, C#...) não têm nome conhecido: entram quando
        # escutam numa porta e rodam de dentro de uma pasta de projeto
        ruido = IGNORAR_PORTAS + DOCKER_PORTAS + [x.lower() for x in self.cfg.ignorar]
        for pid in list(self.pid_portas):
            d = self.procs.get(pid)
            if not d or d["nome"] in RUNTIMES or pid in self.gerenciados or combina(d["nome"], ruido):
                continue
            if projeto_da_pasta(self.cwd(pid), self.cfg) or projeto_da_pasta(self.cmdline(pid), self.cfg):
                grupos[self.raiz(pid)].append(pid)
        # O próprio Argos (e o lançador da venv que o abriu) não aparece
        grupos.pop(self.raiz(os.getpid()), None)

        saida = []
        for raiz in grupos:
            arvore = [raiz, *self.descendentes(raiz)]
            portas = sorted({p for x in arvore for p in self.pid_portas.get(x, ())})
            # Cada porta é classificada pelo processo que a abriu (ex: vite em frontend\ = site)
            portas_tipo = {}
            for p in portas:
                dono = next((x for x in arvore if p in self.pid_portas.get(x, ())), raiz)
                portas_tipo[p] = classificar_porta(self.cmdline(dono))
            proj = self.projeto(raiz)
            ger = self.gerenciado_de(raiz)
            origem, orfao = self.origem(raiz)
            cat = "projeto" if ger else self.categoria(raiz, proj, origem)
            publica = any(ip not in ("127.0.0.1", "::1") for p in portas for ip in self.porta_ips[p])
            saida.append({
                "id": f"p{raiz}",
                "pid": raiz,
                "programa": self.nome(raiz),
                "nome": ger["nome"] if ger else rotulo_comando(self.args(raiz)),
                "cmd": self.cmdline(raiz),
                "projeto": (ger or {}).get("projeto") or (proj[0] if proj else ""),
                "pasta": (ger or {}).get("cwd") or (proj[1] if proj else self.cwd(raiz)),
                "categoria": cat,
                "portas": portas,
                "portas_tipo": portas_tipo,
                "portas_hosts": {p: self.hosts_teste(p) for p in portas},
                "conexoes": sum(len(self.conexoes_porta.get(p, [])) for p in portas),
                "acesso": "rede local" if publica else "só este PC",
                "ram_mb": round(sum(self.ram(x) for x in arvore) / 2**20),
                "inicio": self.criado(raiz),
                "origem": origem,
                "orfao": orfao,
                "gerenciado": ger["id"] if ger else None,
                "pids": arvore,
            })
        saida.sort(key=lambda u: u["inicio"])
        return saida

    def portas_dev(self, unidades: list[dict], containers: list[dict]) -> list[dict]:
        """Portas abertas relevantes (sem o ruído do sistema)."""
        por_pid = {pid: u for u in unidades for pid in u["pids"]}
        host_container = {}
        for c in containers:
            for h, _ in c.get("portas", []):
                host_container[h] = c
        ignorar = IGNORAR_PORTAS + [x.lower() for x in self.cfg.ignorar]
        saida = []
        for porta, pids in sorted(self.porta_pids.items()):
            pid = next(iter(pids))
            nome = self.nome(pid)
            u = por_pid.get(pid)
            c = host_container.get(porta)
            if c or combina(nome, DOCKER_PORTAS):
                if not c and porta >= PORTA_EFEMERA:
                    continue
                saida.append({
                    "porta": porta, "pid": pid, "programa": "Docker",
                    "projeto": (c or {}).get("projeto", ""), "dono": (c or {}).get("nome", "container"),
                    "tipo": "container", "unidade": None,
                    "acesso": self._acesso(porta),
                })
                continue
            if combina(nome, ignorar):
                continue
            if porta >= PORTA_EFEMERA and not u:
                continue
            saida.append({
                "porta": porta, "pid": pid, "programa": nome,
                "projeto": (u or {}).get("projeto", ""), "dono": (u or {}).get("nome", nome),
                "tipo": (u or {}).get("categoria", "outro"), "unidade": (u or {}).get("id"),
                "acesso": self._acesso(porta),
            })
        return saida

    def hosts_teste(self, porta: int) -> list[str]:
        """Endereços onde a porta escuta, para testar sem esperar timeout nos outros."""
        ips = self.porta_ips.get(porta, set())
        hosts = []
        if ips & {"127.0.0.1", "0.0.0.0"} or any(ip.count(".") == 3 for ip in ips):
            hosts.append("127.0.0.1")
        if ips & {"::1", "::"}:
            hosts.append("::1")
        return hosts or ["127.0.0.1", "::1"]

    def _acesso(self, porta: int) -> str:
        return "rede local" if any(ip not in ("127.0.0.1", "::1") for ip in self.porta_ips[porta]) else "só este PC"

    def nome_ferramenta(self, u: dict) -> str:
        """Nome estável de uma ferramenta (ex: servidor MCP), para achar duplicados."""
        if u["projeto"]:
            return u["projeto"]
        args = self.args(u["pid"])
        for i, a in enumerate(args):
            if a == "-m" and i + 1 < len(args):
                return args[i + 1]
        for a in args[1:]:
            if re.search(r"\.(py|js|mjs|cjs|exe)$", a, re.I):
                return ntpath.basename(a)
        for x in u["pids"]:
            if self.nome(x) not in RUNTIMES:
                return self.nome(x)
        return u["programa"]
