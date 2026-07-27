-- Update default memory embedding config (model & dimension) for PostgreSQL
UPDATE memory_service_configs SET "value" = 'bge-m3' WHERE "key" = 'memory_embedding_model';
UPDATE memory_service_configs SET "value" = '1024' WHERE "key" = 'memory_embedding_dimensions';
