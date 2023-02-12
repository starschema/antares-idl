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

import base64
import pulumi_aws as aws
import pulumi
from antares_common.config import config
from antares_common.resources import resources
import pulumi_docker as docker


def get_registry_info(rid):
    creds = aws.ecr.get_credentials(registry_id=rid)
    decoded = base64.b64decode(creds.authorization_token).decode()
    parts = decoded.split(":")
    if len(parts) != 2:
        raise Exception("Invalid credentials")
    return docker.ImageRegistry(
        server=creds.proxy_endpoint, username=parts[0], password=parts[1]
    )


def deploy():
    for container in config.get("/ecr/containers", []):
        ecr_repository = aws.ecr.Repository(
            f"antares-ecr-{container['name']}",
            image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
                scan_on_push=False,
            ),
            image_tag_mutability="MUTABLE",
            force_delete=True,
        )

        image = docker.Image(
            f"{container['name']}-docker-image",
            build=docker.DockerBuild(
                context=f"../../containers/{container['name']}",
                extra_options=["--platform", "linux/amd64"],
            ),
            image_name=ecr_repository.repository_url,
            local_image_name=container["tag"],
            registry=ecr_repository.registry_id.apply(get_registry_info),
            opts=pulumi.ResourceOptions(depends_on=[ecr_repository]),
        )

        # Export the base and specific version image name.
        pulumi.export(f"{container['name']}-base-image-name", image.base_image_name)
        pulumi.export(f"{container['name']}-full-image-name", image.image_name)
