import json
import os
from datetime import date, timedelta
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
ia = OpenAI(base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"))
MODELO = os.getenv("MODELO_CHAT")

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


FUNCOES = {"ver_projeto": ver_projeto,
           "calcular_dias_uteis": calcular_dias_uteis, "lancar_horas": lancar_horas}
ESCRITA = {"lancar_horas"}  # estas precisam de confirmação

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
]

INSTRUCOES = f"""Você é o assistente do painel de projetos de um engenheiro mecânico que projeta
equipamentos industriais (esteiras, transportadores, içamento). Hoje é {date.today().isoformat()}.
Use as ferramentas para buscar dados e fazer contas; nunca invente números nem calcule datas de cabeça.
Ações que alteram dados: chame a ferramenta; o sistema pede a confirmação.
Responda direto, em português, curto, sem comentar o que você está fazendo."""

# ---------- 3. O laço do agente ----------


def perguntar(pergunta):
    mensagens = [{"role": "system", "content": INSTRUCOES},
                 {"role": "user", "content": pergunta}]
    for passo in range(5):  # limite de segurança: no máximo 5 idas e voltas
        r = ia.chat.completions.create(
            model=MODELO, messages=mensagens, tools=FERRAMENTAS, temperature=0)
        msg = r.choices[0].message
        if not msg.tool_calls:                       # a IA não pediu ferramenta: é a resposta final
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
          "Se eu começar em 2026-10-29, em que dia terminam 10 dias úteis?",
          "Lança 3 horas de Modelagem 3D hoje no PRJ060000",
          "O que é fator de segurança?"]:
    print("\n" + "=" * 60 + f"\nVOCÊ: {p}")
    perguntar(p)
