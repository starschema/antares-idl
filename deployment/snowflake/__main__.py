"""
MIT License

Copyright (c) 2022 HCLTech

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


import os
import sys
import inspect
import pulumi
import json

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
sys.path.insert(0, f"{currentdir}/../../lib")

import staging_schema as staging_s
import datamart_schema as datamart_s
import pulumi_snowflake as snowflake
from antares_common.config import config
from antares_common.resources import resources, component_enabled


pulumi_config = pulumi.Config()
generated_creds_file = os.environ.get("PULUMI_GENERATED_CREDS_FILE")


def deploy_db():
    stack_suffix = config["stack"][:].upper()

    if config.get("/snowflake/default-warehouse"):
        wh_name = config.get("/snowflake/default-warehouse")
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
        wh_name = warehouse.name

    database = snowflake.Database(
        "antares-database",
        name=f"ANTARES_{stack_suffix}",
        comment="Database for Kafka Connector",
    )

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

    return database, wh_name


db, wh_name = deploy_db()

reader_roles = []
creds = []

if component_enabled("kafka-schema"):
    (
        kafka_schema,
        kafka_writer_role,
        kafka_reader_role,
        kafka_user,
        kafka_password,
        kafka_tls_key,
    ) = staging_s.deploy_staging_schema("Kafka", db, wh_name)

    reader_roles.append(kafka_reader_role)

    creds = pulumi.Output.all(creds, kafka_user.name, kafka_password.result).apply(
        lambda args: args[0] + [{"kafka_username": args[1], "kafka_password": args[2]}]
    )


if component_enabled("hvr-schema"):
    (
        hvr_schema,
        hvr_writer_role,
        hvr_reader_role,
        hvr_user,
        hvr_password,
        hvr_tls_key,
    ) = staging_s.deploy_staging_schema("HVR", db, wh_name)

    reader_roles.append(hvr_reader_role)

    creds = pulumi.Output.all(creds, hvr_user.name, hvr_password.result).apply(
        lambda args: args[0] + [{"hvr_username": args[1], "hvr_password": args[2]}]
    )


if component_enabled("datamart-schema"):
    (
        datamart_schema,
        datamart_writer_role,
        datamart_reader_role,
        datamart_user,
        datamart_password,
        datamart_tls_key,
    ) = datamart_s.deploy_datamart_schema("Datamart", db, wh_name, reader_roles)

    creds = pulumi.Output.all(
        creds, datamart_user.name, datamart_password.result
    ).apply(
        lambda args: args[0]
        + [{"datamart_username": args[1], "datamart_password": args[2]}]
    )

if generated_creds_file:
    print(generated_creds_file)

    def store_creds(creds):
        with open(generated_creds_file, "w") as f:
            f.write(json.dumps(creds, indent=4))

    creds.apply(store_creds)
