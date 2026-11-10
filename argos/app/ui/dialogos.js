"use strict";
// Modais, avisos, seletor de branch, sessões, QR code e túnel.

// --- alertas, folhas e avisos -------------------------------------------

function modal(html, aoAbrir) {
  return new Promise((resolve) => {
    const m = $("#modal"), f = $("#fundo");
    m.innerHTML = html;
    m.hidden = f.hidden = false;
    const fechar = (v) => { m.hidden = f.hidden = true; m.innerHTML = ""; document.removeEventListener("keydown", tecla); resolve(v); };
    const tecla = (e) => {
      if (e.key === "Escape") fechar(null);
      if (e.key === "Enter" && e.target.tagName !== "TEXTAREA") m.querySelector("[data-padrao]")?.click();
    };
    document.addEventListener("keydown", tecla);
    f.onclick = () => fechar(null);
    m.querySelectorAll("[data-resp]").forEach((b) => b.addEventListener("click", () => fechar(b.dataset.resp === "nao" ? null : b.dataset.resp)));
    aoAbrir && aoAbrir(m, fechar);
    (m.querySelector("[data-foco]") || m.querySelector("[data-padrao]"))?.focus();
  });
}

// Seletor de branch: locais, as que só existem no servidor e criar uma nova
async function abrirBranches(nome) {
  let b = await api.git_branches(nome);
  let filtro = "", sel = 0, ocupado = false;
  await modal(`<div class="folha branches">
    <h3>Branch de ${esc(nome)}</h3>
    <input class="campo" placeholder="Buscar ou digitar o nome de uma branch nova" data-foco spellcheck="false">
    <div class="lista-branches"></div>
    <div class="rodape">
      <button class="bt texto" id="br-fetch" title="git fetch: traz as branches novas do servidor" style="margin-right:auto">Buscar no servidor</button>
      <button class="bt" data-resp="nao">Fechar</button>
    </div></div>`, (m, fechar) => {
    const input = m.querySelector("input"), lista = m.querySelector(".lista-branches");
    const itens = () => {
      const f = filtro.toLowerCase();
      const casa = (n) => !f || n.toLowerCase().includes(f);
      const saida = b.locais.filter(casa).map((n) => ({ grupo: "Neste computador", nome: n, op: "checkout", arg: n, atual: n === b.atual }));
      saida.push(...(b.remotas || []).filter((r) => casa(r.nome))
        .map((r) => ({ grupo: "Só no servidor", nome: r.nome, op: "checkout_remota", arg: r.ref, extra: r.remoto })));
      const exato = b.locais.includes(filtro.trim()) || (b.remotas || []).some((r) => r.nome === filtro.trim());
      if (filtro.trim() && !exato) saida.push({ grupo: "Nova", nome: filtro.trim(), op: "criar", arg: filtro.trim(), nova: true });
      return saida;
    };
    const desenhar = () => {
      const vis = itens();
      sel = Math.min(sel, Math.max(vis.length - 1, 0));
      let grupo = "";
      lista.innerHTML = vis.length ? vis.map((it, n) => {
        const cab = it.grupo !== grupo ? `<div class="branch-grupo">${esc((grupo = it.grupo))}</div>` : "";
        return `${cab}<button class="branch-item ${n === sel ? "sel" : ""} ${it.atual ? "atual" : ""}" data-n="${n}" ${it.atual ? "disabled" : ""}>
          ${it.nova ? IC.mais : IC.git}<span class="branch-nome">${it.nova ? `Criar <b>${esc(it.nome)}</b> a partir de ${esc(b.atual)}` : esc(it.nome)}</span>
          ${it.atual ? `<span class="etq verde">atual</span>` : it.extra ? `<span class="etq">baixar de ${esc(it.extra)}</span>` : ""}
        </button>`;
      }).join("") : `<div class="linha-sub" style="padding:10px 4px">Nenhuma branch com esse nome.</div>`;
      lista.querySelector(".sel")?.scrollIntoView({ block: "nearest" });
    };
    const escolher = async (it) => {
      if (!it || it.atual || ocupado) return;
      ocupado = true;
      lista.innerHTML = `<div class="extra-carregando"><span class="girando"></span></div>`;
      const r = await api.git(nome, it.op, it.arg);
      fechar(null);
      // Projeto rodando: o código da outra branch só vale depois de reiniciar (Vite e afins recarregam sozinhos)
      if (r.ok && r.rodando) {
        avisar(r.msg, false, { texto: "Reiniciar", acao: async () => resultado(await api.reiniciar_projeto(nome)) });
      } else resultado(r);
      delete extrasCache[nome];
      renderProjetos(true);
    };
    // A seleção começa no primeiro item que não é a branch atual
    const primeiro = () => Math.max(itens().findIndex((it) => !it.atual), 0);
    input.addEventListener("input", () => { filtro = input.value; sel = primeiro(); desenhar(); });
    input.addEventListener("keydown", (e) => {
      const vis = itens();
      // As setas pulam a branch atual, que não dá para escolher
      const andar = (passo) => { let n = sel + passo; while (vis[n]?.atual) n += passo; if (vis[n]) sel = n; desenhar(); };
      if (e.key === "ArrowDown") { e.preventDefault(); andar(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); andar(-1); }
      else if (e.key === "Enter") { e.preventDefault(); escolher(vis[sel]); }
    });
    lista.addEventListener("click", (e) => { const el = e.target.closest(".branch-item"); if (el) escolher(itens()[+el.dataset.n]); });
    m.querySelector("#br-fetch").addEventListener("click", async (e) => {
      const bt = e.currentTarget;
      const r = await comCarregando(bt, () => api.git(nome, "fetch"));
      if (!r.ok) return avisar(r.msg, true);
      b = await api.git_branches(nome);
      desenhar();
    });
    sel = primeiro();
    desenhar();
  });
}

// Sessões salvas e perfis com nome ("trabalho", "jogo"): retomar, apagar e salvar o que roda agora
async function abrirSessoes() {
  let lista = await api.sessoes();
  await modal(`<div class="folha sessoes">
    <h3>Sessões e perfis</h3>
    <p>Um perfil guarda um conjunto de processos e containers para subir de novo com um clique.</p>
    <div class="lin"><input class="campo" id="ss-nome" placeholder="Nome do perfil (ex: trabalho)" data-foco spellcheck="false">
      <button class="bt azul" id="ss-salvar">Salvar o que está rodando</button></div>
    <button class="bt texto" id="ss-montar" style="align-self:flex-start">Ou montar um perfil escolhendo projetos…</button>
    <div class="montar-perfil" hidden></div>
    <div class="lista-sessoes"></div>
    <div class="rodape"><button class="bt" data-resp="nao">Fechar</button></div></div>`, (m, fechar) => {
    const caixa = m.querySelector(".lista-sessoes");
    // Perfil sem precisar subir nada antes: escolhe os comandos dos projetos
    const montar = m.querySelector(".montar-perfil");
    m.querySelector("#ss-montar").onclick = async () => {
      if (!projetosCache) projetosCache = await api.projetos();
      montar.hidden = !montar.hidden;
      m.querySelector("#ss-salvar").textContent = montar.hidden ? "Salvar o que está rodando" : "Salvar perfil";
      montar.innerHTML = projetosCache.filter((p) => p.comandos.length).map((p) => `<div class="montar-projeto"><b>${esc(p.nome)}</b>
        ${p.comandos.filter((c) => c.tipo !== "godot").map((c) => `<label><input type="checkbox" data-projeto="${esc(p.nome)}" data-chave="${esc(c.chave)}"
          data-nome="${esc((c.sub ? c.sub + ": " : "") + c.rotulo)}"><span class="mono">${c.sub ? esc(c.sub) + "/ " : ""}${esc(c.rotulo)}</span></label>`).join("")}</div>`).join("")
        || `<div class="linha-sub">Nenhum projeto com comandos.</div>`;
    };
    const desenhar = () => {
      caixa.innerHTML = lista.length ? lista.map((s) => {
        const oq = [s.processos && plural(s.processos, "processo", "processos"), s.containers && plural(s.containers, "container", "containers")].filter(Boolean).join(" e ");
        const estado = s.falhas.length ? `<span class="etq vermelho" title="${esc(s.falhas.join("\n"))}">${plural(s.falhas.length, "falha", "falhas")}</span>`
          : s.nome ? "" : s.retomada ? `<span class="etq">retomada</span>` : `<span class="etq azul">pendente</span>`;
        return `<div class="sessao-item">
          <div class="linha-corpo"><div class="linha-titulo">${esc(s.nome || (s.motivo === "modo jogo" ? "Modo jogo" : "Sessão"))} ${estado}</div>
            <div class="linha-sub">${hora(s.quando)}<span class="p">·</span>${oq}${s.projetos.length ? `<span class="p">·</span>${esc(s.projetos.join(", "))}` : ""}</div></div>
          <button class="bt texto perigo" data-apagar="${esc(s.id)}">Apagar</button>
          <button class="bt" data-retomar="${esc(s.id)}">Retomar</button></div>`;
      }).join("") : `<div class="linha-sub" style="padding:14px 2px">Nenhuma sessão salva. O modo jogo salva uma automaticamente.</div>`;
    };
    m.querySelector("#ss-salvar").onclick = async () => {
      const nome = m.querySelector("#ss-nome").value.trim();
      const escolhidos = [...montar.querySelectorAll("input:checked")].map((i) => ({ projeto: i.dataset.projeto, chave: i.dataset.chave, nome: i.dataset.nome }));
      const r = montar.hidden ? await api.salvar_sessao(nome) : await api.criar_perfil(nome, escolhidos);
      resultado(r);
      if (r.ok) {
        m.querySelector("#ss-nome").value = "";
        montar.hidden = true;
        m.querySelector("#ss-salvar").textContent = "Salvar o que está rodando";
        lista = await api.sessoes();
        desenhar();
      }
    };
    caixa.addEventListener("click", async (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      if (b.dataset.retomar) { fechar(null); resultado(await api.retomar(b.dataset.retomar)); }
      if (b.dataset.apagar) { await api.apagar_sessao(b.dataset.apagar); lista = await api.sessoes(); desenhar(); }
    });
    desenhar();
  });
}

// Procura um texto nos logs de todos os serviços de um projeto
async function abrirBuscaLogs(projeto, inicial = "") {
  await modal(`<div class="folha busca-logs">
    <h3>Buscar nos logs de ${esc(projeto)}</h3>
    <input class="campo" placeholder="Texto para procurar em todos os serviços (ex: error, timeout, /api/pedidos)" data-foco spellcheck="false" value="${esc(inicial)}">
    <div class="resultado-logs"><div class="linha-sub" style="padding:10px 2px">Digite pelo menos 2 letras.</div></div>
    <div class="rodape"><button class="bt" data-resp="nao">Fechar</button></div></div>`, (m, fechar) => {
    const input = m.querySelector("input"), caixa = m.querySelector(".resultado-logs");
    let pedido = 0, espera = null;
    const buscar = async () => {
      const texto = input.value.trim();
      if (texto.length < 2) { caixa.innerHTML = `<div class="linha-sub" style="padding:10px 2px">Digite pelo menos 2 letras.</div>`; return; }
      const n = ++pedido;
      const achados = await api.buscar_logs(projeto, texto);
      if (n !== pedido) return; // chegou uma busca mais nova
      const re = new RegExp(esc(texto).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
      caixa.innerHTML = achados.length ? achados.map((s) => `<div class="servico-achado">
        <button class="bt texto" data-abrir="${esc(s.id)}" data-tipo="${esc(s.tipo)}" data-nome="${esc(s.nome)}" title="Abrir este log com a busca">${esc(s.nome)}
          <span class="linha-sub">${plural(s.total, "linha", "linhas")}${s.vivo ? "" : " · parado"}</span></button>
        <pre>${s.linhas.map((l) => esc(l).replace(re, (x) => `<mark>${x}</mark>`)).join("\n")}</pre></div>`).join("")
        : `<div class="linha-sub" style="padding:10px 2px">Nada encontrado. Só processos iniciados pelo Argos e containers têm log.</div>`;
    };
    input.addEventListener("input", () => { clearTimeout(espera); espera = setTimeout(buscar, 250); });
    caixa.addEventListener("click", (e) => {
      const b = e.target.closest("[data-abrir]");
      if (!b) return;
      const texto = input.value.trim();
      fechar(null);
      abrirLogs(b.dataset.tipo, b.dataset.abrir, b.dataset.nome);
      $("#log-busca").value = texto;
      setTimeout(() => renderLog(true), 1500);
    });
    if (inicial) buscar();
  });
}

// Alerta compacto no estilo do macOS: ícone, título, texto, botões empilhados
function confirmar(titulo, texto, botao = "Confirmar", perigo = true) {
  return modal(`<div class="dialogo">
    <div class="icone-app">&gt;_</div>
    <h3>${esc(titulo)}</h3><p>${texto}</p>
    <div class="botoes">
      <button class="bt ${perigo ? "vermelho" : "azul"}" data-resp="sim" data-padrao>${esc(botao)}</button>
      <button class="bt" data-resp="nao">Cancelar</button>
    </div></div>`);
}

function avisar(msg, erro = false, botao = null, opcoes = {}) {
  const d = document.createElement("div");
  d.className = "aviso";
  const cor = opcoes.cor || (erro ? "var(--vermelho)" : "var(--verde)");
  const titulo = opcoes.titulo ? `<b>${esc(opcoes.titulo)}</b>` : "";
  d.innerHTML = `<span class="ponto" style="background:${cor}"></span><span class="aviso-texto">${titulo}${esc(msg)}</span>`;
  if (botao) {
    const b = document.createElement("button");
    b.className = "bt azul";
    b.textContent = botao.texto;
    b.onclick = () => { d.remove(); botao.acao(); };
    d.appendChild(b);
  }
  const lista = $("#avisos");
  lista.appendChild(d);
  while (lista.children.length > 4) lista.firstChild.remove();
  setTimeout(() => d.remove(), opcoes.duracao || (botao ? 12000 : erro ? 7000 : 3200));
}

// Avisos que vêm do monitor (caiu, pronto, subindo…)
function avisarEvento(ev) {
  const cores = { erro: "var(--vermelho)", aviso: "var(--laranja)", info: "var(--verde)" };
  let botao = null;
  const a = ev.acao;
  if (a) botao = { texto: a.rotulo, acao: () => executarAcaoEvento(a) };
  else if (ev.url) botao = { texto: "Abrir", acao: () => api.abrir("url", ev.url) };
  else if (ev.id) botao = { texto: "Ver logs", acao: () => abrirLogs("processo", ev.id, ev.titulo.replace(/ (caiu|pronto).*$/, "")) };
  const progresso = ev.tipo === "progresso";
  avisar(ev.msg, ev.nivel === "erro", progresso ? null : botao, {
    titulo: progresso ? `${ev.titulo} · ` : `${ev.titulo}  `,
    cor: progresso ? "var(--azul)" : cores[ev.nivel],
    duracao: progresso ? 2500 : ev.nivel === "erro" ? 15000 : undefined,
  });
}

// Botões dos avisos do monitor (ex: "Parar" num servidor ocioso, "Pull" no Git)
async function executarAcaoEvento(a) {
  if (a.tipo === "encerrar") resultado(await api.encerrar(a.pid), ["matar", String(a.pid)]);
  else if (a.tipo === "reiniciar") resultado(await api.reiniciar(a.pid, a.ger || null), ["reiniciar", String(a.pid)]);
  else if (a.tipo === "git") resultado(await api.git(a.projeto, a.op));
  else if (a.tipo === "atualizar") resultado(await api.atualizar());
  else if (a.tipo === "log-arquivo") abrirLogs("arquivo", a.caminho, "Testes");
}

// Endereço com nome (http://projeto.localhost) para um host, se o proxy estiver ligado
function enderecoNome(host) {
  const px = E && E.proxy;
  if (!px || !px.porta || !(host in (px.rotas || {}))) return null;
  return `http://${host}${px.porta === 80 ? "" : ":" + px.porta}`;
}
const dns = (s) => s.toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-|-$/g, "") || "projeto";

async function abrirTunel(porta) {
  const carregando = modal(`<div class="folha celular"><h3>Link público</h3><p>Abrindo o túnel… isso leva alguns segundos.</p>
    <div class="qr"><span class="girando" style="width:28px;height:28px"></span></div></div>`);
  const r = await api.tunel(+porta);
  $("#fundo").click();
  await carregando;
  if (r.falta_cloudflared) {
    const ok = await confirmar("Instalar o cloudflared?", "O link público usa o cloudflared, gratuito e oficial da Cloudflare. Ele será instalado pelo winget (aceitando a licença do pacote).", "Instalar", false);
    if (!ok) return;
    avisar("Instalando o cloudflared… pode levar um minuto.");
    const inst = await api.instalar_cloudflared();
    if (!inst.ok) return avisar(inst.msg, true);
    return abrirTunel(porta);
  }
  if (!r.ok) return avisar(r.msg, true, r.id ? { texto: "Ver logs", acao: () => abrirLogs("processo", r.id, `túnel :${porta}`) } : null);
  await modal(`<div class="folha celular">
    <h3>Link público</h3>
    <p>Qualquer pessoa com o link acessa a porta ${porta} enquanto o túnel estiver aberto.</p>
    <div class="qr">${r.svg || ""}</div>
    <div class="lin" style="justify-content:center"><code class="url">${esc(r.url)}</code>
      <button class="ib" data-acao="copiar" data-texto="${esc(r.url)}" title="Copiar">${IC.copiar}</button></div>
    <div class="rodape"><button class="bt vermelho" id="tn-fechar">Fechar túnel</button><button class="bt azul" data-resp="nao" data-padrao>OK</button></div>
  </div>`, (m, fechar) => {
    m.querySelector("#tn-fechar").onclick = async () => { fechar(null); resultado(await api.encerrar(r.pid)); };
  });
}

async function abrirCelular(porta, idUnidade) {
  const r = await api.celular(+porta);
  if (!r || !r.ok) return avisar(r ? r.msg : "Falhou.", true);
  // Mais de uma porta (ex: site + API): botões para trocar
  const u = idUnidade && E ? E.unidades.find((x) => x.id === idUnidade) : null;
  const opcoes = u && u.portas.length > 1 ? `<div class="segmentos">${u.portas.map((p) => {
    const t = u.portas_tipo?.[p];
    return `<button class="${p === +porta ? "ativo" : ""}" data-trocar="${p}">${p}${t ? ` · ${t === "site" ? "site" : "API"}` : ""}</button>`;
  }).join("")}</div>` : "";
  const tipo = u?.portas_tipo?.[+porta];
  const aviso = tipo === "api" ? `<p class="nota">Essa porta é a API. Para ver o site no celular, escolha a porta marcada como <b>site</b>.</p>` : "";
  await modal(`<div class="folha celular">
    <h3>Abrir no celular</h3>
    <p>Aponte a câmera do celular, conectado na mesma rede Wi-Fi.</p>
    ${opcoes}
    <div class="qr">${r.svg}</div>
    ${aviso}
    <div class="lin" style="justify-content:center"><code class="url">${esc(r.url)}</code>
      <button class="ib" data-acao="copiar" data-texto="${esc(r.url)}" title="Copiar endereço">${IC.copiar}</button></div>
    ${r.so_local ? `<div class="erro-grupo" style="margin-top:12px">Esse servidor só aceita conexões deste PC, então o celular não vai abrir. Para liberar: ${esc(r.dica).replace(/(ex: |use |com )(.+)$/, "$1<code>$2</code>")}.</div>` : ""}
    <p class="nota">Se não abrir, permita o programa no Firewall do Windows (redes privadas).</p>
    <div class="rodape"><button class="bt azul" data-resp="nao" data-padrao>OK</button></div>
  </div>`, (m, fechar) => {
    m.querySelectorAll("[data-trocar]").forEach((b) => b.addEventListener("click", () => {
      fechar(null);
      abrirCelular(+b.dataset.trocar, idUnidade);
    }));
  });
}

// Mostra o resultado de uma ação; se faltar permissão, oferece rodar como admin
function resultado(r, argsAdmin) {
  if (!r) return;
  if (r.msg) avisar(r.msg, !r.ok, r.admin && argsAdmin ? {
    texto: "Tentar como admin", acao: async () => resultado(await api.admin(argsAdmin)),
  } : null);
  setTimeout(ciclo, 300);
}

async function comCarregando(botao, fn) {
  const html = botao?.innerHTML;
  if (botao) { botao.disabled = true; botao.innerHTML = `<span class="girando"></span>`; }
  try { return await fn(); }
  finally { if (botao && botao.isConnected) { botao.disabled = false; botao.innerHTML = html; } }
}
