import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader
from supabase import create_client

load_dotenv()
ia = OpenAI(base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"))
banco = create_client(os.getenv("SUPABASE_URL"),
                      os.getenv("SUPABASE_SERVICE_KEY"))

PASTA = Path("doc/pdfs")
MODELO = "openai/text-embedding-3-small"
TAMANHO = 200  # palavras por trecho
SOBRA = 40     # palavras repetidas entre um trecho e o seguinte


def dividir(texto):
    """Corta o texto de uma página em trechos de até TAMANHO palavras."""
    palavras = texto.split()
    trechos = []
    passo = TAMANHO - SOBRA                                # (1)
    for inicio in range(0, len(palavras), passo):
        trechos.append(" ".join(palavras[inicio:inicio + TAMANHO]))
        if inicio + TAMANHO >= len(palavras):
            break
    return trechos


def limpar(texto):
    """Tira as linhas de cabeçalho e rodapé que se repetem em todas as páginas."""
    boas = []
    for linha in texto.splitlines():
        if linha.startswith("Vetor Engenharia ·"):
            continue
        if linha.startswith("Página "):
            continue
        if "Documento fictício" in linha:
            continue
        boas.append(linha)
    return "\n".join(boas)


def vetores(textos):
    """Manda vários textos de uma vez e recebe um vetor para cada um."""
    r = ia.embeddings.create(model=MODELO, input=textos)
    return [item.embedding for item in r.data]


for pdf in sorted(PASTA.glob("*.pdf")):
    # não indexar o mesmo PDF duas vezes
    ja_existe = banco.table("documentos").select(
        "id").eq("nome", pdf.name).execute()   # (2)
    if ja_existe.data:
        print(f"pulando {pdf.name} (já indexado)")
        continue

    doc = banco.table("documentos").insert({"nome": pdf.name}).execute()
    doc_id = doc.data[0]["id"]

    linhas = []
    for numero, pagina in enumerate(PdfReader(pdf).pages, start=1):             # (3)
        texto = limpar(pagina.extract_text() or "")
        for trecho in dividir(texto):
            linhas.append(
                # (4)
                {"documento_id": doc_id, "pagina": numero, "texto": trecho})

    if not linhas:
        print(f"{pdf.name}: sem texto (PDF escaneado?)")
        continue

    for linha, vetor in zip(linhas, vetores([l["texto"] for l in linhas])):
        linha["embedding"] = vetor

    banco.table("trechos").insert(linhas).execute()
    print(f"{pdf.name}: {len(linhas)} trechos")
