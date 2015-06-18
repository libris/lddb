CREATE TABLE IF NOT EXISTS lddb (
    id text not null unique primary key,
    data jsonb not null,
    entry jsonb not null,
    created timestamp with time zone not null default now(),
    modified timestamp with time zone not null default now(),
    deleted boolean default false
    );

CREATE INDEX idx_lddb_modified ON lddb (modified);
CREATE INDEX idx_lddb_alive ON lddb (id) WHERE deleted is not true;

CREATE INDEX idx_lddb_dataset ON lddb ((entry->'dataset'));
CREATE INDEX idx_lddb_entry ON lddb USING gin (entry jsonb_path_ops);
CREATE INDEX idx_lddb_graphs ON lddb USING gin ((data->'@graph') jsonb_path_ops);

-- versions
CREATE TABLE IF NOT EXISTS lddb__versions (
    pk serial,
    id text not null,
    checksum char(32) not null,
    data jsonb not null,
    entry jsonb not null,
    modified timestamp with time zone not null default now(),
    unique (id, checksum)
    );

CREATE INDEX idx_lddb__versions_id ON lddb__versions (id);
CREATE INDEX idx_lddb__versions_modified ON lddb__versions (modified);
CREATE INDEX idx_lddb__versions_dataset ON lddb__versions ((entry->'dataset'));
