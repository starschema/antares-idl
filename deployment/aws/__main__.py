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
import pulumi_aws as aws

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
sys.path.insert(0, f"{currentdir}/../../lib")

import efs_eks
import msk
import msk_snowflake_connector as msc
import msk_s3_connector as ms3c
import ecr
from antares_common.config import config
from antares_common.resources import resources, component_enabled


aws_account_id = aws.get_caller_identity().account_id
pulumi.export("aws_account_id", aws_account_id)
resources["aws_account_id"] = aws_account_id


if component_enabled("efs-eks"):
    efs_eks.deploy()

if component_enabled("msk"):
    antares_kafka_cluster, antares_bucket, aws_security_group = msk.deploy_msk()

    snowflake_stack_ref = pulumi.StackReference(
        f"{config.org}/antares-idl-snowflake/{config.stack}"
    )

    if component_enabled("msk-snowflake-connector"):
        msc.deploy_msk_snowflake_connector(
            antares_kafka_cluster,
            aws_security_group,
            antares_bucket,
            snowflake_stack_ref,
        )

    if component_enabled("msk-s3-connector"):
        ms3c.deploy_msk_s3_connector(
            antares_kafka_cluster, aws_security_group, antares_bucket
        )

if component_enabled("ecr"):
    ecr.deploy()
