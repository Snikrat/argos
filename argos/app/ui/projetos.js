"use strict";
// Aba Projetos: cards, página do projeto, Git, .env e testes.

// --- projetos ------------------------------------------------------------

async function renderProjetos(recarregar = false) {
  const el = $("#p-projetos");
  if (!projetosCache || recarregar) {
    if (!projetosCache) el.innerHTML = vazio("projetos", "Lendo projetos…", "");
    projetosCache = await api.projetos();
    if (E) renderBarra();
  }
  const f = filtroProjetos.toLowerCase();
  const lista = projetosCache.filter((p) => !f || p.nome.toLowerCase().includes(f));
  if (!lista.length) {
    el.innerHTML = vazio("busca", "Nenhum projeto", f ? "Nada com esse nome." : "Configure as pastas de projetos nas configurações.");
    return;
  }
  assinaturaAtivos = assinatura();
  if (projetoAberto) {
    const p = projetosCache.find((x) => x.nome === projetoAberto);
    if (p) { el.innerHTML = paginaProjeto(p); el.scrollTop = 0; return; }
    projetoAberto = null;
  }
  // Os que estão rodando ficam em cima, separados, para ver na hora o que está aberto
  const rodando = lista.filter((p) => ativoDe(p.nome));
  const outros = lista.filter((p) => !ativoDe(p.nome));
  el.innerHTML = (rodando.length ? `<div class="titulo-secao">Rodando agora <span class="sec">${rodando.length}</span></div>
      <div class="cards">${rodando.map(cartaoProjeto).join("")}</div>` : "")
    + (outros.length ? `<div class="titulo-secao">${rodando.length ? "Parados" : "Todos"} <span class="sec">${outros.length}</span></div>
      <div class="cards">${outros.map(cartaoProjeto).join("")}</div>` : "");
}

// Projeto em execução agora (vem do estado), pelo nome
const ativoDe = (nome) => E?.ativos.find((a) => a.nome && a.nome.toLowerCase() === nome.toLowerCase());
const assinatura = () => (E ? E.ativos.map((a) => `${a.nome}:${a.portas.join(",")}`).join("|") + "#" + E.portas.map((x) => x.porta).join(",") : "");
let assinaturaAtivos = "";

// Quem está ocupando a porta de um comando, se não for o próprio projeto (visto antes de clicar em iniciar)
function conflitoDe(p, c) {
  if (!E || !c.porta) return null;
  const x = E.portas.find((y) => y.porta === c.porta);
  return x && (x.projeto || "").toLowerCase() !== p.nome.toLowerCase() ? x : null;
}

function etiquetasProjeto(p) {
  const partes = [];
  const presos = p.comandos.map((c) => [c, conflitoDe(p, c)]).filter(([, x]) => x);
  if (presos.length) {
    const [c, x] = presos[0];
    partes.push(`<span class="etq vermelho" title="${esc(presos.map(([c2, x2]) => `:${c2.porta} em uso por ${x2.dono}${x2.projeto ? ` (${x2.projeto})` : ""}`).join("\n"))}">porta ${c.porta} ocupada</span>`);
  }
  if (p.git) {
    partes.push(`<button class="git" ${attr({ acao: "branches", projeto: p.nome })} title="Trocar de branch">${IC.git}${esc(p.git.branch)}</button>`);
    if (p.git.alteracoes) partes.push(`<span class="etq laranja" title="Arquivos alterados e não commitados">${plural(p.git.alteracoes, "alteração", "alterações")}</span>`);
    if (p.git.a_enviar) partes.push(`<span class="etq azul" title="Commits que ainda não foram para o GitHub (git push)">${p.git.a_enviar} a enviar</span>`);
    if (p.git.a_receber) partes.push(`<span class="etq" title="Commits no servidor que você ainda não puxou (git pull)">${p.git.a_receber} a receber</span>`);
  }
  if (p.erro_grupo) partes.push(`<span class="etq vermelho" title="${esc(p.erro_grupo)}">argos.toml com erro</span>`);
  if (p.env_faltando) partes.push(`<span class="etq laranja" title="Variáveis do .env.example que não estão no .env">.env: ${plural(p.env_faltando, "faltando", "faltando")}</span>`);
  if (p.testes) partes.push(p.testes.ok
    ? `<span class="etq verde" title="Últimos testes: ${esc(hora(p.testes.quando))}">✓ testes</span>`
    : `<span class="etq vermelho" title="Últimos testes: ${esc(hora(p.testes.quando))}">✗ ${plural(p.testes.falhas, "teste falhou", "testes falharam")}</span>`);
  return partes;
}

function portasDoAtivo(a) {
  const tipos = Object.assign({}, ...a.unidades.map((u) => u.portas_tipo || {}));
  // Site primeiro: é o que normalmente se abre no navegador
  return [...a.portas].sort((x, y) => (tipos[y] === "site") - (tipos[x] === "site")).map((p) => chipPorta(p, tipos[p] || ""));
}

function cartaoProjeto(p) {
  const a = ativoDe(p.nome);
  const principal = p.comandos[0];
  const rodape = a
    ? `${portasDoAtivo(a).slice(0, 3).join("")}<span class="direita">
        ${ib("reiniciar", { acao: "reiniciar-projeto", nome: a.nome }, "Reiniciar tudo")}
        ${ib("parar", { acao: "parar-projeto", nome: a.nome }, "Parar tudo", "perigo")}</span>`
    : principal ? `<button class="bt" ${attr({ acao: "iniciar", projeto: p.nome, chave: principal.chave })}
        title="${esc((principal.chave === p.fixo ? "Comando fixado · " : "") + (principal.detalhe || principal.cmd))}">
        <span style="color:var(--verde)">${IC.play}</span>${principal.sub ? `<span class="sub-cmd">${esc(principal.sub)}</span>` : ""}${esc(principal.rotulo)}</button>` : `<span class="linha-sub">sem comandos</span>`;
  return `<div class="cartao ${a ? "rodando" : ""}" role="button" tabindex="0" ${attr({ acao: "abrir-projeto", projeto: p.nome })}>
    <div class="cartao-topo">
      <span class="ponto ${a ? "" : "cinza"}"></span>
      <span class="cartao-nome">${esc(p.nome)}</span>
      ${a ? `<span class="cartao-desde">desde ${hora(a.inicio)}</span>` : ""}
    </div>
    <div class="cartao-tipos">${esc(p.tipos.join(" · ") || "sem comandos detectados")}</div>
    <div class="cartao-etqs">${etiquetasProjeto(p).join("")}</div>
    <div class="cartao-rodape">${rodape}</div>
  </div>`;
}

// Página de um projeto (substitui a lista de cards)
function paginaProjeto(p) {
  return `<div class="pag">
    <button class="voltar" data-acao="fechar-projeto">${IC.chevron}Projetos</button>
    <div class="pag-cab">
      <div class="linha-corpo">
        <div class="pag-nome">${esc(p.nome)}</div>
        <div class="linha-sub">${[esc(p.tipos.join(" · ") || "sem comandos detectados"), ...etiquetasProjeto(p)].join('<span class="p">·</span>')}</div>
      </div>
      <div class="linha-fim">${botoesPasta(p.pasta)}</div>
    </div>
    <div data-status-projeto>${statusProjeto(p)}</div>
    ${detalheProjeto(p)}
  </div>`;
}

function statusProjeto(p) {
  const a = ativoDe(p.nome);
  if (!a) return "";
  const nomeUrl = enderecoNome(`${dns(a.nome)}.localhost`);
  const nomeApi = enderecoNome(`api.${dns(a.nome)}.localhost`);
  const links = [nomeUrl && `<button class="link-nome" ${attr({ acao: "abrir", tipo: "url", alvo: nomeUrl })} title="Abrir o site pelo nome">${esc(nomeUrl.replace("http://", ""))}</button>`,
    nomeApi && `<button class="link-nome api" ${attr({ acao: "abrir", tipo: "url", alvo: nomeApi })} title="Abrir a API pelo nome">${esc(nomeApi.replace("http://", ""))}</button>`].filter(Boolean).join("");
  return `<div class="pag-rodando">
    <span class="ponto"></span><b>Rodando</b><span class="linha-sub">desde ${hora(a.inicio)} · ${plural(a.unidades.length + a.containers.length, "item", "itens")}</span>
    ${portasDoAtivo(a).join("")}${links}
    <span class="direita">
      <button class="bt texto" ${attr({ acao: "buscar-logs", projeto: p.nome })}>Buscar nos logs</button>
      <button class="bt texto" ${attr({ acao: "aba", aba: "rodando" })}>Ver processos</button>
      ${ib("reiniciar", { acao: "reiniciar-projeto", nome: a.nome }, "Reiniciar tudo")}
      ${ib("parar", { acao: "parar-projeto", nome: a.nome }, "Parar tudo", "perigo")}
    </span>
  </div>`;
}

// A cada ciclo: só redesenha os projetos quando algo começou/parou ou mudou de porta
function atualizarProjetosRodando() {
  if (!projetosCache || assinatura() === assinaturaAtivos) return;
  if (projetoAberto) {
    assinaturaAtivos = assinatura();
    const p = projetosCache.find((x) => x.nome === projetoAberto);
    const el = document.querySelector("[data-status-projeto]");
    if (p && el) el.innerHTML = statusProjeto(p);
    if (p && p.grupo) carregarExtras(p.nome, true); // estado de cada serviço
  } else renderProjetos();
}

function detalheProjeto(p) {
  const grupo = p.erro_grupo
    ? `<div class="erro-grupo">argos.toml: ${esc(p.erro_grupo)}</div>`
    : p.grupo ? "" : `<div class="lin dica-grupo"><span>Tem mais de uma parte (banco, backend, frontend)? Um <b>argos.toml</b> sobe tudo em ordem com um clique.</span>
        <button class="bt texto" ${attr({ acao: "criar-grupo", projeto: p.nome })}>Criar argos.toml</button></div>`;
  // Comandos agrupados pela pasta onde rodam (raiz, backend/, frontend/...)
  const pastas = [...new Set(p.comandos.map((c) => c.sub || ""))];
  const linhaCmd = (c) => {
    const fixo = c.chave === p.fixo;
    return `<div class="cmd-linha" role="button" tabindex="0" ${attr({ acao: "iniciar", projeto: p.nome, chave: c.chave })} title="${esc(c.detalhe || c.cmd)}">
      <span class="play">${IC.play}</span><span class="nome">${esc(c.rotulo)}</span>
      ${c.recente ? `<span class="etq">recente</span>` : ""}
      ${conflitoDe(p, c) ? `<span class="etq vermelho" title="Iniciar vai perguntar se quer encerrar quem está na porta">porta em uso por ${esc(conflitoDe(p, c).dono)}</span>` : ""}
      ${c.porta || c.ferramenta ? `<button class="porta-prev ${c.porta_fixa ? "fixa" : ""}" ${attr({ acao: "editar-porta", projeto: p.nome, chave: c.chave, porta: c.porta || "" })}
        title="${c.porta_fixa ? "Porta fixa deste comando (clique para mudar)" : c.ferramenta ? "Porta prevista: vira fixa ao iniciar (clique para escolher)" : "Porta prevista"}">:${c.porta || "?"}</button>` : ""}
      <span class="cmd-acoes">
        ${c.recente ? ib("fechar", { acao: "esquecer-recente", projeto: p.nome, chave: c.chave }, "Remover dos recentes")
          : ib("fechar", { acao: "ocultar-comando", projeto: p.nome, chave: c.chave }, "Apagar da lista\n(dá para restaurar depois)")}
        ${ib(fixo ? "fixado" : "fixar", { acao: "fixar", projeto: p.nome, chave: fixo ? "" : c.chave },
            fixo ? "Fixado como principal (clique para soltar)" : "Fixar como comando principal", fixo ? "ligado fixo" : "")}
      </span>
    </div>`;
  };
  const opcoesPasta = pastas.filter(Boolean).map((s) => `<option value="${esc(s)}">${esc(s)}/</option>`).join("");
  return `<div class="detalhe">
    <div class="extra"><div class="extra-titulo">${IC.play}Comandos</div>
    ${p.comandos.length ? pastas.map((s) => `<div class="cmd-grupo">
      ${pastas.length > 1 ? `<div class="cmd-pasta">${s ? `${IC.pasta}${esc(s)}/` : `${IC.pasta}raiz do projeto`}</div>` : ""}
      ${p.comandos.filter((c) => (c.sub || "") === s).map(linhaCmd).join("")}
    </div>`).join("") : ""}
    <div class="lin">
      ${opcoesPasta ? `<select class="campo seletor" data-custom-pasta="${esc(p.nome)}" title="Pasta onde o comando roda">
        <option value="">raiz</option>${opcoesPasta}</select>` : ""}
      <input class="campo mono" placeholder="Outro comando…" data-custom="${esc(p.nome)}">
      <button class="bt" ${attr({ acao: "iniciar-custom", projeto: p.nome })}>Rodar</button>
    </div>
    ${(p.ocultos || []).length ? `<div class="lin cmd-ocultos">
      <span class="linha-sub">${plural(p.ocultos.length, "apagado", "apagados")}:</span>
      ${p.ocultos.map((o) => `<button class="cmd-oculto" ${attr({ acao: "restaurar-comandos", projeto: p.nome, chave: o.chave })}
        title="Restaurar este comando">${IC.reiniciar}${o.sub ? esc(o.sub) + "/ " : ""}${esc(o.rotulo)}</button>`).join("")}
      ${p.ocultos.length > 1 ? `<button class="bt texto" ${attr({ acao: "restaurar-comandos", projeto: p.nome })}>Restaurar todos</button>` : ""}
    </div>` : ""}
    ${grupo}
    </div>
    <div data-extras="${esc(p.nome)}">${renderExtras(p)}</div>
    <div class="extra"><div class="lin">
      <div class="deps" data-deps="${esc(p.pasta)}" style="flex:1">${renderDeps(p.pasta)}</div>
    </div></div>
  </div>`;
}

// Git, .env e testes: carregados quando o projeto é aberto
const extrasCache = {};
const extrasCarregando = new Set();

async function carregarExtras(nome, forcar = false) {
  if ((extrasCache[nome] && !forcar) || extrasCarregando.has(nome)) return;
  extrasCarregando.add(nome);
  try {
    const temGrupo = !!((projetosCache || []).find((x) => x.nome === nome) || {}).grupo;
    const [branches, env, testes, servicos] = await Promise.all([api.git_branches(nome), api.ambiente(nome), api.testes(nome),
      temGrupo ? api.servicos(nome) : []]);
    extrasCache[nome] = { branches, env, testes, servicos };
  } finally {
    extrasCarregando.delete(nome);
  }
  const el = document.querySelector(`[data-extras="${CSS.escape(nome)}"]`);
  const p = (projetosCache || []).find((x) => x.nome === nome);
  if (el && p) el.innerHTML = renderExtras(p);
}

function renderExtras(p) {
  const x = extrasCache[p.nome];
  if (!x) { carregarExtras(p.nome); return `<div class="extra-carregando"><span class="girando"></span></div>`; }
  const blocos = [];

  if ((x.servicos || []).length) {
    blocos.push(`<div class="extra"><div class="extra-titulo">${IC.rodando}Serviços do argos.toml
      <button class="bt texto" style="margin-left:auto" ${attr({ acao: "iniciar", projeto: p.nome, chave: (p.comandos.find((c) => c.tipo === "grupo") || {}).chave || "" })}>Subir tudo</button></div>
      ${x.servicos.map((s) => `<div class="lin servico-linha">
        <span class="ponto ${s.rodando ? "" : "cinza"}"></span>
        <span class="mono">${esc(s.nome)}</span>
        <span class="linha-sub" style="flex:1">${s.tipo === "docker" ? "container" : "processo"}${s.depois.length ? ` · depois de ${esc(s.depois.join(", "))}` : ""}</span>
        ${s.rodando
          ? ib("reiniciar", { acao: "servico", projeto: p.nome, servico: s.nome, op: "reiniciar" }, "Reiniciar só este serviço")
            + ib("parar", { acao: "servico", projeto: p.nome, servico: s.nome, op: "parar" }, "Parar só este serviço", "perigo")
          : ib("play", { acao: "servico", projeto: p.nome, servico: s.nome, op: "iniciar" }, s.depois.length ? `Iniciar (sobe antes: ${s.depois.join(", ")})` : "Iniciar só este serviço")}
      </div>`).join("")}</div>`);
  }

  if (p.git && x.branches.locais.length) {
    const g = p.git;
    const outras = x.branches.locais.length - 1 + (x.branches.remotas || []).length;
    blocos.push(`<div class="extra"><div class="extra-titulo">${IC.git}Git</div><div class="lin">
      <button class="campo seletor botao-branch" ${attr({ acao: "branches", projeto: p.nome })}
        title="Trocar de branch${outras ? ` (${outras} outra${outras > 1 ? "s" : ""})` : ""}">${IC.git}<span>${esc(x.branches.atual || "(sem branch)")}</span>${IC.chevron}</button>
      <span class="linha-sub" style="flex:1">${g.alteracoes ? plural(g.alteracoes, "alteração", "alterações") + " não commitada(s)" : "sem alterações"}</span>
      <button class="bt texto" ${attr({ acao: "git", projeto: p.nome, op: "fetch" })} title="Buscar novidades do servidor">Fetch</button>
      <button class="bt ${g.a_receber ? "azul" : ""}" ${attr({ acao: "git", projeto: p.nome, op: "pull" })}>Pull${g.a_receber ? ` (${g.a_receber})` : ""}</button>
      <button class="bt ${g.a_enviar ? "azul" : ""}" ${attr({ acao: "git", projeto: p.nome, op: "push" })}>Push${g.a_enviar ? ` (${g.a_enviar})` : ""}</button>
    </div></div>`);
  }

  if (x.env.length) {
    blocos.push(`<div class="extra"><div class="extra-titulo">${IC.chave}Variáveis de ambiente</div>${x.env.map((a) => `
      <div class="env-pasta">
        ${x.env.length > 1 || a.sub ? `<span class="env-onde">${esc(a.sub ? a.sub + "/" : "raiz")}</span>` : ""}
        ${a.arquivos.map((f) => `<button class="bt texto" ${attr({ acao: "editar-env", caminho: f.caminho, projeto: p.nome })} title="${f.chaves} variável(is)">${esc(f.nome)}</button>`).join("")}
        ${a.faltando.length ? `<span class="etq laranja" title="${esc(a.faltando.join(", "))}">${a.sem_env ? "sem .env" : `faltam ${a.faltando.length}: ${esc(a.faltando.slice(0, 3).join(", "))}${a.faltando.length > 3 ? "…" : ""}`}</span>
          <button class="bt texto" ${attr({ acao: "completar-env", pasta: a.pasta, projeto: p.nome })}>${a.sem_env ? "Criar .env do exemplo" : "Completar"}</button>` : ""}
        ${a.arquivos.length > 1 || a.usar ? `<span class="env-usar"><span class="linha-sub">ao iniciar:</span>
          <select class="campo seletor" data-env-usar="${esc(p.nome)}" data-sub="${esc(a.sub)}" title="Arquivo cujas variáveis vão no ambiente ao iniciar comandos desta pasta">
            <option value="">padrão do projeto</option>
            ${a.arquivos.map((f) => `<option ${f.nome === a.usar ? "selected" : ""}>${esc(f.nome)}</option>`).join("")}</select></span>` : ""}
      </div>`).join("")}</div>`);
  }

  const lista = (x.testes && x.testes.lista) || [];
  if (lista.length) {
    const res = x.testes.resultados || {};
    blocos.push(`<div class="extra"><div class="extra-titulo">${IC.teste}Testes
      <button class="bt texto" style="margin-left:auto" ${attr({ acao: "testar", projeto: p.nome })}>Rodar todos</button></div>
      ${lista.map((t) => { const r = res[t.chave]; return `<div class="lin teste-linha">
        <span class="ponto ${r ? (r.ok ? "" : "vermelho") : "cinza"}"></span>
        <span class="mono">${t.sub ? esc(t.sub) + "/ " : ""}${esc(t.cmd)}</span>
        <span class="linha-sub" style="flex:1">${r ? `${esc(r.resumo)} · ${esc(hora(r.quando))}` : "nunca rodou"}</span>
        ${r ? `<button class="bt texto" ${attr({ acao: "log-teste", caminho: r.log })}>Log</button>` : ""}
        <button class="ib" ${attr({ acao: "testar", projeto: p.nome, chave: t.chave })} title="Rodar">${IC.play}</button>
      </div>`; }).join("")}</div>`);
  }
  return blocos.join("");
}

function renderDeps(pasta) {
  const d = depsCache[pasta];
  if (d === undefined) return `<button class="bt texto" ${attr({ acao: "deps", pasta })}>Ver espaço das dependências</button>`;
  if (d === null) return `<span class="girando"></span>`;
  if (!d.length) return "Sem node_modules ou .venv";
  return d.map((x) => `<div class="deps-item"><span class="mono">${esc(x.nome)}</span> ${bytes(x.bytes)}
    <button class="bt texto perigo" ${attr({ acao: "apagar-dep", caminho: x.caminho, nome: x.nome })}>Apagar</button></div>`).join("");
}
