-- Cada PDF enviado
create extension if not exists vector with schema extensions;
create table documentos (
  id bigint generated always as identity primary key,
  nome text not null,
  projeto text,
  criado_em timestamptz default now()
);

-- Cada pedaço de texto de um PDF, com o vetor dele
create table trechos (
  id bigint generated always as identity primary key,
  documento_id bigint references documentos(id) on delete cascade,
  pagina int,
  texto text not null,
  embedding vector(1536)
);

-- Busca: recebe o vetor da pergunta e devolve os trechos mais parecidos
create or replace function buscar_trechos(
  vetor_pergunta vector(1536),
  quantidade int default 5
)
returns table (id bigint, documento text, pagina int, texto text, similaridade float)
language sql stable
as $$
  select t.id, d.nome, t.pagina, t.texto,
         1 - (t.embedding <=> vetor_pergunta) as similaridade
  from trechos t
  join documentos d on d.id = t.documento_id
  order by t.embedding <=> vetor_pergunta
  limit quantidade;
$$;

-- Segurança: bloqueia acesso pela chave pública
alter table documentos enable row level security;
alter table trechos enable row level security;