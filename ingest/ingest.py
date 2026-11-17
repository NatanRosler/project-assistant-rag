import os
import re
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


def dividir(texto):
    """Junta frases inteiras em trechos de até TAMANHO palavras."""
    frases = re.split(
        r"(?<=[.!?])\s+", " ".join(texto.split()))   # quebra depois de . ! ?
    trechos = []
    atual = []                       # frases do trecho que está sendo montado
    for frase in frases:
        palavras_atual = sum(len(f.split()) for f in atual)
        if atual and palavras_atual + len(frase.split()) > TAMANHO:
            trechos.append(" ".join(atual))      # fecha o trecho
            # o próximo começa repetindo a última frase
            atual = atual[-1:]
        atual.append(frase)
    if atual:
        trechos.append(" ".join(atual))        # não esquecer o último
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
    return "\n".join(boas).replace("\x7f", "-")


def vetores(textos):
    """Manda vários textos de uma vez e recebe um vetor para cada um."""
    r = ia.embeddings.create(model=MODELO, input=textos)
    return [item.embedding for item in r.data]


def indexar_pdf(pdf, projeto_id=None):
    """Indexa um PDF e devolve quantos trechos gravou (0 se já existia)."""
    ja_existe = banco.table("documentos").select(
        "id").eq("nome", pdf.name).execute()   # (2)
    if ja_existe.data:
        return 0

    doc = banco.table("documentos").insert(
        {"nome": pdf.name, "projeto_id": projeto_id}).execute()
    doc_id = doc.data[0]["id"]

    linhas = []
    for numero, pagina in enumerate(PdfReader(pdf).pages, start=1):             # (3)
        texto = limpar(pagina.extract_text() or "")
        for trecho in dividir(texto):
            linhas.append(
                # (4)
                {"documento_id": doc_id, "pagina": numero, "texto": trecho})

    if not linhas:
        return 0

    for linha, vetor in zip(linhas, vetores([l["texto"] for l in linhas])):
        linha["embedding"] = vetor

    banco.table("trechos").insert(linhas).execute()
    return len(linhas)


if __name__ == "__main__":
    for pdf in sorted(PASTA.glob("*.pdf")):
        n = indexar_pdf(pdf)
        print(f"{pdf.name}: {n} trechos" if n else f"pulando {pdf.name}")
