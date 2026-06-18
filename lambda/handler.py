import boto3
import json
import os
from datetime import datetime, timezone

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
ses = boto3.client("ses", region_name=os.getenv("AWS_REGION", "us-east-1"))
cloudwatch = boto3.client("cloudwatch", region_name=os.getenv("AWS_REGION", "us-east-1"))

DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")


def handler(event, context):

    #'event' contains the SQS messages.
    #'context' contains Lambda runtime info 

    records = event.get("Records", [])
    for record in records:
        # "body" field in SQS is JSON string
        # Deserialize back into Python dictionary
        body = json.loads(record["body"])
        transaction_id = body["transaction_id"]
        account_id = body["account_id"]
        amount = body["amount"]
        reason = body["reason"]
        timestamp = body["timestamp"]
        print(f"Processing flagged transaction: {transaction_id} for account {account_id}")

        #Write to DynamoDB
        try:
            store_in_dynamodb(transaction_id, account_id, amount, reason, timestamp)
            print(f"Successfully stored transaction {transaction_id} in DynamoDB")
        except Exception as e:
            print(f"Failed to store in DynamoDB: {e}")
            raise  # Re-raise to trigger Lambda retry logic

        # Publish flagged-transaction count so CloudWatch can track volume over time
        try:
            publish_fraud_metric()
        except Exception as e:
            # Metric failure shouldn't block the rest of the pipeline
            print(f"Failed to publish CloudWatch metric: {e}")

        # Send email alert
        try:
            send_email_alert(transaction_id, account_id, amount, reason)
            print(f"Successfully sent alert for transaction {transaction_id}")
        except Exception as e:
            # DynamoDB record already saved
            # don't retry the whole message
            print(f"Failed to send email alert: {e}")


def store_in_dynamodb(transaction_id: str, account_id: str, amount: float, reason: str, timestamp: str):

    #Write flagged transaction to DynamoDB for record keeping

    table = dynamodb.Table(DYNAMODB_TABLE)
    table.put_item(
        Item={
            "transaction_id": transaction_id,   
            "account_id": account_id,
            "amount": str(amount),              #cannot store float
            "reason": reason,
            "timestamp": timestamp,
            "flagged_at": datetime.now(timezone.utc).isoformat(),
            "status": "flagged"
        }
    )


def publish_fraud_metric():

    #Push a count of 1 to CloudWatch each time a transaction is flagged
    #Volume alarm sums this over 5-min window to catch a spike

    cloudwatch.put_metric_data(
        Namespace="FraudDetection",
        MetricData=[{
            "MetricName": "FlaggedTransactions",
            "Value": 1,
            "Unit": "Count",
        }]
    )


def send_email_alert(transaction_id: str, account_id: str, amount: float, reason: str):
    
    subject = f"(TEST) DEMO Fraud Alert: Suspicious Transaction Detected on Account {account_id}"
    body = f"""
    Demo Alert: A suspicious transaction has been flagged on your account.
    Transaction ID: {transaction_id}
    Account ID:     {account_id}
    Amount:         ${amount}
    Reason:         {reason}

    - Paige's Fraud Detection System
    """
    ses.send_email(
        Source=SENDER_EMAIL,
        Destination={"ToAddresses": [RECIPIENT_EMAIL]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": body}},
        },
    )