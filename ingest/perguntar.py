import os
import sys
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()
ia = OpenAI(base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"))
banco = create_client(os.getenv("SUPABASE_URL"),
                      os.getenv("SUPABASE_SERVICE_KEY"))

# pega a pergunta do terminal; se não tiver nenhuma, usa esta
pergunta = " ".join(sys.argv[1:]) or "qual a tensão correta da corrente?"

# 1. transforma a pergunta em vetor (igual ao teste_embedding)
r = ia.embeddings.create(
    model="openai/text-embedding-3-small", input=pergunta)          # (1)
vetor = r.data[0].embedding

# 2. chama a função do banco
resultado = banco.rpc("buscar_trechos", {
                      # (2) e (3)
                      "vetor_pergunta": vetor, "quantidade": 3}).execute()

# 3. mostra os trechos encontrados
print(f"\nPergunta: {pergunta}\n")
for t in resultado.data:
    print(f"{t['similaridade']:.2f} · {t['documento']} · p. {t['pagina']}")
    print("   " + t["texto"][:200] + "...\n")
