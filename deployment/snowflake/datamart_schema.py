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


def deploy_datamart_schema(label, database, warehouse, reader_roles):
    label_upper = label.upper()
    label_lower = label.lower()

    schema = snowflake.Schema(
        f"antares-schema-{label_lower}",
        name=f"{label_upper}_{stack_suffix}",
        database=database.name,
        comment=f"Schema for {label} Data Landing Zone",
    )

    writer_role = snowflake.Role(
        f"antares-{label_lower}-writer-role",
        name=f"ANTARES_{label_upper}_WRITE_ROLE_{stack_suffix}",
        comment=f"Writer Role for {label} Data Mart",
    )

    reader_role = snowflake.Role(
        f"antares-{label_lower}-reader-role",
        name=f"ANTARES_{label_upper}_READ_ROLE_{stack_suffix}",
        comment=f"Reader Role for {label} Data Mart",
    )

    db_grant = snowflake.DatabaseGrant(
        f"db-grant-{label_lower}",
        database_name=database.name,
        privilege="USAGE",
        roles=[writer_role.name, reader_role.name],
    )

    reader_schema_grants = list(
        map(
            lambda privilege: snowflake.SchemaGrant(
                f"reader-schema-grant-{label_lower}-{privilege.replace(' ', '_')}",
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
                f"writer-schema-grant-{label_lower}-{privilege.replace(' ', '_')}",
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
        f"reader-table-grant-{label_lower}",
        database_name=database.name,
        on_future=True,
        privilege="SELECT",
        roles=[reader_role.name],
        schema_name=schema.name,
        with_grant_option=False,
    )

    writer_grant = snowflake.TableGrant(
        f"writer-table-grant-{label_lower}",
        database_name=database.name,
        on_future=True,
        privilege="OWNERSHIP",
        roles=[writer_role.name],
        schema_name=schema.name,
        with_grant_option=False,
    )

    # Here we are granting the reader roles of the source schemas to the writer role of the data mart schema
    i = 1
    for upstream_reader_role in reader_roles:
        role_grant = snowflake.RoleGrants(
            f"reader-role-grant-{label_lower}-{str(i)}",
            role_name=upstream_reader_role.name,
            roles=[writer_role.name],
        )
        i = i + 1

    tls_key = tls.PrivateKey(f"{label_lower}-tls-key", algorithm="RSA", rsa_bits=4096)

    password = random.RandomPassword(
        f"{label_lower}-user-password", length=16, special=True
    )

    public_key_singleline = tls_key.public_key_pem.apply(
        lambda public_key: public_key.replace("-----BEGIN PUBLIC KEY-----", "")
        .replace("-----END PUBLIC KEY-----", "")
        .replace("\n", "")
    )

    user = snowflake.User(
        f"{label_lower}-user",
        name=f"ANTARES_{label_upper}_USER_{stack_suffix}",
        password=password.result,
        comment=f"User for the {label_lower}",
        default_role=writer_role.name,
        rsa_public_key=public_key_singleline,
        default_warehouse=warehouse,
    )

    role_grant = snowflake.RoleGrants(
        f"user-role-grant-{label_lower}",
        role_name=writer_role.name,
        users=[user.name],
    )

    pulumi.export(f"username-{label_lower}", user.name)
    pulumi.export(f"password-{label_lower}", password.result)
    pulumi.export(f"private-keypair-pem-{label_lower}", tls_key.private_key_pem)
    pulumi.export(
        f"private-key-no-headers-{label_lower}",
        tls_key.private_key_pem.apply(
            lambda pk: pem_keypair_to_private_key_no_headers(pk)
        ),
    )
    pulumi.export(f"public-key-pem-{label_lower}", tls_key.public_key_pem)
    pulumi.export(f"reader-role-{label_lower}", reader_role.name)
    pulumi.export(f"writer-role-{label_lower}", writer_role.name)

    pulumi.export(f"antares-schema-{label_lower}", schema.name)

    return schema, writer_role, reader_role, user, password, tls_key
