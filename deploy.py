import os
import zipfile
import boto3
import botocore
import logging


logging.basicConfig(filename="logs.log", level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

STACK_NAME = "assignment-1-s3-sync"

# ZIP the Lambda Code
def zip_lambda(source_dir, zip_filename):
    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(source_dir):
            for f in files:
                full_path = os.path.join(root, f)
                arcname = os.path.relpath(full_path, source_dir)
                zf.write(full_path, arcname)
    logger.info("Created ZIP: %s", zip_filename)

# Upload Lambda Artifact Into Deployment Bucket
def upload_artifact(bucket, key, file_path, s3):
    logger.info("Uploading %s to S3", file_path)
    s3.upload_file(file_path, bucket, key)
    logger.info("Uploaded successfully")

# CloudFormation Stack Deployment
def deploy_stack(cloudformation_client, template_body, params):
    try:
        cloudformation_client.describe_stacks(StackName=STACK_NAME)
        exists = True
    except botocore.exceptions.ClientError:
        exists = False

    if exists:
        logger.info("Updating stack:")
        resp = cloudformation_client.update_stack(
            StackName=STACK_NAME,
            TemplateBody=template_body,
            Parameters=params,
            Capabilities=['CAPABILITY_NAMED_IAM']
        )
        waiter = cloudformation_client.get_waiter('stack_update_complete')
    else:
        logger.info("Creating stack:")
        resp = cloudformation_client.create_stack(
            StackName=STACK_NAME,
            TemplateBody=template_body,
            Parameters=params,
            Capabilities=['CAPABILITY_NAMED_IAM']
        )
        waiter = cloudformation_client.get_waiter('stack_create_complete')

    logger.info("Stack operation started: %s", resp['StackId'])
    waiter.wait(StackName=STACK_NAME)
    logger.info("Stack creation/update complete!")

def main_func():
    deployment_key = "lambda_artifact.zip"
    zip_lambda("Lambda_Function", deployment_key)

    s3 = boto3.client("s3")
    cloudformation_client = boto3.client("cloudformation")

    # Upload ZIP to artifacts bucket created by CFN
    deployment_bucket = f"{STACK_NAME}-artifacts"
    upload_artifact(deployment_bucket, deployment_key, deployment_key, s3)

    # Read template
    with open("template.yaml") as f:
        template_body = f.read()

    # CFN parameters
    params = [
        {"ParameterKey": "DeploymentObjectKey", "ParameterValue": deployment_key}
    ]

    # Deploy/update stack
    deploy_stack(cloudformation_client, template_body, params)


if __name__ == "__main__":
    main_func()
