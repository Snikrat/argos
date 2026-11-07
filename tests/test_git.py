"""Troca de branch: locais, só no servidor e criar nova (com um repositório de verdade)."""
import subprocess

import pytest

from argos.core import git


def g(pasta, *args):
    subprocess.run(["git", "-C", str(pasta), *args], check=True, capture_output=True)


@pytest.fixture
def clone(tmp_path):
    origem = tmp_path / "origem"
    origem.mkdir()
    g(origem, "init", "-b", "main")
    g(origem, "config", "user.email", "t@t")
    g(origem, "config", "user.name", "t")
    (origem / "a.txt").write_text("a")
    g(origem, "add", ".")
    g(origem, "commit", "-m", "inicio")
    g(origem, "branch", "feature/login")
    g(origem, "branch", "corrige-bug")
    subprocess.run(["git", "clone", "-q", str(origem), str(tmp_path / "clone")], check=True, capture_output=True)
    c = tmp_path / "clone"
    g(c, "config", "user.email", "t@t")
    g(c, "config", "user.name", "t")
    return c


def test_lista_locais_e_as_que_so_existem_no_servidor(clone):
    b = git.branches(str(clone))
    assert b["atual"] == "main" and b["locais"] == ["main"]
    assert sorted(r["nome"] for r in b["remotas"]) == ["corrige-bug", "feature/login"]
    assert {r["ref"] for r in b["remotas"]} == {"origin/corrige-bug", "origin/feature/login"}


def test_baixa_branch_do_servidor_ligada_a_ela(clone):
    ok, msg = git.checkout_remota(str(clone), "origin/feature/login")
    assert ok, msg
    b = git.branches(str(clone))
    assert b["atual"] == "feature/login"
    assert "feature/login" not in [r["nome"] for r in b["remotas"]]  # agora é local
    up = subprocess.run(["git", "-C", str(clone), "rev-parse", "--abbrev-ref", "@{u}"], capture_output=True, text=True)
    assert up.stdout.strip() == "origin/feature/login"


def test_cria_branch_nova_e_recusa_nome_invalido(clone):
    assert not git.criar(str(clone), "nome com espaço")[0]
    ok, _ = git.criar(str(clone), "experimento")
    assert ok and git.branches(str(clone))["atual"] == "experimento"
    assert git.criar(str(clone), "experimento") == (False, "Já existe uma branch com esse nome.")


def test_troca_bloqueada_por_alteracao_nao_commitada(clone):
    git.checkout_remota(str(clone), "origin/corrige-bug")
    (clone / "a.txt").write_text("mudou na corrige-bug")
    g(clone, "commit", "-am", "muda")
    g(clone, "checkout", "main")
    (clone / "a.txt").write_text("rascunho")
    ok, msg = git.checkout(str(clone), "corrige-bug")
    assert not ok and "não commitadas" in msg
