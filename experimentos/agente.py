import json
import os
from datetime import date, timedelta
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()
ia = OpenAI(base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"))
banco = create_client(os.getenv("SUPABASE_URL"),
                      os.getenv("SUPABASE_SERVICE_KEY"))
MODELO_CHAT = os.getenv("MODELO_CHAT")
LIMITE = 0.30
# ---------- 1. As ferramentas "de verdade" (aqui, de mentira) ----------
FERIADOS = {"2026-11-02", "2026-11-15", "2026-11-20", "2026-12-25"}


def ver_projeto(codigo):
    if codigo != "PRJ060000":
        return {"erro": f"Projeto {codigo} não encontrado."}
    return {"codigo": "PRJ060000", "descricao": "Esteira de roletes 6 m", "concluido_pct": 59,
            "horas_lancadas": 168, "horas_previstas": 275, "entrega": "2026-11-10"}


def calcular_dias_uteis(data_inicio, dias):
    d = date.fromisoformat(data_inicio)
    contados = 0
    while contados < dias:
        if d.weekday() < 5 and d.isoformat() not in FERIADOS:
            contados += 1
        if contados < dias:
            d += timedelta(days=1)
    return {"data_final": d.isoformat()}


def lancar_horas(projeto, etapa, data, duracao_min):
    return {"ok": True, "mensagem": f"{duracao_min} min lançados em {projeto}, {etapa}, {data}."}


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


FUNCOES = {"ver_projeto": ver_projeto,
           "calcular_dias_uteis": calcular_dias_uteis, "lancar_horas": lancar_horas,
           "buscar_documentos": buscar_documentos}
ESCRITA = {"lancar_horas"}

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
            "required": ["pergunta"]}}}
]

INSTRUCOES = f"""Você é o assistente do painel de projetos de um engenheiro mecânico que projeta
equipamentos industriais (esteiras, transportadores, içamento). Hoje é {date.today().isoformat()}.
Use as ferramentas para buscar dados e fazer contas. Nunca invente números nem calcule datas de cabeça. 
Informação técnica e de procedimento vem só dos documentos (buscar_documentos). Se não achar, diga que não encontrou.
Ações que alteram dados: chame a ferramenta; o sistema pede a confirmação.
Responda direto, em português, curto, sem comentar o que você está fazendo.
Ao usar informação dos documentos, cite a fonte assim: [nome do documento, p. X]."""

# ---------- 3. O laço do agente ----------


def perguntar(pergunta):
    mensagens = [{"role": "system", "content": INSTRUCOES},
                 {"role": "user", "content": pergunta}]
    for passo in range(5):
        r = ia.chat.completions.create(
            model=MODELO_CHAT, messages=mensagens, tools=FERRAMENTAS, temperature=0)
        msg = r.choices[0].message
        if not msg.tool_calls:
            print(f"\nIA: {msg.content}")
            return
        mensagens.append(msg.model_dump(exclude_none=True))
        for chamada in msg.tool_calls:
            nome = chamada.function.name
            args = json.loads(chamada.function.arguments)
            print(f"  → a IA pediu: {nome}({args})")
            if nome in ESCRITA:
                ok = input("    Confirmar? (s/n) ").strip().lower() == "s"
                resultado = FUNCOES[nome](
                    **args) if ok else {"erro": "O usuário não confirmou."}
            else:
                resultado = FUNCOES[nome](**args)
            print(f"  ← resultado: {resultado}")
            mensagens.append({"role": "tool", "tool_call_id": chamada.id,
                              "content": json.dumps(resultado, ensure_ascii=False)})
    print("Parei: passos demais.")


for p in ["Quanto falta no PRJ060000?",
          "Qual a tensão correta da corrente da esteira?",
          "Como é o bloqueio e etiquetagem antes da manutenção?",
          "O PRJ060000 atrasa se eu precisar de mais 10 dias úteis a partir de hoje?",
          "Qual a cor favorita do Paulo?",]:
    print("\n" + "=" * 60 + f"\nVOCÊ: {p}")
    perguntar(p)
