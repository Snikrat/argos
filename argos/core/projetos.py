"""Catálogo das pastas de projeto: tipo, comandos para iniciar e porta prevista."""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from argos.config import Config

ARQUIVO_GRUPO = "argos.toml"
ARQUIVO_GRUPO_ANTIGO = "devs.toml"  # nome de antes de o app virar Argos: continua valendo


def arquivo_grupo(pasta: str | Path) -> Path | None:
    for nome in (ARQUIVO_GRUPO, ARQUIVO_GRUPO_ANTIGO):
        if (caminho := Path(pasta) / nome).exists():
            return caminho
    return None
ARQUIVOS_COMPOSE = ("compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml")
SCRIPTS_NODE = ("dev", "start", "serve", "preview", "watch")
PASTAS_DEPENDENCIAS = ("node_modules", ".venv", "venv", ".godot")

# Porta padrão de cada ferramenta quando nada é configurado
PORTAS_PADRAO = [
    ("next", 3000), ("nuxt", 3000), ("react-scripts", 3000), ("astro", 4321),
    ("@angular/cli", 4200), ("@sveltejs/kit", 5173), ("vite", 5173),
    ("webpack-dev-server", 8080), ("@remix-run/dev", 3000), ("gatsby", 8000),
]


def achar_godot() -> str | None:
    for nome in ("godot", "godot4"):
        if caminho := shutil.which(nome):
            return caminho
    for pasta in os.environ.get("PATH", "").split(os.pathsep):
        for c in sorted(glob.glob(os.path.join(pasta, "Godot*_win64.exe")), reverse=True):
            if "console" not in c.lower():
                return c
    return None


def _ler_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _porta_env(pasta: Path) -> int | None:
    for nome in (".env.local", ".env"):
        try:
            m = re.search(r"^\s*PORT\s*=\s*(\d+)", (pasta / nome).read_text(encoding="utf-8"), re.M)
        except OSError:
            continue
        if m:
            return int(m.group(1))
    return None


def porta_explicita(texto: str) -> int | None:
    m = re.search(r"(?:--port[= ]|-p |PORT=)(\d{2,5})", texto) or re.search(r"(?:runserver|serve)\s+(?:[\d.]+:)?(\d{4,5})", texto)
    return int(m.group(1)) if m else None


def _gerenciador_node(pasta: Path) -> str:
    if (pasta / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (pasta / "yarn.lock").exists():
        return "yarn"
    if (pasta / "bun.lockb").exists() or (pasta / "bun.lock").exists():
        return "bun"
    return "npm"


class ErroGrupo(ValueError):
    """argos.toml inválido."""


PRONTO = re.compile(r"^(porta:\d{2,5}|https?://\S+|log:.+)$")


def carregar_grupo(pasta: str | Path) -> list[dict]:
    """Lê o argos.toml e devolve os serviços já na ordem de subida."""
    caminho = arquivo_grupo(pasta) or Path(pasta) / ARQUIVO_GRUPO
    try:
        dados = tomllib.loads(caminho.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ErroGrupo(f"{caminho.name} com erro de sintaxe: {e}") from None
    servicos = dados.get("servico") or []
    if not isinstance(servicos, list) or not servicos:
        raise ErroGrupo(f"{caminho.name} não tem nenhum [[servico]].")
    nomes = set()
    for s in servicos:
        nome = s.get("nome")
        if not isinstance(nome, str) or not nome:
            raise ErroGrupo("Todo [[servico]] precisa de um nome.")
        if nome in nomes:
            raise ErroGrupo(f"Serviço '{nome}' aparece duas vezes.")
        nomes.add(nome)
        if bool(s.get("cmd")) == bool(s.get("docker")):
            raise ErroGrupo(f"'{nome}': use cmd = \"...\" ou docker = \"...\" (um dos dois).")
        if "pronto" in s and not PRONTO.match(str(s["pronto"])):
            raise ErroGrupo(f"'{nome}': pronto deve ser \"porta:5173\", \"http://...\" ou \"log:texto\".")
        s.setdefault("depois", [])
        if isinstance(s["depois"], str):
            s["depois"] = [s["depois"]]
    for s in servicos:
        for d in s["depois"]:
            if d not in nomes:
                raise ErroGrupo(f"'{s['nome']}' depende de '{d}', que não existe.")
    return ordenar_servicos(servicos)


def ordenar_servicos(servicos: list[dict]) -> list[dict]:
    """Ordem respeitando `depois` (mantém a ordem do arquivo quando dá)."""
    restantes = list(servicos)
    feitos: set[str] = set()
    ordem = []
    while restantes:
        pronto = next((s for s in restantes if all(d in feitos for d in s["depois"])), None)
        if pronto is None:
            raise ErroGrupo("Dependência circular em 'depois': " + ", ".join(s["nome"] for s in restantes))
        ordem.append(pronto)
        feitos.add(pronto["nome"])
        restantes.remove(pronto)
    return ordem


def gerar_grupo(pasta: str | Path) -> str:
    """Modelo de argos.toml a partir do que foi detectado no projeto."""
    pasta = Path(pasta)
    blocos = []
    compose = next((pasta / n for n in ARQUIVOS_COMPOSE if (pasta / n).exists()), None)
    if compose:
        portas = re.findall(r"[\"'\s-](\d{2,5}):\d{2,5}", compose.read_text(encoding="utf-8", errors="replace"))
        blocos.append(("containers", {"docker": "*", "pronto": f"porta:{portas[0]}" if portas else None}))
    # Subpastas com app próprio (ex: frontend/ e backend/) viram serviços separados
    for rotulo, sub in subpastas_app(pasta):
        cmds = [c for c in comandos_da_pasta(sub)[1] if c["tipo"] == "processo"]
        if cmds:
            blocos.append((rotulo.replace("/", "-"), {"cmd": cmds[0]["cmd"], "pasta": rotulo,
                                                      "pronto": f"porta:{cmds[0]['porta']}" if cmds[0]["porta"] else None}))
    if len(blocos) <= (1 if compose else 0):
        cmds = [c for c in comandos_da_pasta(pasta)[1] if c["tipo"] == "processo"]
        if cmds:
            blocos.append(("app", {"cmd": cmds[0]["cmd"], "pronto": f"porta:{cmds[0]['porta']}" if cmds[0]["porta"] else None}))
    if not blocos:
        blocos.append(("app", {"cmd": "npm run dev", "pronto": "porta:5173"}))

    linhas = [
        "# argos.toml - como subir este projeto inteiro (botão \"Subir tudo\" ou: argos subir <projeto>)",
        "# Cada [[servico]] sobe em ordem; \"depois\" diz de quem ele depende.",
        "# pronto = quando o serviço está no ar:",
        "#   \"porta:5432\"                  a porta abriu",
        "#   \"http://localhost:8000/docs\"  a URL respondeu",
        "#   \"log:Application startup\"     o texto apareceu no log",
        "# auto = true    reinicia sozinho se cair",
        "",
    ]
    anterior = None
    for nome, s in blocos:
        linhas.append("[[servico]]")
        linhas.append(f'nome = "{nome}"')
        if "docker" in s:
            linhas.append(f'docker = "{s["docker"]}"   # "*" = todos do docker-compose, ou o nome de um serviço')
        else:
            linhas.append(f'cmd = "{s["cmd"]}"')
            if s.get("pasta"):
                linhas.append(f'pasta = "{s["pasta"]}"')
        if s.get("pronto"):
            linhas.append(f'pronto = "{s["pronto"]}"')
        if anterior:
            linhas.append(f'depois = ["{anterior}"]')
        linhas.append("")
        anterior = nome
    return "\n".join(linhas)


def git_info(pasta: str) -> dict | None:
    """Branch, alterações não commitadas e commits a enviar/receber (desde o último fetch)."""
    try:
        from argos.plataforma import SEM_JANELA

        r = subprocess.run(["git", "-C", pasta, "status", "--porcelain=v2", "--branch"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=5, creationflags=SEM_JANELA)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    info = {"branch": "", "alteracoes": 0, "a_enviar": 0, "a_receber": 0, "upstream": False}
    for linha in r.stdout.splitlines():
        if linha.startswith("# branch.head "):
            info["branch"] = linha.split(" ", 2)[2]
        elif linha.startswith("# branch.upstream "):
            info["upstream"] = True
        elif linha.startswith("# branch.ab "):
            m = re.match(r"# branch\.ab \+(\d+) -(\d+)", linha)
            if m:
                info["a_enviar"], info["a_receber"] = int(m.group(1)), int(m.group(2))
        elif linha and not linha.startswith("#"):
            info["alteracoes"] += 1
    return info


# --- detectores por linguagem ----------------------------------------------
# Cada um olha só a própria pasta e devolve (tipo, [comandos]).

def _cmd(rotulo: str, cmd: str, porta: int | None = None, detalhe: str = "", tipo: str = "processo") -> dict:
    return {"rotulo": rotulo, "cmd": cmd, "tipo": tipo, "porta": porta, "detalhe": detalhe or cmd}


def _ler(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _node(pasta: Path):
    pkg_arquivo = pasta / "package.json"
    if not pkg_arquivo.exists():
        return None
    pkg = _ler_json(pkg_arquivo)
    gm = _gerenciador_node(pasta)
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    scripts = pkg.get("scripts", {})
    cmds = []
    for s in SCRIPTS_NODE:
        if s not in scripts:
            continue
        porta = porta_explicita(scripts[s]) or _porta_env(pasta)
        if not porta:
            porta = next((p for d, p in PORTAS_PADRAO if d in deps), None)
            if porta == 5173 and s == "preview":
                porta = 4173
        c = _cmd(f"{gm} run {s}", f"{gm} run {s}", porta, scripts[s])
        c["ferramenta"] = ferramenta_do_script(scripts[s])
        cmds.append(c)
    return "node", cmds


# Ferramentas que aceitam porta pela linha de comando (para as portas fixas)
_FERRAMENTA = re.compile(r"(?:^|[\s/])(vite|next|astro|nuxi|nuxt|react-scripts|ng|remix|gatsby|"
                         r"webpack-dev-server|webpack|svelte-kit)(?=\s|$)")


def ferramenta_do_script(script: str) -> str | None:
    """Ferramenta de um script do package.json, se ele rodar uma só (não 'concurrently ...')."""
    if re.search(r"concurrently|npm-run-all|run-p|turbo|&&|\|\||;", script):
        return None
    m = _FERRAMENTA.search(script.strip())
    return m.group(1) if m else None


def _compose(pasta: Path):
    compose = next((pasta / n for n in ARQUIVOS_COMPOSE if (pasta / n).exists()), None)
    if not compose:
        return None
    portas = [int(h) for h in re.findall(r"[\"'\s-](\d{2,5}):\d{2,5}", _ler(compose))]
    c = _cmd("docker compose up", "docker compose up -d", portas[0] if portas else None, compose.name, "compose")
    c["portas"] = portas
    return "docker", [c]


def _python(pasta: Path):
    pyproject = pasta / "pyproject.toml"
    if not any((pasta / n).exists() for n in ("pyproject.toml", "requirements.txt", "manage.py")):
        return None
    uv = "uv run " if (pasta / "uv.lock").exists() or "[tool.uv" in _ler(pyproject) else ""
    cmds = []
    if (pasta / "manage.py").exists():
        cmds.append({**_cmd("runserver", f"{uv}python manage.py runserver", 8000, "Django"), "ferramenta": "django"})

    # FastAPI/Flask dentro de um pacote (app/main.py, src/main.py...): uvicorn app.main:app
    for rel in ("app/main.py", "src/main.py", "api/main.py", "app/app.py", "main.py", "app.py", "server.py"):
        arq = pasta / rel
        if not arq.exists():
            continue
        texto = _ler(arq)
        m = re.search(r"^(\w+)\s*=\s*FastAPI\(", texto, re.M)
        if m:
            modulo = rel.removesuffix(".py").replace("/", ".")
            porta = porta_explicita(texto) or 8000
            cmds.append({**_cmd(f"uvicorn {modulo}:{m.group(1)}", f"{uv}uvicorn {modulo}:{m.group(1)} --reload --port {porta}",
                                porta, f"FastAPI em {rel}"), "ferramenta": "uvicorn"})
            break
        if "/" not in rel:
            porta = porta_explicita(texto) or (5000 if re.search(r"flask", texto, re.I) else None)
            cmds.append(_cmd(f"python {rel}", f"{uv}python {rel}", porta, rel))
            break

    # Comandos declarados no pyproject ([project.scripts])
    try:
        scripts = tomllib.loads(_ler(pyproject)).get("project", {}).get("scripts", {}) if pyproject.exists() else {}
    except tomllib.TOMLDecodeError:
        scripts = {}
    for nome in list(scripts)[:4]:
        cmds.append(_cmd(nome, f"{uv or 'uv run '}{nome}", None, f"[project.scripts] {nome}"))
    return "python", cmds


def _go(pasta: Path):
    if not (pasta / "go.mod").exists():
        return None
    cmds = []
    if any("package main" in _ler(f) for f in pasta.glob("*.go")):
        cmds.append(_cmd("go run .", "go run .", None, "go.mod"))
    for main in sorted(pasta.glob("cmd/*/main.go"))[:4]:
        cmds.append(_cmd(f"go run ./cmd/{main.parent.name}", f"go run ./cmd/{main.parent.name}", None, "cmd/"))
    return "go", cmds


def _rust(pasta: Path):
    cargo = pasta / "Cargo.toml"
    if not cargo.exists() or "[package]" not in _ler(cargo):
        return None
    return "rust", [_cmd("cargo run", "cargo run", None, "Cargo.toml")]


def _dotnet(pasta: Path):
    projs = list(pasta.glob("*.csproj")) + list(pasta.glob("*.fsproj"))
    if not projs:
        return None
    web = any("Microsoft.NET.Sdk.Web" in _ler(p) for p in projs)
    return "dotnet", [_cmd("dotnet watch", "dotnet watch run", 5000 if web else None, projs[0].name),
                      _cmd("dotnet run", "dotnet run", 5000 if web else None, projs[0].name)]


def _php(pasta: Path):
    if (pasta / "artisan").exists():
        return "php", [_cmd("php artisan serve", "php artisan serve", 8000, "Laravel")]
    if (pasta / "composer.json").exists() and (pasta / "public" / "index.php").exists():
        return "php", [_cmd("php -S (public)", "php -S localhost:8000 -t public", 8000, "public/index.php")]
    return None


def _java(pasta: Path):
    pom, gradle = pasta / "pom.xml", next((pasta / n for n in ("build.gradle", "build.gradle.kts") if (pasta / n).exists()), None)
    if pom.exists() and "spring-boot" in _ler(pom):
        mvn = "mvnw" if (pasta / "mvnw.cmd").exists() else "mvn"
        return "java", [_cmd(f"{mvn} spring-boot:run", f"{mvn} spring-boot:run", 8080, "Spring Boot")]
    if gradle and "spring" in _ler(gradle):
        gr = "gradlew" if (pasta / "gradlew.bat").exists() else "gradle"
        return "java", [_cmd(f"{gr} bootRun", f"{gr} bootRun", 8080, "Spring Boot")]
    if gradle and "application" in _ler(gradle):
        gr = "gradlew" if (pasta / "gradlew.bat").exists() else "gradle"
        return "java", [_cmd(f"{gr} run", f"{gr} run", None, gradle.name)]
    return None


def _deno(pasta: Path):
    arq = next((pasta / n for n in ("deno.json", "deno.jsonc") if (pasta / n).exists()), None)
    if not arq:
        return None
    try:
        tarefas = json.loads(re.sub(r"^\s*//.*$", "", _ler(arq), flags=re.M)).get("tasks", {})
    except ValueError:
        tarefas = {}
    return "deno", [_cmd(f"deno task {t}", f"deno task {t}", porta_explicita(str(tarefas[t])), str(tarefas[t]))
                    for t in SCRIPTS_NODE if t in tarefas]


def _rails(pasta: Path):
    if not (pasta / "bin" / "rails").exists():
        return None
    return "ruby", [_cmd("rails server", "ruby bin/rails server", 3000, "Rails")]


def _make(pasta: Path):
    mk = pasta / "Makefile"
    if not mk.exists():
        return None
    alvos = re.findall(r"^(dev|run|start|serve|up)\s*:", _ler(mk), re.M)
    return ("make", [_cmd(f"make {a}", f"make {a}", None, "Makefile") for a in dict.fromkeys(alvos)]) if alvos else None


DETECTORES = (_node, _compose, _python, _go, _rust, _dotnet, _php, _java, _deno, _rails, _make)

# Subpastas que nunca são um app separado
IGNORAR_SUB = set(PASTAS_DEPENDENCIAS) | {
    "dist", "build", "docs", "doc", "tests", "test", "public", "static", "assets", "src", "lib",
    "scripts", "migrations", "coverage", "tmp", "temp", "logs", "out", "target", "bin", "obj", "vendor",
}
# Pastas de monorepo: os apps ficam um nível abaixo (apps/web, packages/api...)
MONOREPO = {"apps", "packages", "services", "servicos"}


def comandos_da_pasta(pasta: Path) -> tuple[list[str], list[dict]]:
    """Tipos e comandos detectados só nesta pasta (sem olhar subpastas)."""
    tipos, comandos = [], []
    for detector in DETECTORES:
        r = detector(pasta)
        if r:
            tipo, cmds = r
            tipos.append(tipo)
            comandos += cmds
    return tipos, comandos


def subpastas_app(pasta: Path) -> list[tuple[str, Path]]:
    """Subpastas que podem ser apps separados: (rótulo relativo, caminho)."""
    saida = []
    try:
        filhas = sorted(p for p in pasta.iterdir() if p.is_dir() and not p.name.startswith("."))
    except OSError:
        return []
    for sub in filhas:
        if sub.name.lower() in IGNORAR_SUB:
            continue
        if sub.name.lower() in MONOREPO:
            try:
                saida += [(f"{sub.name}/{n.name}", n) for n in sorted(sub.iterdir())
                          if n.is_dir() and not n.name.startswith(".")]
            except OSError:
                pass
        else:
            saida.append((sub.name, sub))
    return saida


def chave_comando(c: dict) -> str:
    return "grupo" if c["tipo"] == "grupo" else f"{c.get('sub') or '.'}|{c['cmd']}"


def detectar(pasta: Path, simples: bool = False) -> dict:
    tipos, comandos = comandos_da_pasta(pasta)
    for c in comandos:
        c["pasta"], c["sub"] = str(pasta), ""

    # Apps em subpastas (frontend/, backend/, apps/web...) com comandos próprios
    if not simples:
        for rotulo, sub in subpastas_app(pasta):
            sub_tipos, sub_cmds = comandos_da_pasta(sub)
            for c in sub_cmds:
                c["pasta"], c["sub"] = str(sub), rotulo
            comandos += sub_cmds
            tipos += [t for t in sub_tipos if t not in tipos]

    jogos = [pasta] if (pasta / "project.godot").exists() else sorted(
        p.parent for p in pasta.glob("*/project.godot"))
    if jogos:
        tipos.append("godot")
        godot = achar_godot()
        for j in jogos if godot else []:
            sufixo = "" if j == pasta else f" ({j.name})"
            caminho = "." if j == pasta else j.name
            for c in (_cmd(f"Abrir no Godot{sufixo}", f'"{godot}" --editor --path "{caminho}"', None, "editor", "godot"),
                      _cmd(f"Rodar jogo{sufixo}", f'"{godot}" --path "{caminho}"', None, "Godot")):
                c["pasta"], c["sub"] = str(pasta), ""
                comandos.append(c)

    if (pasta / "index.html").exists() and not comandos:
        tipos.append("site")
        c = _cmd("servidor estático", "python -m http.server 8080", 8080, "index.html")
        c["pasta"], c["sub"] = str(pasta), ""
        comandos.append(c)

    projeto = {"nome": pasta.name, "pasta": str(pasta), "tipos": tipos, "comandos": comandos,
               "tem_git": (pasta / ".git").exists(), "grupo": None, "erro_grupo": None, "fixo": None}
    if not simples and arquivo_grupo(pasta):
        try:
            servicos = carregar_grupo(pasta)
            projeto["grupo"] = [s["nome"] for s in servicos]
            comandos.insert(0, {**_cmd("Subir tudo", "", None, " → ".join(projeto["grupo"]), "grupo"),
                                "pasta": str(pasta), "sub": ""})
        except ErroGrupo as e:
            projeto["erro_grupo"] = str(e)
    for c in comandos:
        c["chave"] = chave_comando(c)
    if not simples:
        from argos.core import preferencias
        preferencias.aplicar(projeto)
    return projeto


def buscar_comando(projeto: dict, chave: str) -> dict | None:
    return next((c for c in projeto["comandos"] if c["chave"] == chave), None)


def listar(cfg: Config, com_git: bool = True) -> list[dict]:
    saida = []
    for raiz in cfg.pastas_projetos:
        try:
            pastas = sorted(Path(raiz).iterdir(), key=lambda p: p.name.lower())
        except OSError:
            continue
        for p in pastas:
            if p.is_dir() and not p.name.startswith("."):
                saida.append(detectar(p))
    if com_git:
        com_repo = [p for p in saida if p["tem_git"]]
        with ThreadPoolExecutor(max_workers=8) as ex:
            for p, info in zip(com_repo, ex.map(lambda p: git_info(p["pasta"]), com_repo)):
                p["git"] = info
    return saida


def buscar(cfg: Config, nome: str) -> dict | None:
    for p in listar(cfg, com_git=False):
        if p["nome"].lower() == nome.lower():
            return p
    return None


def tamanho_pasta(caminho: str) -> int:
    """Tamanho total, sem seguir links/junções (o pnpm usa muitas)."""
    total, pilha = 0, [caminho]
    while pilha:
        atual = pilha.pop()
        try:
            with os.scandir(atual) as it:
                for e in it:
                    try:
                        if e.is_symlink() or e.is_junction():
                            continue
                        if e.is_dir(follow_symlinks=False):
                            pilha.append(e.path)
                        else:
                            total += e.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def dependencias(pasta: str) -> list[dict]:
    """Pastas regeneráveis (node_modules, .venv...) e quanto ocupam."""
    saida = []
    for nome in PASTAS_DEPENDENCIAS:
        p = Path(pasta) / nome
        if p.is_dir():
            saida.append({"nome": nome, "caminho": str(p), "bytes": tamanho_pasta(str(p))})
    return saida
