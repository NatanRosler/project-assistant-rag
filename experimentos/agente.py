import json
import math
import os
from datetime import date, timedelta
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client
from pathlib import Path
from ingest.ingest import indexar_pdf

load_dotenv()
ia = OpenAI(base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"))
banco = create_client(os.getenv("SUPABASE_URL"),
                      os.getenv("SUPABASE_SERVICE_KEY"))
MODELO_CHAT = os.getenv("MODELO_CHAT")
LIMITE = 0.30
# ---------- 1. As ferramentas "de verdade" (aqui, de mentira) ----------
FERIADOS = {"2026-11-02", "2026-11-15", "2026-11-20", "2026-12-25"}


def salvar_documento_projeto(caminho, projeto):
    r = banco.table("projetos").select("*").eq("codigo", projeto).execute()
    if not r.data:
        return {"erro": f"Projeto {projeto} não encontrado."}
    p = r.data[0]
    arquivo = Path(caminho)
    if not arquivo.exists():
        return {"erro": f"Arquivo {caminho} não encontrado."}
    n = indexar_pdf(arquivo, p["id"])
    if n == 0:
        return {"erro": f"{arquivo.name} já estava salvo."}
    return {"ok": True, "mensagem": f"{arquivo.name} salvo no {projeto} ({n} trechos)."}


def ver_projeto(codigo):
    r = banco.table("projetos").select("*").eq("codigo", codigo).execute()
    if not r.data:
        return {"erro": f"Projeto {codigo} não encontrado."}
    p = r.data[0]
    l = banco.table("lancamentos").select(
        "duracao_min").eq("projeto_id", p["id"]).execute()
    minutos = sum(x["duracao_min"] for x in l.data)
    return {"codigo": p["codigo"], "descricao": p["descricao"], "cliente": p["cliente"],
            "concluido_pct": p["concluido_pct"], "horas_lancadas": round(minutos / 60, 1),
            "horas_previstas": p["horas_previstas"], "entrega": p["entrega"]}


def calcular_dias_uteis(data_inicio, dias):
    d = date.fromisoformat(data_inicio)
    contados = 0
    while contados < dias:
        if d.weekday() < 5 and d.isoformat() not in FERIADOS:
            contados += 1
        if contados < dias:
            d += timedelta(days=1)
    return {"data_final": d.isoformat()}


def dias_uteis_entre(data_inicio, data_fim):
    d = date.fromisoformat(data_inicio) + \
        timedelta(days=1)   # começa no dia seguinte
    fim = date.fromisoformat(data_fim)
    contados = 0
    while d <= fim:
        if d.weekday() < 5 and d.isoformat() not in FERIADOS:      # dia de semana e não é feriado
            contados += 1
        d += timedelta(days=1)                                  # próximo dia
    return {"dias_uteis": contados}


def lancar_horas(projeto, etapa, data, duracao_min):
    r = banco.table("projetos").select("*").eq("codigo", projeto).execute()
    if not r.data:
        return {"erro": f"Projeto {projeto} não encontrado."}
    p = r.data[0]
    banco.table("lancamentos").insert({"projeto_id": p["id"], "etapa": etapa,
                                       "data": data, "duracao_min": duracao_min}).execute()
    return {"ok": True, "mensagem": f"{duracao_min / 60:g} h lançados em {projeto}, {etapa}, {data}."}


def potencia_helicoidal(vazao_m3h, densidade_t_m3, comprimento_m, inclinacao_graus, c0, diametro_m):
    # vazão em t/h
    Q = vazao_m3h * densidade_t_m3
    # altura vencida
    H = comprimento_m * math.sin(math.radians(inclinacao_graus))
    p_mover = Q * c0 * comprimento_m / 367
    p_elevar = Q * H / 367
    p_vazio = diametro_m * comprimento_m / 20
    total = p_mover + p_elevar + p_vazio
    return {"vazao_t_h": round(Q, 2), "altura_m": round(H, 2),
            "p_mover_kw": round(p_mover, 3), "p_elevar_kw": round(p_elevar, 3),
            "p_vazio_kw": round(p_vazio, 3), "potencia_kw": round(total, 3)}


def buscar_documentos(pergunta):
    vetor = ia.embeddings.create(
        model="openai/text-embedding-3-small", input=pergunta).data[0].embedding
    r = banco.rpc("buscar_trechos", {
                  "vetor_pergunta": vetor, "quantidade": 5}).execute()
    trechos = [t for t in r.data if t["similaridade"] >= LIMITE]
    if not trechos:
        return {"resultado": "Nada encontrado nos documentos."}
    return {"trechos": [
        {"documento": t["documento"],
            "pagina": t["pagina"], "texto": t["texto"]}
        for t in trechos
    ]}


def salvar_calculo(projeto, tipo, entradas, fontes):
    r = banco.table("projetos").select("*").eq("codigo", projeto).execute()
    if not r.data:
        return {"erro": f"Projeto {projeto} não encontrado."}
    p = r.data[0]
    if tipo not in CALCULOS:
        return {"erro": f"Tipo de cálculo {tipo} desconhecido."}
    try:
        resultado = CALCULOS[tipo](**entradas)        # refaz a conta em Python
    except TypeError as e:
        return {"erro": f"Entradas inválidas para {tipo}: {e}"}
    banco.table("calculos").insert({"projeto_id": p["id"], "tipo": tipo,
                                    "entradas": entradas, "resultado": resultado, "fontes": fontes}).execute()
    return {"ok": True, "resultado": resultado}


def ver_calculos(projeto):
    r = banco.table("projetos").select("*").eq("codigo", projeto).execute()
    if not r.data:
        return {"erro": f"Projeto {projeto} não encontrado."}
    p = r.data[0]
    c = banco.table("calculos").select("tipo, entradas, resultado, fontes, criado_em") \
        .eq("projeto_id", p["id"]).order("criado_em", desc=True).execute()
    if not c.data:
        return {"resultado": f"Nenhum cálculo salvo no {projeto}."}
    return {"calculos": c.data}


CALCULOS = {"potencia_helicoidal": potencia_helicoidal}
FUNCOES = {"ver_projeto": ver_projeto,
           "calcular_dias_uteis": calcular_dias_uteis, "lancar_horas": lancar_horas,
           "buscar_documentos": buscar_documentos,
           "dias_uteis_entre": dias_uteis_entre,
           "salvar_documento_projeto": salvar_documento_projeto,
           "potencia_helicoidal": potencia_helicoidal,
           "salvar_calculo": salvar_calculo,
           "ver_calculos": ver_calculos}
ESCRITA = {"lancar_horas", "salvar_documento_projeto", "salvar_calculo"}

# ---------- 2. O catálogo: a descrição que a IA recebe ----------
FERRAMENTAS = [
    {"type": "function", "function": {
        "name": "ver_projeto",
        "description": "Dados de um projeto: andamento, horas lançadas e previstas, data de entrega.",
        "parameters": {"type": "object", "properties": {
            "codigo": {"type": "string", "description": "Código do projeto, ex.: PRJ060000"}},
            "required": ["codigo"]}}},
    {"type": "function", "function": {
        "name": "calcular_dias_uteis",
        "description": "Soma dias úteis a uma data, pulando fins de semana e feriados.",
        "parameters": {"type": "object", "properties": {
            "data_inicio": {"type": "string", "description": "AAAA-MM-DD"},
            "dias": {"type": "integer"}},
            "required": ["data_inicio", "dias"]}}},
    {"type": "function", "function": {
        "name": "lancar_horas",
        "description": "Lança horas trabalhadas num projeto. Chame direto quando o pedido estiver claro: "
        "o sistema mostra uma confirmação ao usuário antes de gravar. Não peça confirmação no texto.",
        "parameters": {"type": "object", "properties": {
            "projeto": {"type": "string"}, "etapa": {"type": "string"},
            "data": {"type": "string", "description": "AAAA-MM-DD"},
            "duracao_min": {"type": "integer", "description": "duração em minutos"}},
            "required": ["projeto", "etapa", "data", "duracao_min"]}}},
    {"type": "function", "function": {
        "name": "buscar_documentos",
        "description": "Busca nos documentos técnicos da empresa: manuais, procedimentos, "
        "checklists, propostas e normas internas. Use para perguntas técnicas e de procedimento. "
        "NÃO use para horas, andamento ou prazo de projeto (para isso existe ver_projeto).",
        "parameters": {"type": "object", "properties": {
            "pergunta": {"type": "string", "description": "Texto da busca, com as palavras-chave"}},
            "required": ["pergunta"]}}},
    {"type": "function", "function": {
        "name": "dias_uteis_entre",
        "description": "Conta quantos dias úteis existem entre duas datas, pulando fins de semana "
        "e feriados. Use para medir atraso ou folga em relação à data de entrega.",
        "parameters": {"type": "object", "properties": {
            "data_inicio": {"type": "string", "description": "AAAA-MM-DD (não entra na contagem)"},
            "data_fim": {"type": "string", "description": "AAAA-MM-DD (entra na contagem)"}},
            "required": ["data_inicio", "data_fim"]}}},
    {"type": "function", "function": {
        "name": "salvar_documento_projeto",
        "description": "Salva um arquivo PDF dentro de um projeto e o deixa disponível para busca. "
        "Chame direto quando o pedido estiver claro: o sistema mostra uma confirmação ao usuário.",
        "parameters": {"type": "object", "properties": {
            "caminho": {"type": "string", "description": "Caminho do arquivo PDF, ex.: doc/novos/ficha.pdf"},
            "projeto": {"type": "string", "description": "Código do projeto, ex.: PRJ070000"}},
            "required": ["caminho", "projeto"]}}},
    {"type": "function", "function": {
        "name": "potencia_helicoidal",
        "description": "Calcula a potência de um transportador helicoidal (rosca transportadora) "
        "pelo método DIN: mover + elevar + em vazio, em kW. Antes de calcular, busque os dados "
        "nos documentos do projeto (buscar_documentos): vazão, comprimento e inclinação costumam "
        "estar na proposta; densidade e coeficiente c0 na ficha do material. Se algum dado não "
        "estiver nos documentos nem na pergunta, peça ao usuário em vez de supor.",
        "parameters": {"type": "object", "properties": {
            "vazao_m3h": {"type": "number", "description": "Vazão volumétrica em m³/h"},
            "densidade_t_m3": {"type": "number", "description": "Densidade aparente do material em t/m³"},
            "comprimento_m": {"type": "number", "description": "Comprimento do transportador em metros"},
            "inclinacao_graus": {"type": "number", "description": "Inclinação em graus (0 se horizontal)"},
            "c0": {"type": "number", "description": "Coeficiente de resistência do material (ex.: 2,0 para farelos)"},
            "diametro_m": {"type": "number", "description": "Diâmetro da rosca em METROS (250 mm = 0.25)"}},
            "required": ["vazao_m3h", "densidade_t_m3", "comprimento_m",
                         "inclinacao_graus", "c0", "diametro_m"]}}},
    {"type": "function", "function": {
        "name": "salvar_calculo",
        "description": "Salva um cálculo dentro de um projeto. Use depois de calcular, passando as "
        "MESMAS entradas usadas no cálculo: o sistema refaz a conta antes de gravar. Chame direto "
        "quando o pedido estiver claro: o sistema mostra uma confirmação ao usuário.",
        "parameters": {"type": "object", "properties": {
            "projeto": {"type": "string", "description": "Código do projeto, ex.: PRJ070000"},
            "tipo": {"type": "string", "enum": ["potencia_helicoidal"],
                     "description": "Nome da ferramenta de cálculo usada"},
            "entradas": {"type": "object",
                         "description": "Os mesmos parâmetros passados para a ferramenta de cálculo"},
            "fontes": {"type": "object",
                       "description": "De onde veio cada entrada, ex.: "
                       "{\"vazao_m3h\": \"proposta-PRJ070000-transportador-helicoidal.pdf, p. 1\", "
                       "\"diametro_m\": \"informado pelo usuário\"}"}},
            "required": ["projeto", "tipo", "entradas", "fontes"]}}},
    {"type": "function", "function": {
        "name": "ver_calculos",
        "description": "Lista os cálculos já salvos num projeto, do mais novo para o mais antigo, "
        "com entradas, resultado e fontes. Use quando perguntarem por cálculos feitos antes.",
        "parameters": {"type": "object", "properties": {
            "projeto": {"type": "string", "description": "Código do projeto, ex.: PRJ070000"}},
            "required": ["projeto"]}}},
]

INSTRUCOES = f"""Você é o assistente do painel de projetos de um engenheiro mecânico que projeta
equipamentos industriais (esteiras, transportadores, içamento). Hoje é {date.today().isoformat()}.
Use as ferramentas para buscar dados e fazer contas. Nunca invente números nem calcule datas de cabeça. 
Informação técnica e de procedimento vem só dos documentos (buscar_documentos). Se não achar, diga que não encontrou.
Ações que alteram dados: chame a ferramenta; o sistema pede a confirmação.
Responda direto, em português, curto, sem comentar o que você está fazendo.
Ao calcular, diga de qual documento veio cada dado de entrada.
Cite a fonte em toda informação dos documentos, sempre com o nome completo: [nome-do-arquivo.pdf, p. X]. Nunca cite só a página."""

# ---------- 3. O motor do agente ----------
# Antes o laço fazia tudo de uma vez e parava no input() para confirmar.
# Numa tela web não existe input(): a confirmação é um botão, que chega DEPOIS.
# Por isso o laço agora é dividido em duas funções:
#   avancar()  → roda até ter a resposta final OU até precisar de confirmação, e PARA;
#   decidir()  → recebe o "sim" ou "não" do usuário e continua de onde parou.


def executar(mensagens, chamada, passos, ok=True):
    """Roda uma ferramenta (ou registra que o usuário recusou) e guarda o resultado."""
    if ok:
        resultado = FUNCOES[chamada["nome"]](**chamada["args"])
    else:
        resultado = {"erro": "O usuário não confirmou."}
    passos.append({"nome": chamada["nome"], "args": chamada["args"], "resultado": resultado})
    mensagens.append({"role": "tool", "tool_call_id": chamada["id"],
                      "content": json.dumps(resultado, ensure_ascii=False)})


def avancar(mensagens, pendentes=None):
    """Roda o agente até a resposta final ou até uma ferramenta de escrita.

    Devolve um dicionário:
      {"tipo": "resposta",  "texto": ..., "passos": [...]}
      {"tipo": "confirmar", "chamada": {...}, "pendentes": [...], "passos": [...]}
    """
    passos = []
    for _ in range(8):  # limite de segurança
        if not pendentes:
            r = ia.chat.completions.create(
                model=MODELO_CHAT, messages=mensagens, tools=FERRAMENTAS, temperature=0)
            msg = r.choices[0].message
            if not msg.tool_calls:  # resposta final
                mensagens.append({"role": "assistant", "content": msg.content})
                return {"tipo": "resposta", "texto": msg.content, "passos": passos}
            mensagens.append(msg.model_dump(exclude_none=True))
            pendentes = [{"id": c.id, "nome": c.function.name,
                          "args": json.loads(c.function.arguments)} for c in msg.tool_calls]
        while pendentes:
            chamada = pendentes[0]
            if chamada["nome"] in ESCRITA:  # para e pede confirmação
                return {"tipo": "confirmar", "chamada": chamada,
                        "pendentes": pendentes, "passos": passos}
            pendentes.pop(0)
            executar(mensagens, chamada, passos)
    return {"tipo": "resposta", "texto": "Parei: passos demais.", "passos": passos}


def decidir(mensagens, pendentes, ok):
    """Continua depois do Confirmar (ok=True) ou do Cancelar (ok=False)."""
    passos = []
    executar(mensagens, pendentes.pop(0), passos, ok)
    r = avancar(mensagens, pendentes)
    r["passos"] = passos + r["passos"]
    return r


def nova_conversa():
    return [{"role": "system", "content": INSTRUCOES}]


def perguntar(pergunta):
    """Modo terminal, para os testes: usa o mesmo motor, com input() no lugar do botão."""
    mensagens = nova_conversa() + [{"role": "user", "content": pergunta}]
    r = avancar(mensagens)
    while True:
        for p in r["passos"]:
            print(f"  → {p['nome']}({p['args']})\n  ← {p['resultado']}")
        if r["tipo"] == "resposta":
            print(f"\nIA: {r['texto']}")
            return
        c = r["chamada"]
        print(f"  → a IA quer: {c['nome']}({c['args']})")
        ok = input("    Confirmar? (s/n) ").strip().lower() == "s"
        r = decidir(mensagens, r["pendentes"], ok)


if __name__ == "__main__":
    for p in ["Calcula a potência do transportador do PRJ070000 com rosca de 250 mm e salva no projeto",
              "Quais cálculos já foram feitos no PRJ070000?"]:
        print("\n" + "=" * 60 + f"\nVOCÊ: {p}")
        perguntar(p)
