from experimentos.agente import avancar, decidir, nova_conversa
import streamlit as st
import sys
from datetime import date
from pathlib import Path

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
        rotulo = "1 passo" if len(
            passos) == 1 else f"{len(passos)} passos"
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
        # ex.: "Salvar o cálculo de potencia_helicoidal no PRJ070000 (6 entradas, com fontes)"
        return f"Salvar o cálculo de **{a['tipo']}** no **{a['projeto']}**"
    if c["nome"] == "salvar_documento_projeto":
        # ex.: "Salvar o arquivo ficha-material-PRJ070000.pdf no PRJ070000"
        return f"Salvar o arquivo {Path(a['caminho']).name}** no {a['projeto']}**"
    return f"Executar {c['nome']}"   # qualquer ferramenta nova cai aqui


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
        st.warning(f"{descrever(c)}?  \nNada é gravado sem a sua confirmação.")
        with st.expander("Detalhes técnicos"):
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
