import sys
from datetime import date
from pathlib import Path

# O Streamlit roda a partir da pasta app/; isto deixa a raiz do projeto visível
# para o "from experimentos.agente import ..." funcionar (o mesmo papel do -m).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st
from experimentos.agente import (avancar, banco, decidir, nova_conversa,
                                 salvar_documento_projeto, ver_calculos, ver_projeto)

RAIZ = Path(__file__).resolve().parents[1]

st.set_page_config(page_title="Assistente de Projetos", layout="wide")
st.title("Assistente de Projetos")

# ---------- Memória da página ----------
# O Streamlit roda este arquivo INTEIRO de novo a cada clique.
# O st.session_state é a "gaveta" que sobrevive entre uma rodada e outra.
if "mensagens" not in st.session_state:
    st.session_state.mensagens = nova_conversa()  # o que a IA vê
    st.session_state.historico = []               # o que aparece na tela
    st.session_state.pendente = None              # pedido esperando Confirmar/Cancelar


def mostrar_passos(passos):
    """Mostra as ferramentas usadas numa área recolhível."""
    if passos:
        rotulo = "1 passo" if len(passos) == 1 else f"{len(passos)} passos"
        with st.expander(rotulo):
            for p in passos:
                st.code(f"{p['nome']}({p['args']})", language=None)


def descrever(c):
    """Transforma o pedido da IA numa frase que qualquer pessoa entende."""
    a = c["args"]
    if c["nome"] == "lancar_horas":
        data = date.fromisoformat(a["data"]).strftime("%d/%m/%Y")
        return f"Lançar **{a['duracao_min'] / 60:g} h** de {a['etapa']} no **{a['projeto']}** em {data}"
    if c["nome"] == "salvar_calculo":
        return f"Salvar o cálculo de {a['tipo']} no **{a['projeto']}** ({len(a['entradas'])} entradas, com fontes)"
    if c["nome"] == "salvar_documento_projeto":
        return f"Salvar o arquivo **{Path(a['caminho']).name}** no **{a['projeto']}**"
    return f"Executar {c['nome']}"


def tratar(r, passos_antes=None):
    """Guarda o que o motor devolveu: uma resposta, ou um pedido de confirmação."""
    if passos_antes:
        r["passos"] = passos_antes + r["passos"]
    if r["tipo"] == "resposta":
        st.session_state.historico.append(
            {"papel": "assistant", "texto": r["texto"], "passos": r["passos"]})
        st.session_state.pendente = None
    else:
        st.session_state.pendente = r


# ---------- 0. Lateral ----------
projetos = banco.table("projetos").select("id, codigo, descricao").order("codigo").execute().data
nomes = {p["codigo"]: f"{p['codigo']} · {p['descricao']}" for p in projetos}

with st.sidebar:
    st.subheader("Assistente de Projetos")
    st.caption("Vetor Engenharia (fictícia)")
    if st.button("Nova conversa", icon=":material/add_comment:", use_container_width=True):
        st.session_state.mensagens = nova_conversa()
        st.session_state.historico = []
        st.session_state.pendente = None
        st.rerun()

    # Escolha do projeto: o key="projeto" guarda a escolha no session_state sozinho
    codigo = st.radio("Projeto", list(nomes), format_func=nomes.get, key="projeto")
    projeto = next(p for p in projetos if p["codigo"] == codigo)

    st.divider()
    st.markdown("**Documentos do projeto**")
    arquivo = st.file_uploader("Enviar PDF para o projeto", type="pdf")
    if arquivo and st.button("Salvar no projeto", type="primary", use_container_width=True):
        # Clicar no botão já é a confirmação: a pessoa escolheu o arquivo e mandou salvar
        caminho = RAIZ / "doc" / "novos" / arquivo.name
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(arquivo.getvalue())
        with st.spinner("Lendo o PDF..."):
            r = salvar_documento_projeto(str(caminho), codigo)
        if "erro" in r:
            st.error(r["erro"])
        else:
            st.success(r["mensagem"])
    docs = banco.table("documentos").select("nome").eq("projeto_id", projeto["id"]).execute().data
    for d in docs:
        st.caption(f":material/description: {d['nome']}")
    if not docs:
        st.caption("Nenhum documento ainda.")

    st.divider()
    st.markdown("**Cálculos salvos**")
    calc = ver_calculos(codigo)
    for c in calc.get("calculos", []):
        quando = date.fromisoformat(c["criado_em"][:10]).strftime("%d/%m/%Y")
        st.caption(f"{c['tipo']} · **{str(c['resultado'].get('potencia_kw')).replace('.', ',')} kW** · {quando}")
    if not calc.get("calculos"):
        st.caption("Nenhum cálculo salvo ainda.")

# Resumo do projeto escolhido, no topo da conversa
info = ver_projeto(codigo)
entrega = date.fromisoformat(info["entrega"]).strftime("%d/%m/%Y")
st.caption(f"**{info['codigo']} · {info['descricao']}** · {info['cliente']} · "
           f"{info['horas_lancadas']:g} h de {info['horas_previstas']:g} h · entrega {entrega}")


# ---------- 1. A conversa até aqui ----------
for h in st.session_state.historico:
    with st.chat_message(h["papel"]):
        mostrar_passos(h.get("passos"))
        st.markdown(h["texto"])

# ---------- 2. Pedido de confirmação ----------
pend = st.session_state.pendente
if pend:
    with st.chat_message("assistant"):
        mostrar_passos(pend["passos"])
        c = pend["chamada"]
        st.warning(f"{descrever(c)}?  \nNada é gravado sem a sua confirmação.")
        with st.expander("Detalhes técnicos"):
            st.json(c["args"])
        col1, col2 = st.columns(2)
        if col1.button("Confirmar", type="primary", use_container_width=True):
            with st.spinner("Gravando..."):
                tratar(decidir(st.session_state.mensagens, pend["pendentes"], True), pend["passos"])
            st.rerun()
        if col2.button("Cancelar", use_container_width=True):
            with st.spinner("Avisando a IA..."):
                tratar(decidir(st.session_state.mensagens, pend["pendentes"], False), pend["passos"])
            st.rerun()

# ---------- 3. Caixa de mensagem ----------
pergunta = st.chat_input("Pergunte sobre o projeto, peça um cálculo ou lance horas...",
                         disabled=pend is not None)
if pergunta:
    st.session_state.historico.append({"papel": "user", "texto": pergunta})
    # A IA recebe a pergunta junto com o projeto escolhido na lateral (isso não aparece na tela)
    st.session_state.mensagens.append(
        {"role": "user", "content": f"[Projeto selecionado na tela: {codigo}]\n{pergunta}"})
    with st.chat_message("user"):
        st.markdown(pergunta)
    with st.spinner("Pensando..."):
        tratar(avancar(st.session_state.mensagens))
    st.rerun()