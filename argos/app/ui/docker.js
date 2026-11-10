"use strict";
// Abas Docker e Ferramentas.

// --- docker --------------------------------------------------------------

function renderDocker() {
  const el = $("#p-docker");
  const dk = E.docker;
  if (!dk.instalado) { el.innerHTML = vazio("docker", "Docker não instalado", ""); return; }
  const nenhumRodando = !dk.containers.some((c) => c.estado === "running");
  const dica = dk.vmmem_mb != null
    ? `A VM do WSL está usando ${ram(dk.vmmem_mb)} de memória.${nenhumRodando && dk.vmmem_mb > 500 ? " Nenhum container rodando: desligar libera essa memória." : ""}`
    : "A VM do WSL não está rodando.";

  const containers = dk.containers.length ? `<div class="grupo">${dk.containers.map((c) => {
    const rodando = c.estado === "running";
    return `<div class="linha">
      <span class="ponto ${rodando ? "azul" : "cinza"}"></span>
      <div class="linha-corpo">
        <div class="linha-titulo">${esc(c.nome)}</div>
        <div class="linha-sub">${esc(c.imagem)}${c.projeto ? `<span class="p">·</span>${esc(c.projeto)}` : ""}<span class="p">·</span>${esc(c.status)}</div>
      </div>
      <div class="linha-fim">
        ${c.portas.map(([h]) => chipPorta(h)).join("")}
        <div class="acoes ocultas">
          ${ib("logs", { acao: "logs", tipo: "container", alvo: c.id, nome: c.nome }, "Logs")}
          ${rodando
            ? ib("reiniciar", { acao: "container", op: "reiniciar", id: c.id }, "Reiniciar") + ib("parar", { acao: "container", op: "parar", id: c.id }, "Parar", "perigo")
            : ib("play", { acao: "container", op: "iniciar", id: c.id }, "Iniciar")}
        </div>
      </div>
    </div>`;
  }).join("")}</div>` : `<div class="grupo"><div class="linha"><div class="linha-corpo linha-sub">${dk.ligado ? "Nenhum container." : "Ligue o Docker para ver os containers."}</div></div></div>`;

  let disco = "";
  if (dk.ligado) {
    const d = discoCache;
    disco = `<div class="titulo-secao">Espaço em disco
        <span class="sec">imagens, volumes e cache acumulam com o tempo</span>
        <div style="margin-left:auto" class="lin">
          <button class="bt texto" data-acao="docker-disco">${d ? "Atualizar" : "Analisar"}</button>
          <button class="bt texto perigo" data-acao="docker-limpar">Limpar…</button>
        </div></div>
      ${d === null ? `<div class="grupo"><div class="linha"><span class="girando"></span></div></div>` : d ? `<div class="grupo"><table class="tab">
        <thead><tr><th>Tipo</th><th class="num">Total</th><th class="num">Em uso</th><th class="num">Tamanho</th><th class="num">Recuperável</th></tr></thead><tbody>
        ${d.map((x) => `<tr><td>${esc(x.tipo)}</td><td class="num">${esc(x.total)}</td><td class="num">${esc(x.ativos)}</td><td class="num">${esc(x.tamanho)}</td><td class="num">${esc(x.recuperavel)}</td></tr>`).join("")}
      </tbody></table></div>` : ""}`;
  }

  el.innerHTML = `<div class="grupo"><div class="linha">
      <span class="ic" style="color:var(--azul);width:20px">${IC.docker}</span>
      <div class="linha-corpo"><div class="linha-titulo">Docker Desktop</div><div class="linha-sub">${esc(dica)}</div></div>
      <div class="linha-fim"><label class="chave" title="${dk.ligado ? "Desligar" : "Ligar"} o Docker Desktop">
        <input type="checkbox" data-acao="${dk.ligado ? "docker-desligar" : "docker-ligar"}" ${dk.ligado ? "checked" : ""}><span></span></label></div>
    </div></div>
    <div class="titulo-secao">Containers</div>${containers}${disco}`;
}

// --- ferramentas ---------------------------------------------------------

function renderFerramentas() {
  const el = $("#p-ferramentas");
  if (!E.ferramentas.length) {
    el.innerHTML = vazio("ferramentas", "Nenhuma ferramenta rodando", "Servidores MCP do Claude e afins aparecem aqui.");
    return;
  }
  el.innerHTML = `<p class="linha-sub" style="white-space:normal;margin:0 2px 4px;font-size:12px">Servidores MCP e ferramentas de apps como o Claude. Cada sessão aberta costuma ter a sua; as marcadas em laranja perderam o app que as abriu e só gastam memória.</p>`
    + E.ferramentas.map((f) => `<div class="bloco">
      <div class="titulo-secao">${esc(f.nome)} <span class="sec">${plural(f.instancias, "instância", "instâncias")} · ${ram(f.ram_mb)}</span>
        ${f.orfas ? `<span class="etq laranja">${plural(f.orfas, "órfã", "órfãs")}</span>` : ""}</div>
      <div class="grupo">${f.unidades.map((u) => `<div class="linha ${u.orfao ? "alerta" : ""}">
        <span class="ponto ${u.orfao ? "laranja" : "cinza"}"></span>
        <div class="linha-corpo">
          <div class="linha-titulo mono" title="${esc(u.cmd)}">${esc(u.nome)}</div>
          <div class="linha-sub">${u.orfao ? "sem dono" : `aberto por ${esc(u.origem)}`}<span class="p">·</span>desde ${esc(hora(u.inicio))}<span class="p">·</span>${ram(u.ram_mb)}<span class="p">·</span>PID ${u.pid}</div>
        </div>
        <div class="linha-fim">${u.portas.map(chipPorta).join("")}<div class="acoes ocultas">
          ${ib("parar", { acao: "encerrar", pid: u.pid, nome: u.nome, ferramenta: 1 }, "Encerrar", "perigo")}</div></div>
      </div>`).join("")}</div>
    </div>`).join("");
}
