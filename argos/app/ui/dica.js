// Tooltip ("dica") no lugar do tooltip nativo do Windows.
//
// Funciona com qualquer elemento que tenha `title` (inclusive os criados depois):
// no primeiro hover o texto vai para data-dica e o title some, para o nativo não
// aparecer junto. Também dá para usar data-dica direto. "\n" quebra linha.
// Opcional: data-dica-lado="cima" | "baixo" (padrão: baixo, vira se não couber).
(() => {
  const ATRASO = 450;      // espera antes da primeira dica
  const SEGUIDA = 300;     // logo depois de fechar uma, a próxima aparece na hora (como no Mac)
  const MARGEM = 8;        // distância das bordas da janela
  const DISTANCIA = 6;     // distância do elemento

  const el = document.createElement("div");
  el.className = "dica";
  el.id = "dica";
  el.setAttribute("role", "tooltip");
  el.hidden = true;
  document.body.appendChild(el);

  let alvo = null, timer = null, fechadaEm = 0, vigia = 0;

  function textoDe(a) {
    const t = a.getAttribute("title");
    if (t !== null) {
      // O title pode ser atualizado pelo app a qualquer momento: sempre vale o mais novo
      if (t) a.dataset.dica = t;
      a.removeAttribute("title");
      if (!a.hasAttribute("aria-label") && t && !a.textContent.trim()) a.setAttribute("aria-label", t);
    }
    return a.dataset.dica || "";
  }

  function posicionar() {
    const r = alvo.getBoundingClientRect();
    const d = el.getBoundingClientRect();
    const vw = innerWidth, vh = innerHeight;
    const cabeBaixo = r.bottom + DISTANCIA + d.height <= vh - MARGEM;
    const cabeCima = r.top - DISTANCIA - d.height >= MARGEM;
    const querCima = alvo.dataset.dicaLado === "cima";
    const cima = querCima ? cabeCima || !cabeBaixo : !cabeBaixo && cabeCima;
    const top = cima ? r.top - DISTANCIA - d.height : r.bottom + DISTANCIA;
    const left = Math.min(Math.max(r.left + r.width / 2 - d.width / 2, MARGEM), vw - MARGEM - d.width);
    el.style.top = `${Math.round(top)}px`;
    el.style.left = `${Math.round(left)}px`;
    // A setinha continua apontando para o centro do elemento mesmo quando a dica é empurrada
    el.style.setProperty("--seta", `${Math.round(r.left + r.width / 2 - left)}px`);
    el.dataset.lado = cima ? "cima" : "baixo";
  }

  function mostrar() {
    if (!alvo || !alvo.isConnected) return esconder();
    const texto = alvo.dataset.dica;
    if (!texto) return;
    el.textContent = texto;
    el.hidden = false;
    el.classList.remove("visivel");
    posicionar();
    requestAnimationFrame(() => el.classList.add("visivel"));
    alvo.setAttribute("aria-describedby", "dica");
    // O app redesenha listas a cada ciclo: se o elemento sumir, a dica some junto
    clearInterval(vigia);
    vigia = setInterval(() => { if (!alvo || !alvo.isConnected) esconder(); }, 250);
  }

  function esconder() {
    clearTimeout(timer);
    clearInterval(vigia);
    if (!el.hidden) fechadaEm = Date.now();
    el.hidden = true;
    el.classList.remove("visivel");
    if (alvo) alvo.removeAttribute("aria-describedby");
    alvo = null;
  }

  function agendar(novo, imediato) {
    if (novo === alvo) return;
    esconder();
    if (!textoDe(novo)) return;
    alvo = novo;
    timer = setTimeout(mostrar, imediato || Date.now() - fechadaEm < SEGUIDA ? 0 : ATRASO);
  }

  const procurar = (no) => no instanceof Element ? no.closest("[title], [data-dica]") : null;

  document.addEventListener("pointerover", (e) => {
    if (e.pointerType === "touch") return;
    const novo = procurar(e.target);
    if (novo) agendar(novo, false);
    else if (alvo) esconder();
  });
  document.addEventListener("pointerout", (e) => {
    if (alvo && !alvo.contains(e.relatedTarget)) esconder();
  });
  // Teclado: mostra ao focar com Tab (não ao clicar)
  document.addEventListener("focusin", (e) => {
    const novo = procurar(e.target);
    if (novo && e.target.matches(":focus-visible")) agendar(novo, true);
  });
  document.addEventListener("focusout", () => alvo && esconder());
  for (const ev of ["pointerdown", "keydown", "wheel"]) document.addEventListener(ev, esconder, true);
  addEventListener("scroll", esconder, true);
  addEventListener("blur", esconder);
  addEventListener("resize", esconder);

  window.dica = { esconder };
})();
