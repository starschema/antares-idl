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


def deploy_staging_schema(source_system_label, database, warehouse):
    source_system_label_upper = source_system_label.upper()
    source_system_label_lower = source_system_label.lower()

    schema = snowflake.Schema(
        f"antares-schema-{source_system_label_lower}",
        name=f"{source_system_label_upper}_LANDING_{stack_suffix}",
        database=database.name,
        comment=f"Schema for {source_system_label} Data Landing Zone",
    )

    writer_role = snowflake.Role(
        f"antares-{source_system_label_lower}-writer-role",
        name=f"ANTARES_{source_system_label_upper}_WRITE_ROLE_{stack_suffix}",
        comment=f"Writer Role for {source_system_label} Data Landing Zone",
    )

    reader_role = snowflake.Role(
        f"antares-{source_system_label_lower}-reader-role",
        name=f"ANTARES_{source_system_label_upper}_READ_ROLE_{stack_suffix}",
        comment=f"Reader Role for {source_system_label} Data Landing Zone",
    )

    db_grant = snowflake.DatabaseGrant(
        f"db-grant-{source_system_label_lower}",
        database_name=database.name,
        privilege="USAGE",
        roles=[writer_role.name, reader_role.name],
    )

    reader_schema_grants = list(
        map(
            lambda privilege: snowflake.SchemaGrant(
                f"reader-schema-grant-{source_system_label_lower}-{privilege.replace(' ', '_')}",
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
                f"writer-schema-grant-{source_system_label_lower}-{privilege.replace(' ', '_')}",
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
        f"reader-table-grant-{source_system_label_lower}",
        database_name=database.name,
        on_future=True,
        privilege="SELECT",
        roles=[reader_role.name],
        schema_name=schema.name,
        with_grant_option=False,
    )

    tls_key = tls.PrivateKey(
        f"{source_system_label_lower}-tls-key", algorithm="RSA", rsa_bits=4096
    )

    password = random.RandomPassword(
        f"{source_system_label_lower}-user-password", length=16, special=True
    )

    public_key_singleline = tls_key.public_key_pem.apply(
        lambda public_key: public_key.replace("-----BEGIN PUBLIC KEY-----", "")
        .replace("-----END PUBLIC KEY-----", "")
        .replace("\n", "")
    )

    user = snowflake.User(
        f"{source_system_label_lower}-user",
        name=f"ANTARES_{source_system_label_upper}_USER_{stack_suffix}",
        password=password.result,
        comment=f"User for the {source_system_label_upper}",
        default_role=writer_role.name,
        rsa_public_key=public_key_singleline,
        default_warehouse=warehouse,
    )

    role_grant = snowflake.RoleGrants(
        f"user-role-grant-{source_system_label_lower}",
        role_name=writer_role.name,
        users=[user.name],
    )

    pulumi.export(f"username-{source_system_label_lower}", user.name)
    pulumi.export(f"password-{source_system_label_lower}", password.result)
    pulumi.export(
        f"private-keypair-pem-{source_system_label_lower}", tls_key.private_key_pem
    )
    pulumi.export(
        f"private-key-no-headers-{source_system_label_lower}",
        tls_key.private_key_pem.apply(
            lambda pk: pem_keypair_to_private_key_no_headers(pk)
        ),
    )
    pulumi.export(f"public-key-pem-{source_system_label_lower}", tls_key.public_key_pem)
    pulumi.export(f"reader-role-{source_system_label_lower}", reader_role.name)
    pulumi.export(f"writer-role-{source_system_label_lower}", writer_role.name)

    pulumi.export(f"antares-schema-{source_system_label_lower}", schema.name)

    return schema, writer_role, reader_role, user, password, tls_key
