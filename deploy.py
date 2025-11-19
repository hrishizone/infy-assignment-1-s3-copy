import os
import zipfile
import boto3
import botocore
import logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()          
    ]
)
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
        logger.info("Updating stack ...")

        try:
            resp = cloudformation_client.update_stack(
                StackName=STACK_NAME,
                TemplateBody=template_body,
                Parameters=params,
                Capabilities=['CAPABILITY_NAMED_IAM']
            )

            logger.info("Stack update initiated: %s", resp['StackId'])

            waiter = cloudformation_client.get_waiter('stack_update_complete')
            waiter.wait(StackName=STACK_NAME)

            logger.info("Stack update completed successfully!")

        except botocore.exceptions.ClientError as e:
            if "No updates are to be performed" in str(e):
                logger.info("Stack is already up-to-date.")
                return
            raise

    else:
        logger.info("Creating new stack ...")

        resp = cloudformation_client.create_stack(
            StackName=STACK_NAME,
            TemplateBody=template_body,
            Parameters=params,
            Capabilities=['CAPABILITY_NAMED_IAM']
        )

        logger.info("Stack creation initiated: %s", resp['StackId'])

        waiter = cloudformation_client.get_waiter('stack_create_complete')
        waiter.wait(StackName=STACK_NAME)

        logger.info("Stack creation completed successfully!")


def ensure_bucket_exists(bucket, s3):
    try:
        s3.head_bucket(Bucket=bucket)
        logger.info("Bucket %s already exists", bucket)
    except botocore.exceptions.ClientError:
        logger.info("Bucket %s does not exist, creating...", bucket)
        s3.create_bucket(
            Bucket=bucket,
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"}
        )
        logger.info("Bucket %s created successfully", bucket)

    logger.info("Enabling bucket versioning on %s", bucket)
    s3.put_bucket_versioning(
        Bucket=bucket,
        VersioningConfiguration={"Status": "Enabled"}
    )

def main_func():
    deployment_key = "lambda_artifact.zip"
    zip_lambda("Lambda_Function", deployment_key)

    s3 = boto3.client("s3")
    cloudformation_client = boto3.client("cloudformation")

    deployment_bucket = f"{STACK_NAME}-artifacts"

    ensure_bucket_exists(deployment_bucket, s3)

    upload_artifact(deployment_bucket, deployment_key, deployment_key, s3)

    obj = s3.head_object(Bucket=deployment_bucket, Key=deployment_key)
    version_id = obj["VersionId"]
    logger.info("Uploaded S3 Object Version: %s", version_id)

    with open("template.yaml") as f:
        template_body = f.read()

    params = [
        {"ParameterKey": "DeploymentBucketName", "ParameterValue": deployment_bucket},
        {"ParameterKey": "DeploymentObjectKey", "ParameterValue": deployment_key},
        {"ParameterKey": "DeploymentObjectVersion", "ParameterValue": version_id}
    ]

    deploy_stack(cloudformation_client, template_body, params)


if __name__ == "__main__":
    main_func()
