"""Gera o argos.ico a partir do mesmo desenho do ícone da bandeja.

Cada tamanho é desenhado à parte (em vez de reduzir o maior): nos pequenos o
anel de olhos sai e o olho central cresce, para continuar legível.
"""
import sys

from argos.app.bandeja import desenhar

TAMANHOS = [16, 20, 24, 32, 40, 48, 64, 128, 256]
imagens = [desenhar("rodando", t) for t in TAMANHOS]
imagens[-1].save(sys.argv[1], sizes=[(t, t) for t in TAMANHOS], append_images=imagens[:-1])
