"""Ícone perto do relógio: muda de cor conforme o que está rodando e tem um menu
para iniciar e parar projetos sem abrir a janela."""

from __future__ import annotations

import logging
import math
import threading
import time
from typing import Callable

import pystray
from PIL import Image, ImageDraw

CORES = {
    "nada": (107, 114, 128),
    "rodando": (34, 197, 94),
    "orfao": (245, 158, 11),
}
PROJETOS_VALIDADE = 60  # segundos até reler a lista de projetos do disco


FUNDO = (14, 21, 19, 255)
OLHO = (238, 242, 240, 255)
APAGADO = (44, 58, 53, 255)
ACESOS = {5, 9, 11}  # quais dos 12 "olhos" do anel acendem com a cor do estado


def desenhar(estado: str, t: int = 64, anel: bool | None = None) -> Image.Image:
    """Logo do Argos (o gigante de cem olhos): um olho central cercado por um anel de
    olhos menores. A íris e os olhos acesos têm a cor do estado."""
    s = 4  # desenha maior e reduz: bordas suaves
    T = t * s
    k, c = T / 150, T / 2  # o desenho original é um quadrado de 150 centrado em 0,0
    img = Image.new("RGBA", (T, T), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((k, k, T - k, T - k), radius=34 * k, fill=FUNDO)
    cor = (*CORES[estado], 255)

    def bola(x: float, y: float, r: float, cor_: tuple) -> None:
        d.ellipse((c + (x - r) * k, c + (y - r) * k, c + (x + r) * k, c + (y + r) * k), fill=cor_)

    # Até 32 px o anel vira ruído: fica só o olho, maior
    detalhe = t >= 48 if anel is None else anel
    g = 1.0 if detalhe else 1.8
    if detalhe:
        for i in range(12):
            a = math.radians(i * 30)
            bola(56 * math.cos(a), 56 * math.sin(a), 5, cor if i in ACESOS and estado != "nada" else APAGADO)

    # Olho em amêndoa: duas curvas de Bézier quadráticas (-38,0) → (0,∓34) → (38,0)
    pontos = []
    for lado in (-1, 1):
        for n in range(33):
            u = n / 32 if lado < 0 else 1 - n / 32
            x = (1 - u) ** 2 * -38 + u ** 2 * 38
            y = 2 * (1 - u) * u * 34 * lado
            pontos.append((c + x * g * k, c + y * g * k))
    d.polygon(pontos, fill=OLHO)
    bola(0, 0, 14 * g, cor)
    bola(0, 0, 6 * g, FUNDO)
    return img.resize((t, t), Image.LANCZOS)


class Bandeja:
    def __init__(self, api, abrir: Callable[[], None], modo_jogo: Callable[[], None],
                 abrir_logs: Callable[[], None], sair: Callable[[], None]):
        self._api = api
        self._abrir = abrir
        # Na bandeja o ícone aparece com 16-24 px: sem o anel, mas em alta resolução para telas com zoom
        self._imagens = {k: desenhar(k, 64, anel=False) for k in CORES}
        self._atual = "nada"
        self._ativos: list[str] = []
        self._projetos: list[dict] = []
        self._projetos_em = 0.0
        self.icone = pystray.Icon(
            "argos", self._imagens["nada"], "Argos",
            menu=pystray.Menu(lambda: self._itens(modo_jogo, abrir_logs, sair)),
        )

    # --- menu ---------------------------------------------------------------

    def _em_segundo_plano(self, f, *args) -> None:
        def rodar():
            try:
                r = f(*args)
                if isinstance(r, dict) and r.get("msg") and not r.get("em_andamento"):
                    self.notificar("Argos", r["msg"])
            except Exception as e:
                self.notificar("Argos", f"Falhou: {e}")
        threading.Thread(target=rodar, daemon=True).start()

    def _lista_projetos(self) -> list[dict]:
        if time.time() - self._projetos_em > PROJETOS_VALIDADE:
            try:
                self._projetos = self._api.projetos()
                self._projetos_em = time.time()
            except Exception:
                pass
        return self._projetos

    def _itens(self, modo_jogo, abrir_logs, sair):
        Item, Menu = pystray.MenuItem, pystray.Menu
        itens = [Item("Abrir painel", lambda: self._abrir(), default=True), Menu.SEPARATOR]

        # O pystray só aceita ações com 0 a 2 parâmetros (conta até os que têm valor
        # padrão): por isso a ação é montada aqui em vez de lambda com n=nome
        def acao(f, *args):
            return lambda: self._em_segundo_plano(f, *args)

        for nome in self._ativos:
            itens.append(Item(f"● {nome}", Menu(
                Item("Reiniciar", acao(self._api.reiniciar_projeto, nome)),
                Item("Parar", acao(self._api.parar_projeto, nome)),
            )))

        parados = [p for p in self._lista_projetos() if p["comandos"] and p["nome"] not in self._ativos]
        if parados:
            def item_projeto(p):
                cmds = [c for c in p["comandos"] if c["tipo"] != "godot"] or p["comandos"]
                return Item(p["nome"], Menu(*[
                    Item(f"{c['sub']}: {c['rotulo']}" if c.get("sub") else c["rotulo"],
                         acao(self._api.iniciar, p["nome"], c["chave"], False))
                    for c in cmds[:12]
                ]))
            itens.append(Item("Iniciar", Menu(*[item_projeto(p) for p in parados])))

        itens += [
            Menu.SEPARATOR,
            Item("Modo jogo...", lambda: modo_jogo()),
            Item("Pasta de logs", lambda: abrir_logs()),
            Menu.SEPARATOR,
            Item("Sair do Argos", lambda: sair()),
        ]
        return itens

    # --- ciclo de vida ------------------------------------------------------

    def iniciar(self) -> None:
        threading.Thread(target=self._rodar, daemon=True, name="bandeja").start()

    def _rodar(self) -> None:
        # Erro aqui deixava o app sem ícone e sem nenhum rastro no app.log
        try:
            self.icone.run()
        except Exception:
            logging.exception("o ícone da bandeja falhou")

    def parar(self) -> None:
        try:
            self.icone.stop()
        except Exception:
            pass

    def notificar(self, titulo: str, msg: str) -> None:
        try:
            self.icone.notify(msg, titulo)
        except Exception:
            pass

    def atualizar(self, est: dict) -> None:
        r = est["resumo"]
        if r["orfaos"]:
            estado = "orfao"
        elif r["processos"] or r["containers"]:
            estado = "rodando"
        else:
            estado = "nada"
        partes = []
        if r["processos"]:
            partes.append(f"{r['processos']} processo(s)")
        if r["containers"]:
            partes.append(f"{r['containers']} container(s)")
        if r["portas"]:
            partes.append(f"{r['portas']} porta(s)")
        if r["orfaos"]:
            partes.append(f"{r['orfaos']} órfão(s)")
        dica = "Argos · " + (", ".join(partes) if partes else "nada rodando")
        ativos = [a["nome"] for a in est["ativos"] if a["nome"]]
        try:
            if estado != self._atual:
                self.icone.icon = self._imagens[estado]
                self._atual = estado
            self.icone.title = dica[:127]
            if ativos != self._ativos:
                self._ativos = ativos
                self.icone.update_menu()
        except Exception:
            pass
