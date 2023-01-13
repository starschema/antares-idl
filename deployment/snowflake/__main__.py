"""A Python Pulumi program"""
import os
import inspect
import sys

import pulumi
import pulumi_snowflake as snowflake
import pulumi_tls as tls
import pulumi_random as random


currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
sys.path.insert(0, f"{currentdir}/../../lib")
from antares_common.config import config
from antares_common import pem_keypair_to_private_key_no_headers

stack_suffix = config["stack"][:].upper()


if config.get("/snowflake/default-warehouse"):
    default_warehouse = config.get("/snowflake/default-warehouse")
else:
    warehouse_size = config.get("/snowflake/warehouse-size", "X-SMALL")
    warehouse = snowflake.Warehouse(
        "antares_warehouse",
        name=f"ANTARES_WAREHOUSE_{stack_suffix}",
        auto_resume=True,
        initially_suspended=True,
        auto_suspend=120,
        warehouse_size=warehouse_size,
        enable_query_acceleration=False,
    )
    default_warehouse = warehouse.name

database = snowflake.Database(
    "antares-database",
    name=f"ANTARES_{stack_suffix}",
    comment="Database for Kafka Connector",
)

schema = snowflake.Schema(
    "antares-schema",
    name=f"KAFKA_LANDING_{stack_suffix}",
    database=database.name,
    comment="Schema for Kafka Connector",
)

writer_role = snowflake.Role(
    "antares-writer-role",
    name=f"ANTARES_WRITE_ROLE_{stack_suffix}",
    comment="Antares Writer Role",
)

reader_role = snowflake.Role(
    "antares-reader-role",
    name=f"ANTARES_READ_ROLE_{stack_suffix}",
    comment="Antares Reader Role",
)

db_grant = snowflake.DatabaseGrant(
    "db-grant",
    database_name=database.name,
    privilege="USAGE",
    roles=[writer_role.name, reader_role.name],
)

reader_schema_grants = list(
    map(
        lambda privilege: snowflake.SchemaGrant(
            f"reader-schema-grant-{privilege.replace(' ', '_')}",
            database_name=database.name,
            privilege=privilege,
            enable_multiple_grants=True,
            roles=[reader_role.name],
            schema_name=schema.name,
            with_grant_option=False,
        ),
        ["USAGE"],
    )
)

writer_schema_grants = list(
    map(
        lambda privilege: snowflake.SchemaGrant(
            f"writer-schema-grant-{privilege.replace(' ', '_')}",
            database_name=database.name,
            privilege=privilege,
            roles=[writer_role.name],
            schema_name=schema.name,
            with_grant_option=False,
        ),
        ["USAGE", "CREATE TABLE", "CREATE STAGE", "CREATE PIPE"],
    )
)

reader_grant = snowflake.TableGrant(
    "reader-table-grant",
    database_name=database.name,
    on_future=True,
    privilege="SELECT",
    roles=[reader_role.name],
    schema_name=schema.name,
    with_grant_option=False,
)

tls_key = tls.PrivateKey("tls-key", algorithm="RSA", rsa_bits=4096)

password = random.RandomPassword("password", length=16, special=True)

public_key_singleline = tls_key.public_key_pem.apply(
    lambda public_key: public_key.replace("-----BEGIN PUBLIC KEY-----", "")
    .replace("-----END PUBLIC KEY-----", "")
    .replace("\n", "")
)

user = snowflake.User(
    "user",
    name=f"ANTARES_KAFKA_USER_{stack_suffix}",
    password=password.result,
    comment="User for the Kafka Connector",
    default_role=writer_role.name,
    rsa_public_key=public_key_singleline,
    default_warehouse=default_warehouse,
)

role_grant = snowflake.RoleGrants(
    "user-role-grant", role_name=writer_role.name, users=[user.name]
)

pulumi.export("username", user.name)
pulumi.export("password", password.result)
pulumi.export("private-keypair-pem", tls_key.private_key_pem)
pulumi.export(
    "private-key-no-headers",
    tls_key.private_key_pem.apply(lambda pk: pem_keypair_to_private_key_no_headers(pk)),
)
pulumi.export("public-key-pem", tls_key.public_key_pem)
pulumi.export("reader-role", reader_role.name)
pulumi.export("writer-role", writer_role.name)


snowflake_config = pulumi.Config(name="snowflake")
snowflake_account = snowflake_config.get("account")
snowflake_organization = config.get("/snowflake/organization")
snowflake_region = snowflake_config.get("region")
pulumi.export(
    "snowflake-url",
    f"{snowflake_organization}-{snowflake_account}.snowflakecomputing.com:443",
)
pulumi.export("snowflake-region", snowflake_region)
pulumi.export("antares-database", database.name)
pulumi.export("antares-schema", schema.name)
