-- Liga cada documento a um projeto (opcional: os manuais e procedimentos gerais ficam sem projeto)
-- Rode no SQL Editor do Supabase depois do 002_projetos.sql.

alter table documentos
  add column projeto_id bigint references projetos(id) on delete set null;

-- A coluna de texto "projeto" do 001 nunca foi usada; a ligação agora é pelo id
alter table documentos drop column projeto;