-- Cálculos de engenharia salvos dentro de um projeto
-- Rode no SQL Editor do Supabase depois do 003_documentos_no_projeto.sql.

create table calculos (
  id bigint generated always as identity primary key,
  projeto_id bigint not null references projetos(id) on delete cascade,
  tipo text not null,          -- ex.: potencia_helicoidal
  entradas jsonb not null,     -- ex.: {"vazao_m3h": 12, "densidade_t_m3": 0.6, ...}
  resultado jsonb not null,    -- ex.: {"potencia_kw": 0.455, ...}
  fontes jsonb,                -- ex.: {"vazao_m3h": "proposta-PRJ070000...pdf, p. 1", ...}
  criado_em timestamptz default now()
);

alter table calculos enable row level security;