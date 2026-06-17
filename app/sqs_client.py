
import boto3
import json
import os
from datetime import datetime


sqs = boto3.client("sqs", region_name=os.getenv("AWS_REGION", "us-east-1"))

def push_flagged_transaction(transaction_id: str, account_id: str, amount: float, reason: str, timestamp: datetime):
    # Push flagged transaction as a JSON message to the SQS queue.
    
    queue_url = os.getenv("SQS_QUEUE_URL")

    if not queue_url:
        raise ValueError("SQS_QUEUE_URL environment variable is not set")

    message = {
        "transaction_id": transaction_id,
        "account_id": account_id,
        "amount": amount,
        "reason": reason,
        "timestamp": timestamp.isoformat(),  # convert datetime to string
    }

    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message),  # Convert dict to JSON string
    )

    return response