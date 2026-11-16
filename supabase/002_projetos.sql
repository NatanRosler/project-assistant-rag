-- Projetos e lançamentos de horas (dados fictícios da "Vetor Engenharia")
-- Rode no SQL Editor do Supabase depois do 001_schema.sql.

-- Cada projeto do escritório
create table projetos (
  id bigint generated always as identity primary key,
  codigo text not null unique,             -- ex.: PRJ060000
  descricao text not null,
  cliente text not null,
  horas_previstas numeric not null,
  entrega date not null,
  concluido_pct int not null default 0 check (concluido_pct between 0 and 100),
  criado_em timestamptz default now()
);

-- Cada lançamento de horas trabalhadas num projeto
create table lancamentos (
  id bigint generated always as identity primary key,
  projeto_id bigint not null references projetos(id) on delete cascade,
  etapa text not null,
  data date not null,
  duracao_min int not null check (duracao_min > 0),
  criado_em timestamptz default now()
);

-- Segurança: igual às outras tabelas, nada passa pela chave pública
alter table projetos enable row level security;
alter table lancamentos enable row level security;

-- ---------- Dados de exemplo ----------
insert into projetos (codigo, descricao, cliente, horas_previstas, entrega, concluido_pct) values
  ('PRJ060000', 'Esteira de roletes 6 m',               'Alfa Embalagens (fictício)', 275, '2026-11-10', 59),
  ('PRJ070000', 'Transportador helicoidal 12 m³/h',     'Delta Automação (fictício)', 190, '2026-11-27', 35),
  ('PRJ080000', 'Pórtico com talha elétrica 2 t',       'Beta Logística (fictício)',  120, '2026-12-18', 10);

-- PRJ060000: 168 h lançadas
insert into lancamentos (projeto_id, etapa, data, duracao_min)
select id, etapa, data::date, duracao_min from projetos, (values
  ('Reunião de início',   '2026-09-01',  360),
  ('Pré-projeto',         '2026-09-08', 2400),
  ('Modelagem 3D',        '2026-09-22', 3600),
  ('Modelagem 3D',        '2026-10-06', 1200),
  ('Detalhamento',        '2026-10-20', 2520)
) as l(etapa, data, duracao_min)
where codigo = 'PRJ060000';

-- PRJ070000: 66 h lançadas (etapas da proposta)
insert into lancamentos (projeto_id, etapa, data, duracao_min)
select id, etapa, data::date, duracao_min from projetos, (values
  ('Reunião de início',   '2026-10-13',  360),
  ('Pré-projeto',         '2026-10-20', 2400),
  ('Modelagem 3D',        '2026-11-03', 1200)
) as l(etapa, data, duracao_min)
where codigo = 'PRJ070000';

-- PRJ080000: 12 h lançadas
insert into lancamentos (projeto_id, etapa, data, duracao_min)
select id, etapa, data::date, duracao_min from projetos, (values
  ('Reunião de início',   '2026-11-04',  240),
  ('Pré-projeto',         '2026-11-11',  480)
) as l(etapa, data, duracao_min)
where codigo = 'PRJ080000';