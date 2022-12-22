
# Kubernetes module for Antares iDL

## Components

 * `efs`: efs storage class for EKS clusters on AWS. AWS EKS provides gp2 ebs storage by default, which does not provide the necessary failover support for distributed clusters (like multi-AZ deployments)
 * `airbyte`: open source ingestion application Airbyte

## Deploy componeents


```
pulumi config org <your_pulumi_org>
pulumi config set --path 'components.<component>' [true|false]
pulumi up
```

## Potential Issues

1. After deploying EFS on EKS, the PVC throws: `status code: 400, Failed to fetch File System info: Describe File System failed: WebIdentityErr: failed to retrieve credentials`

```
  Warning  ProvisioningFailed  7m41s  efs.csi.aws.com_efs-csi-controller-7f64bc4548-vvn88_b4e4f5df-b8aa-4a2b-af45-a5cf72f63923  failed to provision volume with StorageClass "efs-sc": rpc error: code = Internal desc = Failed to fetch File System info: Describe File System failed: WebIdentityErr: failed to retrieve credentials
caused by: InvalidIdentityToken: No OpenIDConnect provider found in your account for https://oidc.eks.eu-central-1.amazonaws.com/id/683407ADCA408C02D6B18AF8AC769039
           status code: 400, request id: 8ea65c50-337a-4e51-bbec-bb33dca8ce32
```

Follow the instructions at https://aws.amazon.com/premiumsupport/knowledge-center/eks-troubleshoot-oidc-and-irsa/. If your OIDC is not registered in AIM, then issue `eksctl utils associate-iam-oidc-provider --cluster my-cluster --approve`. 
