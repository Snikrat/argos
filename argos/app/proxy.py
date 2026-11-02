"""Endereços com nome: http://agendamento.localhost em vez de localhost:5173.

Navegadores mandam qualquer *.localhost para este PC. O proxy escuta na porta
80, lê o cabeçalho Host e repassa a conexão inteira (byte a byte, então
WebSocket e recarregamento automático do Vite funcionam) para a porta certa.
Só aceita conexões deste PC.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
import threading
import time

log = logging.getLogger("argos")
LIMITE_CABECALHO = 64 * 1024


def nome_dns(texto: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", texto.lower()).strip("-") or "projeto"


def calcular_rotas(est: dict) -> dict[str, tuple[str, int]]:
    """host -> (ip, porta). Site: projeto.localhost · API: api.projeto.localhost · qualquer porta: 5173.projeto.localhost"""
    rotas: dict[str, tuple[str, int]] = {}
    for u in est["unidades"]:
        if u["categoria"] == "ferramenta" or not u["projeto"] or not u["portas"]:
            continue
        proj = nome_dns(u["projeto"])
        for p in u["portas"]:
            ip = (u.get("portas_hosts", {}).get(p) or ["127.0.0.1"])[0]
            tipo = u.get("portas_tipo", {}).get(p, "")
            rotas[f"{p}.{proj}.localhost"] = (ip, p)
            if tipo == "site":
                rotas.setdefault(f"{proj}.localhost", (ip, p))
            elif tipo == "api":
                rotas.setdefault(f"api.{proj}.localhost", (ip, p))
        # Sem nenhuma porta marcada como site, o nome curto vai para a primeira
        p = u["portas"][0]
        rotas.setdefault(f"{proj}.localhost", ((u.get("portas_hosts", {}).get(p) or ["127.0.0.1"])[0], p))
    return rotas


class Proxy:
    def __init__(self, porta: int = 80):
        self.porta_desejada = porta
        self.porta: int | None = None     # porta em uso (None = não subiu)
        self.rotas: dict[str, tuple[str, int]] = {}
        self.ultimo_uso: dict[int, float] = {}  # porta de destino -> último uso pelo navegador
        self._ativos: dict[int, int] = {}

    def endereco(self, host: str) -> str:
        return f"http://{host}" + ("" if self.porta == 80 else f":{self.porta}")

    def iniciar(self) -> None:
        threading.Thread(target=self._rodar, daemon=True, name="proxy").start()

    def _rodar(self) -> None:
        asyncio.run(self._servir())

    async def _servir(self) -> None:
        for porta in (self.porta_desejada, 8088):
            try:
                servidor = await asyncio.start_server(self._atender, host=["127.0.0.1", "::1"], port=porta,
                                                      limit=LIMITE_CABECALHO)
            except OSError as e:
                log.warning("proxy: porta %s indisponível (%s)", porta, e)
                continue
            self.porta = porta
            log.info("proxy de nomes na porta %s", porta)
            async with servidor:
                await servidor.serve_forever()
        log.warning("proxy de nomes desligado: nenhuma porta disponível")

    async def _atender(self, leitor: asyncio.StreamReader, escritor: asyncio.StreamWriter) -> None:
        try:
            cabecalho = await asyncio.wait_for(leitor.readuntil(b"\r\n\r\n"), 15)
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError, ConnectionError):
            escritor.close()
            return
        m = re.search(rb"^host:\s*([^\r\n:]+)", cabecalho, re.I | re.M)
        host = m.group(1).decode("latin-1").strip().lower() if m else ""
        alvo = self.rotas.get(host)
        if not alvo:
            await self._pagina(escritor, host)
            return
        ip, porta = alvo
        try:
            leitor2, escritor2 = await asyncio.wait_for(asyncio.open_connection(ip, porta), 5)
        except (OSError, asyncio.TimeoutError):
            await self._pagina(escritor, host, f"{host} está registrado, mas a porta {porta} não respondeu.")
            return
        self._ativos[porta] = self._ativos.get(porta, 0) + 1
        self.ultimo_uso[porta] = time.time()
        escritor2.write(cabecalho)
        try:
            await asyncio.gather(self._copiar(leitor, escritor2, porta), self._copiar(leitor2, escritor, porta))
        finally:
            self._ativos[porta] -= 1
            self.ultimo_uso[porta] = time.time()
            for e in (escritor, escritor2):
                e.close()

    async def _copiar(self, origem: asyncio.StreamReader, destino: asyncio.StreamWriter, porta: int) -> None:
        try:
            while dados := await origem.read(65536):
                destino.write(dados)
                await destino.drain()
                self.ultimo_uso[porta] = time.time()
        except (ConnectionError, OSError):
            pass
        finally:
            try:
                destino.write_eof()
            except (OSError, RuntimeError):
                pass

    def em_uso(self, porta: int) -> bool:
        return self._ativos.get(porta, 0) > 0

    async def _pagina(self, escritor: asyncio.StreamWriter, host: str, aviso: str = "") -> None:
        """Página com a lista de endereços (quando o nome não existe ou o servidor caiu)."""
        itens = "".join(
            f'<li><a href="{html.escape(self.endereco(h))}">{html.escape(h)}</a> <span>→ :{p}</span></li>'
            for h, (_, p) in sorted(self.rotas.items()) if not h[0].isdigit())
        corpo = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Argos</title>
<style>body{{font:15px system-ui,sans-serif;max-width:560px;margin:60px auto;padding:0 20px;color:#1d1d1f}}
@media(prefers-color-scheme:dark){{body{{background:#1c1c1e;color:#f5f5f7}}a{{color:#0a84ff}}}}
li{{margin:8px 0}}span{{color:#8e8e93;font-size:13px}}p{{color:#8e8e93}}</style></head><body>
<h2>Argos</h2><p>{html.escape(aviso or (f'Nada rodando em {host}.' if host and host not in ('localhost', 'argos.localhost') else 'Projetos rodando agora:'))}</p>
<ul>{itens or '<li>Nenhum projeto rodando.</li>'}</ul></body></html>""".encode()
        status = b"200 OK" if host in ("localhost", "argos.localhost") else b"404 Not Found"
        escritor.write(b"HTTP/1.1 " + status + b"\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: "
                       + str(len(corpo)).encode() + b"\r\nConnection: close\r\n\r\n" + corpo)
        try:
            await escritor.drain()
        finally:
            escritor.close()
