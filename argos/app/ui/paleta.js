"use strict";
// Paleta de comandos.

// --- paleta de comandos (Ctrl+K) ----------------------------------------

const normalizar = (s) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

function itensPaleta() {
  const it = [];
  const add = (titulo, sub, icone, f) => it.push({ titulo, sub, icone, f });
  if (E) {
    for (const a of E.ativos.filter((a) => a.nome)) {
      add(`Parar ${a.nome}`, "projeto rodando", "parar", () => ACOES["parar-projeto"]({ nome: a.nome }));
      add(`Reiniciar ${a.nome}`, "projeto rodando", "reiniciar", () => ACOES["reiniciar-projeto"]({ nome: a.nome }));
    }
    for (const u of E.unidades.filter((u) => u.categoria !== "ferramenta")) {
      const onde = u.projeto || "sem projeto";
      if (u.gerenciado) add(`Logs: ${u.nome}`, onde, "logs", () => abrirLogs("processo", u.gerenciado, u.nome));
      for (const p of u.portas) {
        const t = u.portas_tipo?.[p];
        const rot = t === "site" ? "site " : t === "api" ? "API " : "";
        add(`Abrir ${rot}localhost:${p}`, `${onde} · ${u.nome}`, "rodando", () => api.abrir("url", `http://localhost:${p}`));
        if (t !== "api") add(`Celular: ${rot}localhost:${p}`, `${onde} · QR code`, "celular", () => abrirCelular(p, u.id));
      }
    }
    for (const c of E.docker.containers.filter((c) => c.estado === "running")) {
      add(`Logs: ${c.nome}`, "container", "logs", () => abrirLogs("container", c.id, c.nome));
    }
  }
  for (const p of projetosCache || []) {
    p.comandos.forEach((c) => add(c.tipo === "grupo" ? `Subir tudo: ${p.nome}` : c.sub ? `${c.sub}: ${c.rotulo}` : c.rotulo,
      `iniciar ${p.nome}`, "play", () => ACOES.iniciar({ projeto: p.nome, chave: c.chave })));
    add(`VS Code: ${p.nome}`, "abrir projeto", "codigo", () => api.abrir("vscode", p.pasta));
    add(`Terminal: ${p.nome}`, "abrir na pasta", "terminal", () => api.abrir("terminal", p.pasta));
    add(`Pasta: ${p.nome}`, "abrir no Explorer", "pasta", () => api.abrir("pasta", p.pasta));
  }
  if (E && E.sessao) add("Retomar sessão salva", `${E.sessao.processos + E.sessao.containers} itens · ${hora(E.sessao.quando)}`, "retomar", () => ACOES.retomar({ id: E.sessao.id }));
  add("Salvar sessão agora", "lembrar o que está rodando", "retomar", () => ACOES["salvar-sessao"]());
  if (E) {
    for (const [host, porta] of Object.entries((E.proxy && E.proxy.rotas) || {})) {
      if (/^\d/.test(host)) continue;
      add(`Abrir ${host}`, `porta ${porta}`, "mundo", () => api.abrir("url", enderecoNome(host)));
    }
    for (const u of E.unidades.filter((u) => u.categoria !== "ferramenta" && u.portas.length)) {
      add(`Link público: ${u.projeto || u.nome}`, `túnel para a porta ${portaSite(u)}`, "mundo", () => abrirTunel(portaSite(u)));
    }
  }
  for (const p of (projetosCache || []).filter((p) => p.tem_testes)) {
    add(`Testar ${p.nome}`, "rodar os testes", "teste", () => ACOES.testar({ projeto: p.nome }));
  }
  ABAS.forEach((a) => add(`Ir para ${a.rot}`, "seção", a.id, () => trocarAba(a.id)));
  if (E && E.docker.instalado) {
    if (E.docker.ligado) add("Desligar o Docker Desktop", "docker", "docker", () => ACOES["docker-desligar"]());
    else add("Ligar o Docker Desktop", "docker", "docker", () => ACOES["docker-ligar"]());
  }
  for (const p of (projetosCache || []).filter((p) => p.git)) {
    add(`Trocar branch · ${p.nome}`, p.git.branch, "git", () => abrirBranches(p.nome));
  }
  for (const a of (E ? E.ativos : []).filter((a) => a.nome)) {
    add(`Buscar nos logs · ${a.nome}`, "todos os serviços", "busca", () => abrirBuscaLogs(a.nome));
  }
  add("Modo jogo", "parar tudo e liberar memória", "jogo", () => abrirModoJogo());
  add("Sessões e perfis", "salvar e retomar conjuntos de projetos", "retomar", () => abrirSessoes());
  add("Configurações", "Argos", "config", () => abrirConfig());
  return it;
}

function filtrarPaleta(itens, q) {
  const palavras = normalizar(q).split(/\s+/).filter(Boolean);
  if (!palavras.length) return itens.slice(0, 40);
  return itens
    .map((i) => {
      const t = normalizar(i.titulo), s = normalizar(i.sub);
      if (!palavras.every((p) => t.includes(p) || s.includes(p))) return null;
      const nota = (t.startsWith(palavras[0]) ? 0 : 1) + (palavras.every((p) => t.includes(p)) ? 0 : 1);
      return [nota, i];
    })
    .filter(Boolean)
    .sort((a, b) => a[0] - b[0])
    .slice(0, 40)
    .map(([, i]) => i);
}

async function abrirPaleta() {
  if ($("#paleta")) return;
  const caixa = document.createElement("div");
  caixa.id = "paleta";
  caixa.innerHTML = `<div class="paleta-fundo"></div><div class="paleta" role="dialog" aria-label="Comandos">
    <label class="paleta-busca">${IC.busca}<input placeholder="Iniciar, parar, abrir, logs…" spellcheck="false"></label>
    <div class="paleta-lista" role="listbox"></div></div>`;
  document.body.appendChild(caixa);
  const input = caixa.querySelector("input"), lista = caixa.querySelector(".paleta-lista");
  let itens = itensPaleta(), vis = [], sel = 0;

  const desenhar = () => {
    vis = filtrarPaleta(itens, input.value);
    sel = Math.min(sel, Math.max(0, vis.length - 1));
    lista.innerHTML = vis.length ? vis.map((i, n) => `<div class="paleta-item ${n === sel ? "sel" : ""}" data-n="${n}" role="option">
      <span class="ic">${IC[i.icone] || ""}</span><span class="t">${esc(i.titulo)}</span><span class="s">${esc(i.sub)}</span></div>`).join("")
      : `<div class="paleta-vazio">Nada encontrado</div>`;
    lista.querySelector(".sel")?.scrollIntoView({ block: "nearest" });
  };
  const fechar = () => caixa.remove();
  const executar = (n) => { const i = vis[n]; fechar(); if (i) i.f(); };

  input.addEventListener("input", () => { sel = 0; desenhar(); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); sel = Math.min(sel + 1, vis.length - 1); desenhar(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); sel = Math.max(sel - 1, 0); desenhar(); }
    else if (e.key === "Enter") { e.preventDefault(); executar(sel); }
    else if (e.key === "Escape") { e.preventDefault(); fechar(); }
  });
  lista.addEventListener("mousemove", (e) => {
    const el = e.target.closest(".paleta-item");
    if (el && +el.dataset.n !== sel) { sel = +el.dataset.n; lista.querySelectorAll(".paleta-item").forEach((x, n) => x.classList.toggle("sel", n === sel)); }
  });
  lista.addEventListener("click", (e) => { const el = e.target.closest(".paleta-item"); if (el) executar(+el.dataset.n); });
  caixa.querySelector(".paleta-fundo").addEventListener("click", fechar);
  desenhar();
  input.focus();
  if (!projetosCache) {
    projetosCache = await api.projetos();
    if (caixa.isConnected) { itens = itensPaleta(); desenhar(); }
  }
}
