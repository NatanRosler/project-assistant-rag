import hashlib
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
    """Indexa um PDF e devolve {"trechos": n, "situacao": ...}.

    situacao: "novo"       → o arquivo ainda não existia no banco
              "atualizado" → já existia com esse nome, mas o conteúdo mudou: foi reindexado
              "igual"      → já existia e não mudou nada: não faz nada
              "sem_texto"  → o PDF não tem texto (escaneado?): não grava nada
    """
    impressao = hashlib.sha256(pdf.read_bytes()).hexdigest()  # muda se 1 byte do arquivo mudar
    antigo = banco.table("documentos").select("id, hash, projeto_id") \
        .eq("nome", pdf.name).execute().data
    if antigo and antigo[0]["hash"] == impressao:
        return {"trechos": 0, "situacao": "igual"}

    # Primeiro lê o PDF e gera os vetores; só depois mexe no banco.
    # Assim, se algo falhar no meio, a versão antiga continua lá inteira.
    paginas = []
    for numero, pagina in enumerate(PdfReader(pdf).pages, start=1):
        texto = limpar(pagina.extract_text() or "")
        for trecho in dividir(texto):
            paginas.append((numero, trecho))
    if not paginas:
        return {"trechos": 0, "situacao": "sem_texto"}
    embeddings = vetores([trecho for _, trecho in paginas])

    situacao = "novo"
    if antigo:
        if projeto_id is None:            # reindexado pelo ingest: mantém o projeto que já tinha
            projeto_id = antigo[0]["projeto_id"]
        banco.table("documentos").delete().eq("id", antigo[0]["id"]).execute()  # trechos vão junto
        situacao = "atualizado"

    doc = banco.table("documentos").insert(
        {"nome": pdf.name, "projeto_id": projeto_id, "hash": impressao}).execute()
    doc_id = doc.data[0]["id"]
    linhas = [{"documento_id": doc_id, "pagina": numero, "texto": trecho, "embedding": vetor}
              for (numero, trecho), vetor in zip(paginas, embeddings)]
    banco.table("trechos").insert(linhas).execute()
    return {"trechos": len(linhas), "situacao": situacao}


if __name__ == "__main__":
    for pdf in sorted(PASTA.glob("*.pdf")):
        r = indexar_pdf(pdf)
        print(f"{pdf.name}: {r['situacao']} ({r['trechos']} trechos)")