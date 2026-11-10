"use strict";
// O que cada botão faz (data-acao) e as configurações.

// --- ações -------------------------------------------------------------

const ACOES = {
  aba: (d) => trocarAba(d.aba),
  abrir: async (d) => { const r = await api.abrir(d.tipo, d.alvo); if (r && !r.ok) avisar(r.msg, true); },
  logs: (d) => abrirLogs(d.tipo, d.alvo, d.nome),
  "log-fechar": () => { $("#gaveta").hidden = true; logAtual = null; fecharLogLado(); },
  "log-copiar": async () => {
    const r = await api.copiar($("#log").innerText);
    avisar(r.ok ? "Log copiado." : r.msg, !r.ok);
  },
  copiar: async (d) => { const r = await api.copiar(d.texto); avisar(r.ok ? "Copiado." : r.msg, !r.ok); },
  celular: (d) => abrirCelular(d.porta, d.unidade),
  auto: async (d) => resultado(await api.auto(d.id, !!d.ligar)),
  "criar-grupo": async (d) => {
    const r = await api.criar_grupo(d.projeto);
    resultado(r);
    if (r.ok) setTimeout(() => renderProjetos(true), 800);
  },

  "jan-fechar": () => api.esconder(),
  "jan-minimizar": () => api.minimizar(),
  "jan-maximizar": () => api.maximizar(),

  "abrir-projeto": (d) => { projetoAberto = d.projeto; renderProjetos(); },
  "fechar-projeto": () => { projetoAberto = null; renderProjetos(); },

  reiniciar: async (d, b) => resultado(await comCarregando(b, () => api.reiniciar(+d.pid, d.ger || null)), ["reiniciar", d.pid]),
  "reiniciar-ger": async (d, b) => resultado(await comCarregando(b, () => api.reiniciar_gerenciado(d.id))),
  esquecer: async (d) => resultado(await api.esquecer(d.id)),
  encerrar: async (d, b) => {
    const extra = d.ferramenta ? " Se a sessão que usa essa ferramenta ainda estiver aberta, ela pode parar de funcionar." : "";
    if (!(await confirmar(`Encerrar ${d.nome}?`, `O processo ${esc(d.pid)} e os filhos dele serão encerrados.${extra}`, "Encerrar"))) return;
    resultado(await comCarregando(b, () => api.encerrar(+d.pid)), ["matar", d.pid]);
  },
  "encerrar-porta": async (d, b) => {
    if (!(await confirmar(`Encerrar ${d.nome}?`, `Ele está usando a porta ${esc(d.porta)}.`, "Encerrar"))) return;
    resultado(await comCarregando(b, () => api.encerrar_porta(+d.porta)), ["porta", d.porta]);
  },
  "parar-projeto": async (d, b) => {
    if (!(await confirmar(`Parar ${d.nome}?`, "Todos os processos e containers desse projeto serão parados.", "Parar tudo"))) return;
    resultado(await comCarregando(b, () => api.parar_projeto(d.nome)), ["parar", d.nome]);
  },
  "reiniciar-projeto": async (d, b) => resultado(await comCarregando(b, () => api.reiniciar_projeto(d.nome)), ["reiniciar", d.nome]),
  container: async (d, b) => resultado(await comCarregando(b, () => api.container(d.op, d.id))),

  iniciar: async (d, b) => {
    let r = await comCarregando(b, () => api.iniciar(d.projeto, d.chave, false));
    if (r && r.conflito) {
      const c = r.conflito;
      const ok = await confirmar("Porta em uso", `A porta ${c.porta} já está sendo usada por ${esc(c.dono)}${c.projeto ? ` (${esc(c.projeto)})` : ""}. Encerrar e iniciar mesmo assim?`, "Encerrar e iniciar");
      if (!ok) return;
      const e = await api.encerrar(c.pid);
      if (!e.ok) return resultado(e, ["matar", String(c.pid)]);
      r = await comCarregando(b, () => api.iniciar(d.projeto, d.chave, true));
    }
    resultado(r);
    if (r && r.ok && r.extra && r.extra.id) setTimeout(() => abrirLogs("processo", r.extra.id, r.msg.replace(/^Iniciado: /, "")), 400);
    if (r && r.ok) atualizarProjetosDepois();
  },
  subir: async (d, b) => resultado(await comCarregando(b, () => api.subir(d.projeto))),
  "iniciar-custom": async (d, b) => {
    const campo = document.querySelector(`[data-custom="${CSS.escape(d.projeto)}"]`);
    const sub = document.querySelector(`[data-custom-pasta="${CSS.escape(d.projeto)}"]`)?.value || "";
    const cmd = campo.value.trim();
    if (!cmd) { campo.focus(); return; }
    const r = await comCarregando(b, () => api.iniciar_personalizado(d.projeto, cmd, sub));
    resultado(r);
    if (r && r.ok) {
      campo.value = "";
      setTimeout(() => abrirLogs("processo", r.extra.id, sub ? `${sub}: ${cmd}` : cmd), 400);
      atualizarProjetosDepois();
    }
  },
  retomar: async (d, b) => resultado(await comCarregando(b, () => api.retomar(d.id || null))),
  "descartar-sessao": async (d) => resultado(await api.descartar_sessao(d.id)),
  "salvar-sessao": async () => resultado(await api.salvar_sessao()),
  sessoes: () => abrirSessoes(),
  "buscar-logs": (d) => d.projeto && abrirBuscaLogs(d.projeto),
  servico: async (d, b) => {
    const r = await comCarregando(b, () => api.servico(d.projeto, d.servico, d.op));
    resultado(r);
    setTimeout(() => carregarExtras(d.projeto, true), 1200);
  },
  "exportar-config": async () => { const r = await api.exportar_config(); if (r.msg) resultado(r); },
  "importar-config": async () => {
    const r = await api.importar_config();
    if (!r.msg) return;
    resultado(r);
    if (r.ok) { CFG = await api.config(); projetosCache = null; if (aba === "projetos") renderProjetos(true); }
  },
  periodo: (d) => { periodoHoje = d.periodo; renderHoje(); },
  tunel: (d) => abrirTunel(d.porta),
  "editar-porta": async (d) => {
    const r = await modal(`<div class="folha"><h3>Porta fixa</h3>
      <p>Esse comando sempre vai subir nessa porta. Deixe vazio para o Argos escolher sozinho.</p>
      <div class="form"><div class="grupo"><label class="item"><span class="rot">Porta</span>
        <input class="campo" id="pf-porta" type="number" min="1" max="65535" value="${esc(d.porta)}" data-foco></label></div></div>
      <div class="rodape"><button class="bt" data-resp="nao">Cancelar</button><button class="bt azul" id="pf-ok" data-padrao>Salvar</button></div></div>`,
      (m, fechar) => { m.querySelector("#pf-ok").onclick = () => fechar({ porta: m.querySelector("#pf-porta").value }); });
    if (!r) return;
    resultado(await api.definir_porta(d.projeto, d.chave, r.porta ? +r.porta : null));
    renderProjetos(true);
  },
  git: async (d, b) => {
    const r = await comCarregando(b, () => api.git(d.projeto, d.op));
    resultado(r);
    if (r.ok) { delete extrasCache[d.projeto]; renderProjetos(true); }
  },
  branches: (d) => abrirBranches(d.projeto),
  "editar-env": async (d) => {
    const r = await api.ler_env(d.caminho);
    if (!r.ok) return avisar(r.msg, true);
    const nome = d.caminho.split("\\").pop();
    const resp = await modal(`<div class="folha env"><h3>${esc(nome)}</h3>
      <p>${esc(d.caminho)}</p>
      <textarea class="campo mono" id="env-texto" spellcheck="false" data-foco>${esc(r.texto)}</textarea>
      <div class="rodape"><button class="bt" data-resp="nao">Cancelar</button><button class="bt azul" id="env-ok">Salvar</button></div></div>`,
      (m, fechar) => { m.querySelector("#env-ok").onclick = () => fechar({ texto: m.querySelector("#env-texto").value }); });
    if (!resp) return;
    resultado(await api.salvar_env(d.caminho, resp.texto));
    delete extrasCache[d.projeto];
    renderProjetos(true);
  },
  "completar-env": async (d) => {
    resultado(await api.completar_env(d.pasta));
    delete extrasCache[d.projeto];
    renderProjetos(true);
  },
  testar: async (d, b) => resultado(await comCarregando(b, () => api.testar(d.projeto, d.chave || null))),
  "log-teste": (d) => abrirLogs("arquivo", d.caminho, "Testes"),
  "procurar-atualizacao": async () => resultado(await api.atualizar()),
  "conectar-claude": async (d, b) => resultado(await comCarregando(b, () => api.instalar_mcp())),
  fixar: async (d) => { resultado(await api.fixar(d.projeto, d.chave || null)); renderProjetos(true); },
  "esquecer-recente": async (d) => { resultado(await api.esquecer_recente(d.projeto, d.chave)); renderProjetos(true); },
  "ocultar-comando": async (d) => { resultado(await api.ocultar_comando(d.projeto, d.chave)); renderProjetos(true); },
  "restaurar-comandos": async (d) => { resultado(await api.restaurar_comandos(d.projeto, d.chave || "")); renderProjetos(true); },
  "recarregar-projetos": () => { depsCache = {}; renderProjetos(true); },
  deps: async (d) => {
    depsCache[d.pasta] = null;
    atualizarDeps(d.pasta);
    depsCache[d.pasta] = await api.dependencias(d.pasta);
    atualizarDeps(d.pasta);
  },
  "apagar-dep": async (d, b) => {
    const p = d.caminho.split("\\").slice(-2, -1)[0];
    if (!(await confirmar(`Apagar ${d.nome}?`, `A pasta ${esc(p)}\\${esc(d.nome)} será apagada. Dá para recriar depois com npm install ou uv sync.`, "Apagar"))) return;
    resultado(await comCarregando(b, () => api.apagar_dependencia(d.caminho)));
    const pasta = d.caminho.slice(0, d.caminho.lastIndexOf("\\"));
    delete depsCache[pasta];
    ACOES.deps({ pasta });
  },

  "docker-ligar": async () => { avisar("Ligando o Docker Desktop… pode levar um minuto."); resultado(await api.docker_ligar()); },
  "docker-desligar": async () => {
    if (!(await confirmar("Desligar o Docker Desktop?", "Todos os containers param e a memória da VM é liberada.", "Desligar"))) { renderDocker(); return; }
    resultado(await api.docker_desligar());
  },
  "docker-disco": async () => { discoCache = null; renderDocker(); discoCache = await api.docker_disco(); renderDocker(); },
  "docker-limpar": async () => {
    const r = await modal(`<div class="folha"><h3>Limpar o Docker</h3>
      <p>Remove containers parados, imagens que nenhum container usa, redes sem uso e o cache de build. Imagens removidas são baixadas de novo quando precisar.</p>
      <div class="form"><div class="grupo"><label class="item"><span class="rot">Apagar também volumes sem uso<small>Dados de bancos de containers removidos são perdidos.</small></span>
        <span class="chave"><input type="checkbox" id="lim-vol"><span></span></span></label></div></div>
      <div class="rodape"><button class="bt" data-resp="nao">Cancelar</button><button class="bt vermelho" id="lim-ok" data-padrao>Limpar</button></div></div>`,
      (m, fechar) => { m.querySelector("#lim-ok").onclick = () => fechar({ vol: m.querySelector("#lim-vol").checked }); });
    if (!r) return;
    avisar("Limpando… pode demorar.");
    resultado(await api.docker_limpar(r.vol));
    ACOES["docker-disco"]();
  },

  "modo-jogo": () => abrirModoJogo(),
  config: () => abrirConfig(),
  paleta: () => abrirPaleta(),
};

// O comando usado vira o principal: recarrega a lista em segundo plano
function atualizarProjetosDepois() {
  setTimeout(async () => {
    projetosCache = await api.projetos();
    if (aba === "projetos") renderProjetos();
  }, 1200);
}

function atualizarDeps(pasta) {
  const el = document.querySelector(`[data-deps="${CSS.escape(pasta)}"]`);
  if (el) el.innerHTML = renderDeps(pasta);
}

async function abrirModoJogo() {
  if (!E) return;
  const r = E.resumo;
  const resp = await modal(`<div class="folha"><h3>Modo jogo</h3>
    <p>Para tudo de desenvolvimento para liberar memória. As ferramentas do Claude não são tocadas.</p>
    <div class="chips"><span class="chip"><b>${r.processos}</b> processos</span><span class="chip"><b>${r.containers}</b> containers</span>
      ${E.docker.vmmem_mb ? `<span class="chip">WSL <b>${ram(E.docker.vmmem_mb)}</b></span>` : ""}</div>
    <div class="form"><div class="grupo">
      <label class="item"><span class="rot">Lembrar o que está rodando<small>Depois, "Retomar" sobe tudo de novo com um clique.</small></span><span class="chave"><input type="checkbox" id="mj-lembrar" checked><span></span></span></label>
      <label class="item"><span class="rot">Desligar o Docker Desktop</span><span class="chave"><input type="checkbox" id="mj-docker" checked><span></span></span></label>
      <label class="item"><span class="rot">Desligar o WSL inteiro<small>Fecha qualquer Linux aberto no WSL.</small></span><span class="chave"><input type="checkbox" id="mj-wsl"><span></span></span></label>
    </div></div>
    <div class="rodape"><button class="bt" data-resp="nao">Cancelar</button><button class="bt vermelho" id="mj-ok" data-padrao>Parar tudo</button></div></div>`,
    (m, fechar) => { m.querySelector("#mj-ok").onclick = () => fechar({ docker: m.querySelector("#mj-docker").checked, wsl: m.querySelector("#mj-wsl").checked, lembrar: m.querySelector("#mj-lembrar").checked }); });
  if (!resp) return;
  avisar("Parando tudo…");
  resultado(await api.modo_jogo(resp.docker, resp.wsl, resp.lembrar));
}
window.abrirModoJogo = abrirModoJogo;

async function abrirConfig() {
  const c = await api.config();
  const resp = await modal(`<div class="folha"><h3>Configurações</h3><p>Dados e logs ficam em ${esc(c.pasta_dados)}.</p>
    <div class="form">
      <div class="grupo"><div class="bloco-campo"><label>Pastas de projetos <small>uma por linha; cada subpasta vira um projeto</small></label>
        <textarea class="campo mono" id="cf-pastas" rows="2">${esc((c.pastas_projetos || []).join("\n"))}</textarea></div></div>
      <div class="grupo" style="margin-top:12px">
        <label class="item"><span class="rot">Iniciar com o Windows</span><span class="chave"><input type="checkbox" id="cf-init" ${c.inicializacao ? "checked" : ""}><span></span></span></label>
        <label class="item"><span class="rot">Avisar sobre processos órfãos</span><span class="chave"><input type="checkbox" id="cf-orfaos" ${c.alerta_orfaos ? "checked" : ""}><span></span></span></label>
        <label class="item"><span class="rot">Avisar quando algo rodar por mais de<small>horas · 0 desliga</small></span><input class="campo" id="cf-horas" type="number" min="0" step="0.5" value="${esc(c.alerta_horas)}"></label>
        <label class="item"><span class="rot">Atualizar a cada<small>segundos</small></span><input class="campo" id="cf-int" type="number" min="1" max="60" value="${esc(c.intervalo)}"></label>
        <label class="item"><span class="rot">Atalho para abrir o painel<small>vale depois de reiniciar o app</small></span><input class="campo" id="cf-atalho" value="${esc(c.atalho)}"></label>
      </div>
      <div class="grupo" style="margin-top:12px">
        <label class="item"><span class="rot">Portas fixas<small>cada comando sempre na mesma porta</small></span><span class="chave"><input type="checkbox" id="cf-portas" ${c.portas_fixas ? "checked" : ""}><span></span></span></label>
        <label class="item"><span class="rot">Endereços com nome<small>projeto.localhost · vale depois de reiniciar o app</small></span><span class="chave"><input type="checkbox" id="cf-proxy" ${c.proxy ? "checked" : ""}><span></span></span></label>
        <label class="item"><span class="rot">Avisar servidor sem uso por<small>horas · 0 desliga</small></span><input class="campo" id="cf-ocioso" type="number" min="0" step="0.5" value="${esc(c.ocioso_horas)}"></label>
        <label class="item"><span class="rot">Buscar novidades do Git a cada<small>minutos · 0 desliga</small></span><input class="campo" id="cf-git" type="number" min="0" value="${esc(c.git_fetch_minutos)}"></label>
        <label class="item"><span class="rot">Avisar quando um processo passar de<small>MB de memória · 0 desliga</small></span><input class="campo" id="cf-ram" type="number" min="0" step="100" value="${esc(c.limite_ram_mb)}"></label>
      </div>
      <div class="grupo" style="margin-top:12px">
        <div class="item"><span class="rot">Argos ${esc(c.versao)}<small>versões novas: Releases do GitHub e pasta de atualização</small></span>
          <button class="bt" data-acao="procurar-atualizacao">Atualizar</button></div>
        <label class="item"><span class="rot">Procurar atualizações no GitHub<small>uma consulta a cada 6 horas</small></span><span class="chave"><input type="checkbox" id="cf-gh" ${c.procurar_atualizacao ? "checked" : ""}><span></span></span></label>
        <div class="item"><span class="rot">Ferramenta do Claude (MCP)<small>deixa o Claude Code ver e controlar o Argos</small></span>
          <button class="bt" data-acao="conectar-claude">Conectar</button></div>
        <div class="item"><span class="rot">Levar para outra máquina<small>opções, portas fixas e perfis · sem variáveis de ambiente</small></span>
          <span style="display:flex;gap:6px"><button class="bt" data-acao="importar-config">Importar</button><button class="bt" data-acao="exportar-config">Exportar</button></span></div>
      </div>
    </div>
    <div class="rodape"><button class="bt texto perigo" id="cf-sair" style="margin-right:auto">Sair do Argos</button>
      <button class="bt" data-resp="nao">Cancelar</button><button class="bt azul" id="cf-ok" data-padrao>Salvar</button></div></div>`,
    (m, fechar) => {
      m.querySelector("#cf-sair").onclick = () => { fechar(null); api.sair(); };
      m.querySelector("#cf-ok").onclick = () => fechar({
        pastas_projetos: m.querySelector("#cf-pastas").value.split("\n").map((s) => s.trim()).filter(Boolean),
        intervalo: Math.max(1, +m.querySelector("#cf-int").value || 3),
        alerta_horas: Math.max(0, +m.querySelector("#cf-horas").value || 0),
        atalho: m.querySelector("#cf-atalho").value.trim(),
        alerta_orfaos: m.querySelector("#cf-orfaos").checked,
        inicializacao: m.querySelector("#cf-init").checked,
        portas_fixas: m.querySelector("#cf-portas").checked,
        proxy: m.querySelector("#cf-proxy").checked,
        ocioso_horas: Math.max(0, +m.querySelector("#cf-ocioso").value || 0),
        git_fetch_minutos: Math.max(0, Math.round(+m.querySelector("#cf-git").value || 0)),
        limite_ram_mb: Math.max(0, Math.round(+m.querySelector("#cf-ram").value || 0)),
        procurar_atualizacao: m.querySelector("#cf-gh").checked,
      });
    });
  if (!resp) return;
  const r = await api.salvar_config(resp);
  // Atalho e endereços com nome só valem depois de reiniciar o app: oferece na hora
  if (r.ok && (resp.atalho !== c.atalho || resp.proxy !== c.proxy)) {
    avisar("Configurações salvas. O atalho e os endereços com nome valem depois de reiniciar o Argos.", false,
      { texto: "Reiniciar agora", acao: () => api.reiniciar_app() });
  } else resultado(r);
  CFG = await api.config();
  projetosCache = null;
  if (aba === "projetos") renderProjetos(true);
}

function trocarAba(nova) {
  aba = nova;
  document.querySelectorAll("#menu button").forEach((b) => b.classList.toggle("ativo", b.dataset.aba === nova));
  document.querySelectorAll("[data-painel]").forEach((s) => (s.hidden = s.dataset.painel !== nova));
  $("#conteudo").scrollTop = 0;
  if (E) renderBarra();
  if (nova === "projetos") renderProjetos();
  else if (nova === "hoje") renderHoje();
  else if (E) render();
}
