import os
import boto3
import urllib.parse
import logging

s3 = boto3.client('s3')
DEST_BUCKET = os.environ.get("DESTINATION_BUCKET")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info("Received event: %s", event)
    for record in event.get("Records", []):
        if record.get("eventSource") != "aws:s3":
            logger.warning("Skipping non-S3 event: %s", record)
            continue
        src_bucket = record["s3"]["bucket"]["name"]
        logger.info("Received Key: %s", record["s3"]["object"]["key"])
        src_key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        try:
            copy_source = {"Bucket": src_bucket, "Key": src_key}
            s3.copy_object(Bucket=DEST_BUCKET, Key=src_key, CopySource=copy_source)
            logger.info("Copied %s from %s  to%s", src_key, src_bucket, DEST_BUCKET)
        except Exception as e:
            logger.exception("Error copying %s: %s", src_key, str(e))
            raise
  
