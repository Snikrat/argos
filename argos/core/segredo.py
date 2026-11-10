"""Variáveis de ambiente dos processos, guardadas cifradas.

Para reiniciar um processo igual ao original o Argos guarda o ambiente dele, e ali
costumam estar chaves de API e tokens. No disco isso fica cifrado com a DPAPI do
Windows (só o mesmo usuário abre); em memória continua um dict comum.
"""

from __future__ import annotations

import base64
import json

from argos.plataforma import desproteger, proteger

# Variáveis da sessão de um assistente de código (quem pediu para iniciar o processo).
# Não pertencem ao projeto e incluem credenciais da sessão: não são repassadas nem guardadas.
DE_SESSAO = ("CLAUDE_CODE_", "CLAUDECODE", "CLAUDE_PID", "CLAUDE_AGENT_SDK_", "SENTRY-TRACE", "BAGGAGE")

_abertos: dict[str, dict] = {}   # texto cifrado -> dict (ler o registro a cada ciclo não decifra de novo)
_fechados: dict[str, str] = {}   # json -> texto cifrado (regravar sem mudança mantém o mesmo texto)


def sem_sessao(env: dict) -> dict:
    return {k: v for k, v in env.items() if not k.upper().startswith(DE_SESSAO)}


def fechar(env: dict) -> str:
    claro = json.dumps(env, ensure_ascii=False, sort_keys=True)
    if claro not in _fechados:
        if len(_fechados) > 300:
            _fechados.clear()
        _fechados[claro] = base64.b64encode(proteger(claro.encode("utf-8"))).decode("ascii")
        _abertos[_fechados[claro]] = env
    return _fechados[claro]


def abrir(texto: str) -> dict:
    """Devolve {} se não der para abrir (arquivo copiado de outra máquina ou usuário)."""
    if texto not in _abertos:
        if len(_abertos) > 300:
            _abertos.clear()
        try:
            _abertos[texto] = json.loads(desproteger(base64.b64decode(texto)).decode("utf-8"))
        except (OSError, ValueError):
            _abertos[texto] = {}
    return dict(_abertos[texto])


def guardar_em(item: dict) -> dict:
    """Cópia de `item` pronta para o disco: `env` vira `env_p` (cifrado)."""
    if "env" not in item:
        return item
    copia = {k: v for k, v in item.items() if k != "env"}
    copia["env_p"] = fechar(item["env"] or {})
    return copia


def ler_de(item: dict) -> dict:
    """Inverso de `guardar_em`. Entradas antigas, com `env` em texto puro, passam direto."""
    if "env_p" in item:
        item["env"] = abrir(item.pop("env_p"))
    return item
