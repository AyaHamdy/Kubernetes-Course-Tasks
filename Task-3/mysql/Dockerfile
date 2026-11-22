FROM mysql:8.4

# Default database, application user and replication user.
# Override any of them with environment variables at runtime.
# MYSQL_ROOT_PASSWORD has no default: it must be given at runtime.
ENV APP_DB_NAME=webapp \
    APP_DB_USER=webapp \
    APP_DB_PASSWORD=webapp123 \
    MYSQL_REPL_USER=repl \
    MYSQL_REPL_PASSWORD=repl123 \
    MYSQL_ROLE=source \
    MYSQL_INITDB_SKIP_TZINFO=1

# Server settings needed for source/replica replication
COPY conf/replication.cnf /etc/mysql/conf.d/replication.cnf

# Tables and default data used by the app
COPY schema/schema.sql /opt/webapp/schema.sql

# Runs once, on the first start with an empty data directory
COPY initdb/01-setup.sh /docker-entrypoint-initdb.d/01-setup.sh
