"""Tudo que depende do sistema operacional fica aqui.

Hoje só existe a implementação de Windows; para Mac/Linux basta criar
`mac.py`/`linux.py` com as mesmas funções e escolher abaixo.
"""

import sys

if sys.platform == "win32":
    from argos.plataforma.windows import *  # noqa: F401,F403
else:
    raise SystemExit("argos: por enquanto só funciona no Windows.")
