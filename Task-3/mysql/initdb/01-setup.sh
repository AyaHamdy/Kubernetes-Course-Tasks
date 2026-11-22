#!/bin/bash
# Runs ONCE, the first time the container starts with an empty data directory.
# The official MySQL entrypoint sources this file, so docker_process_sql,
# mysql_note and mysql_error are available here.
#
#   MYSQL_ROLE=source   -> write server: database, users, tables, default data
#   MYSQL_ROLE=replica  -> read server: copies everything from the source

case "${MYSQL_ROLE}" in

  source)
    mysql_note "Role: source (write). Creating database '${APP_DB_NAME}', users and tables"
    docker_process_sql <<EOSQL
CREATE DATABASE IF NOT EXISTS \`${APP_DB_NAME}\`;
CREATE USER IF NOT EXISTS '${APP_DB_USER}'@'%' IDENTIFIED BY '${APP_DB_PASSWORD}';
GRANT SELECT, INSERT, UPDATE, DELETE ON \`${APP_DB_NAME}\`.* TO '${APP_DB_USER}'@'%';
CREATE USER IF NOT EXISTS '${MYSQL_REPL_USER}'@'%' IDENTIFIED BY '${MYSQL_REPL_PASSWORD}';
GRANT REPLICATION SLAVE ON *.* TO '${MYSQL_REPL_USER}'@'%';
EOSQL
    docker_process_sql --database="${APP_DB_NAME}" < /opt/webapp/schema.sql
    ;;

  replica)
    if [ -z "${MYSQL_SOURCE_HOST}" ]; then
      mysql_error "MYSQL_SOURCE_HOST must be set when MYSQL_ROLE=replica"
    fi

    # Every server needs a unique server_id. Build it from the Pod IP.
    if [ -n "${POD_IP}" ]; then
      IFS=. read -r _ _ ip3 ip4 <<< "${POD_IP}"
      SERVER_ID=$(( 1000 + ip3 * 256 + ip4 ))
    else
      SERVER_ID=$(( 1000 + RANDOM ))
    fi

    mysql_note "Role: replica (read). server_id=${SERVER_ID}, source=${MYSQL_SOURCE_HOST}"
    docker_process_sql <<EOSQL
SET PERSIST server_id = ${SERVER_ID};
CHANGE REPLICATION SOURCE TO
  SOURCE_HOST='${MYSQL_SOURCE_HOST}',
  SOURCE_PORT=3306,
  SOURCE_USER='${MYSQL_REPL_USER}',
  SOURCE_PASSWORD='${MYSQL_REPL_PASSWORD}',
  SOURCE_AUTO_POSITION=1,
  GET_SOURCE_PUBLIC_KEY=1,
  SOURCE_CONNECT_RETRY=10,
  SOURCE_RETRY_COUNT=8640;
START REPLICA;
SET PERSIST super_read_only = ON;
EOSQL
    ;;

  *)
    mysql_error "Unknown MYSQL_ROLE '${MYSQL_ROLE}' (use 'source' or 'replica')"
    ;;
esac
