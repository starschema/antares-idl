import pulumi
import pulumi_aws as aws
import efs_eks

resources = {}

config = pulumi.Config()
components = config.require_object("components")

aws_account_id = aws.get_caller_identity().account_id
pulumi.export("aws_account_id", aws_account_id)
resources["aws_account_id"] = aws_account_id


if components["efs"]:
    efs_eks.deploy_efs(resources)