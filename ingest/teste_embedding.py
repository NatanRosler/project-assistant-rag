import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

cliente = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

r = cliente.embeddings.create(
    model="openai/text-embedding-3-small",
    input="tensão da corrente da esteira",
)

print(len(r.data[0].embedding))  # esperado: 1536
