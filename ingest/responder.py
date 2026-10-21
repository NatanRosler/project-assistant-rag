import os
import sys
import re
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()
ia = OpenAI(base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"))
banco = create_client(os.getenv("SUPABASE_URL"),
                      os.getenv("SUPABASE_SERVICE_KEY"))
MODELO_CHAT = os.getenv("MODELO_CHAT")
LIMITE = 0.30  # trechos com similaridade abaixo disso são descartados

INSTRUCOES = """Você é o assistente de documentos da Vetor Engenharia.
Responda em português, usando SOMENTE as informações dos trechos fornecidos.
Depois de cada informação, cite a fonte com o número do trecho, por exemplo [1].
Se os trechos não tiverem NENHUMA informação sobre a pergunta, responda apenas: "Não encontrei isso nos documentos."
Se encontrar só parte da resposta, responda essa parte e diga o que ficou de fora, sem usar essa frase.
Nunca invente números, prazos, valores ou procedimentos.
Cite apenas números de trechos que existem na lista. Nunca cite um trecho que não foi fornecido."""


def buscar(pergunta, quantidade=5):
    vetor = ia.embeddings.create(
        model="openai/text-embedding-3-small", input=pergunta).data[0].embedding
    r = banco.rpc("buscar_trechos", {
                  "vetor_pergunta": vetor, "quantidade": quantidade}).execute()
    return [t for t in r.data if t["similaridade"] >= LIMITE]


def montar_contexto(trechos):
    """Numera os trechos para a IA poder citar [1], [2]..."""
    partes = []
    for n, t in enumerate(trechos, start=1):
        partes.append(
            f"[{n}] {t['documento']}, p. {t['pagina']}\n{t['texto']}")
    return "\n\n".join(partes)


pergunta = " ".join(sys.argv[1:]) or "qual a tensão correta da corrente?"
trechos = buscar(pergunta)

if not trechos:
    print("Não encontrei isso nos documentos.")
    sys.exit()

resposta = ia.chat.completions.create(
    model=MODELO_CHAT,
    messages=[
        {"role": "system", "content": INSTRUCOES},
        {"role": "user",
            "content": f"Trechos (numerados de 1 a {len(trechos)}):\n\n{montar_contexto(trechos)}\n\nPergunta: {pergunta}"},
    ],
    temperature=0,
)

texto = resposta.choices[0].message.content
citados = sorted({int(x) for x in re.findall(r"\[(\d+)\]", texto)})
invalidos = [c for c in citados if c < 1 or c > len(trechos)]

print(f"\nPergunta: {pergunta}\n")
print(texto)

if invalidos:
    print(f"\n⚠ A resposta citou fontes que não existem: {invalidos}")

print("\nFontes citadas:")
if not citados:
    print("  nenhuma")
for n in citados:
    if 1 <= n <= len(trechos):
        t = trechos[n - 1]
        print(
            f"  [{n}] {t['documento']} · p. {t['pagina']} · {t['similaridade']:.2f}")
