"""A Python Pulumi program"""

import pulumi
import pulumi_snowflake as snowflake
import pulumi_tls as tls
import pulumi_random as random

config = pulumi.Config()

# warehouse_size = config.get("warehouse-size") or "X-SMALL"

# warehouse = snowflake.Warehouse("warehouse",
#     warehouse_size=warehouse_size)

database = snowflake.Database(
    "ANTARES",
    comment="Database for Kafka Connector",
)

schema = snowflake.Schema(
    "KAFKA_STAGING",
    database=database.name,
    comment="Schema for Kafka Connector",
)

writer_role = snowflake.Role(
    "writer-role", comment="Antares Writer Role"
)

reader_role = snowflake.Role(
    "reader-role", comment="Antares Reader Role"
)

db_grant = snowflake.DatabaseGrant(
    "db-grant",
    database_name=database.name,
    privilege="USAGE",
    roles=[writer_role.name, reader_role.name],
)

for privilege in ["USAGE", "CREATE TABLE", "CREATE STAGE", "CREATE PIPE"]:
    schema_grant = snowflake.SchemaGrant(
        f"writer-schema-grant-{privilege.replace(' ', '_')}",
        database_name=database.name,
        privilege=privilege,
        roles=[writer_role.name],
        schema_name=schema.name,
        with_grant_option=False,
    )

for privilege in ["USAGE"]:
    schema_grant = snowflake.SchemaGrant(
        f"reader-schema-grant-{privilege.replace(' ', '_')}",
        database_name=database.name,
        privilege=privilege,
        roles=[reader_role.name],
        schema_name=schema.name,
        with_grant_option=False,
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


tls_key = tls.PrivateKey(
    "tls-key", algorithm="RSA", rsa_bits=4096
)

tls_key.public_key_openssh.apply(lambda key: open("public_key", "w").write(key))

password = random.RandomPassword(
    "password", length=16, special=True
)

public_key = tls_key.public_key_pem.apply(
    lambda public_key: public_key.replace("-----BEGIN PUBLIC KEY-----", "")
    .replace("-----END PUBLIC KEY-----", "")
    .replace("\n", "")
)

user = snowflake.User(
    "user",
    password=password.result,
    comment="User for the Kafka Connector",
    default_role=writer_role.name,
    rsa_public_key=public_key,
)

role_grant = snowflake.RoleGrants(
    "user-role-grant", role_name=writer_role.name, users=[user.name]
)

pulumi.export("user", user.name)
pulumi.export("password", password.result)
pulumi.export("private-key", tls_key.private_key_pem)
pulumi.export("public-key", public_key)
pulumi.export("reader-role", reader_role.name)
pulumi.export("writer-role", writer_role.name)
