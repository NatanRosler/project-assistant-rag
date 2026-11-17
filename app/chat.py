from experimentos.agente import avancar, decidir, nova_conversa
import streamlit as st
import sys
from pathlib import Path

# O Streamlit roda a partir da pasta app/; isto deixa a raiz do projeto visível
# para o "from experimentos.agente import ..." funcionar (o mesmo papel do -m).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


st.set_page_config(page_title="Assistente de Projetos", layout="wide")
st.title("Assistente de Projetos")

# ---------- Memória da página ----------
# O Streamlit roda este arquivo INTEIRO de novo a cada clique.
# O st.session_state é a "gaveta" que sobrevive entre uma rodada e outra.
if "mensagens" not in st.session_state:
    st.session_state.mensagens = nova_conversa()  # o que a IA vê
    st.session_state.historico = []               # o que aparece na tela
    # pedido esperando Confirmar/Cancelar
    st.session_state.pendente = None


def mostrar_passos(passos):
    """Mostra as ferramentas usadas numa área recolhível."""
    if passos:
        with st.expander(f"{len(passos)} passos"):
            for p in passos:
                st.code(f"{p['nome']}({p['args']})", language=None)


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


# ---------- 1. A conversa até aqui ----------
for h in st.session_state.historico:
    with st.chat_message(h["papel"]):
        mostrar_passos(h.get("passos"))
        st.markdown(h["texto"])                      # o texto da mensagem

# ---------- 2. Pedido de confirmação ----------
pend = st.session_state.pendente
if pend:
    with st.chat_message("assistant"):
        mostrar_passos(pend["passos"])
        c = pend["chamada"]
        st.warning(
            f"Posso executar **{c['nome']}**? Nada é gravado sem a sua confirmação.")
        st.json(c["args"])
        col1, col2 = st.columns(2)
        if col1.button("Confirmar", type="primary", use_container_width=True):
            with st.spinner("Gravando..."):
                tratar(decidir(st.session_state.mensagens,
                       pend["pendentes"], True), pend["passos"])
            st.rerun()
        if col2.button("Cancelar", use_container_width=True):
            with st.spinner("Avisando a IA..."):
                tratar(decidir(st.session_state.mensagens,
                       pend["pendentes"], False), pend["passos"])
            st.rerun()

# ---------- 3. Caixa de mensagem ----------
pergunta = st.chat_input("Pergunte sobre o projeto, peça um cálculo ou lance horas...",
                         disabled=pend is not None)
if pergunta:
    st.session_state.historico.append(
        {"papel": "user", "texto": pergunta})            # para a tela
    st.session_state.mensagens.append(
        {"role": "user", "content": pergunta})           # para a IA
    with st.chat_message("user"):
        st.markdown(pergunta)
    with st.spinner("Pensando..."):
        tratar(avancar(st.session_state.mensagens))       # roda o agente
    st.rerun()
