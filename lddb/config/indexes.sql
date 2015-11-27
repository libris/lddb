CREATE INDEX idx_lddb_alive ON lddb (id) WHERE deleted IS NOT true;
CREATE INDEX idx_lddb_modified ON lddb (modified);
CREATE INDEX idx_lddb_manifest ON lddb USING GIN (manifest jsonb_path_ops);
CREATE INDEX idx_lddb_quoted ON lddb USING GIN (quoted jsonb_path_ops);
CREATE INDEX idx_lddb_entry ON lddb USING GIN ((data->'descriptions'->'entry') jsonb_path_ops);
CREATE INDEX idx_lddb_entry_type ON lddb ((data->'descriptions'->'entry'->>'@type'));
CREATE INDEX idx_lddb_items ON lddb USING GIN ((data->'descriptions'->'items') jsonb_path_ops);
CREATE INDEX idx_lddb_dataset ON lddb ((manifest->>'dataset'));
CREATE INDEX idx_lddb_alt_ids ON lddb USING GIN ((manifest->'alternateIdentifiers') jsonb_path_ops);

CREATE INDEX idx_lddb__versions_id ON lddb__versions (id);
CREATE INDEX idx_lddb__versions_modified ON lddb__versions (modified);
CREATE INDEX idx_lddb__versions_checksum ON lddb__versions (checksum);
CREATE INDEX idx_lddb__versions_manifest ON lddb__versions USING GIN (manifest jsonb_path_ops);
CREATE INDEX idx_lddb__versions_dataset ON lddb__versions USING GIN ((manifest->'dataset') jsonb_path_ops);
