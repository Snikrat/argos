"""O menu da bandeja é montado quando o ícone aparece: se falhar, o ícone nem é criado."""
from argos.app.bandeja import Bandeja


class ApiFalsa:
    def __init__(self):
        self.chamadas = []

    def projetos(self):
        return [{"nome": "loja", "comandos": [{"rotulo": "npm run dev", "chave": ".|npm run dev", "tipo": "processo", "sub": ""},
                                              {"rotulo": "uvicorn", "chave": "backend|uvicorn", "tipo": "processo", "sub": "backend"}]},
                {"nome": "api", "comandos": [{"rotulo": "go run .", "chave": ".|go run .", "tipo": "processo", "sub": ""}]}]

    def iniciar(self, *a):
        self.chamadas.append(("iniciar", a))

    def parar_projeto(self, *a):
        self.chamadas.append(("parar", a))

    def reiniciar_projeto(self, *a):
        self.chamadas.append(("reiniciar", a))


def test_menu_monta_com_projetos_rodando_e_parados():
    api = ApiFalsa()
    b = Bandeja(api, lambda: None, lambda: None, lambda: None, lambda: None)
    b._ativos = ["api"]
    b._em_segundo_plano = lambda f, *args: f(*args)
    itens = b._itens(lambda: None, lambda: None, lambda: None)
    assert bool(b.icone.menu)  # é o que o pystray faz ao mostrar o ícone
    rodando = next(i for i in itens if str(i.text).endswith("api"))
    list(rodando.submenu.items)[1](b.icone)  # Parar
    iniciar = next(i for i in itens if i.text == "Iniciar")
    loja = list(iniciar.submenu.items)[0]
    list(loja.submenu.items)[1](b.icone)  # backend: uvicorn
    assert api.chamadas == [("parar", ("api",)), ("iniciar", ("loja", "backend|uvicorn", False))]
