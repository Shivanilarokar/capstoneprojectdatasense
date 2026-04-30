TENANTS_SQL = """
CREATE TABLE IF NOT EXISTS tenants (
    tenant_key TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL,
    pg_host TEXT NOT NULL,
    pg_port INTEGER NOT NULL,
    pg_database TEXT NOT NULL,
    pg_user TEXT NOT NULL,
    pg_password TEXT NOT NULL,
    pg_sslmode TEXT NOT NULL,
    pg_connect_timeout INTEGER NOT NULL,
    neo4j_uri TEXT NOT NULL,
    neo4j_username TEXT NOT NULL,
    neo4j_password TEXT NOT NULL,
    neo4j_database TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
""".strip()

USERS_SQL = """
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    provider_subject TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    last_login_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
""".strip()

USER_TENANT_MEMBERSHIPS_SQL = """
CREATE TABLE IF NOT EXISTS user_tenant_memberships (
    email TEXT NOT NULL,
    tenant_key TEXT NOT NULL,
    status TEXT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (email, tenant_key)
);
""".strip()

USER_ROLE_ASSIGNMENTS_SQL = """
CREATE TABLE IF NOT EXISTS user_role_assignments (
    email TEXT NOT NULL,
    tenant_key TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (email, tenant_key, role)
);
""".strip()
