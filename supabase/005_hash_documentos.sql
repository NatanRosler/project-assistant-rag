-- "Impressão digital" (SHA-256) de cada PDF indexado.
-- Serve para perceber quando um arquivo com o MESMO nome mudou e precisa ser reindexado.
-- Rode no SQL Editor do Supabase depois do 004_calculos.sql.

alter table documentos add column hash text;