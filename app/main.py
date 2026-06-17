
import uuid
from fastapi import FastAPI, HTTPException
from datetime import datetime, timezone
from app.models import Transaction, TransactionResponse
from app.detection_logic import evaluate_transaction
from app.sqs_client import push_flagged_transaction

app = FastAPI(
    title="Fraud Detection API",
    description="Banking transaction fraud detection system",
    version="1.0.0"
)

@app.get("/health")
def health_check():
    
    
    #Pings this constantly to confirm the service is alive. 
    # If this returns anything other than 200, ECS will restart the container.
    
    return {"status": "healthy"}


@app.post("/transaction", response_model=TransactionResponse)
def process_transaction(transaction: Transaction):
    #Receives a transaction, evaluates it for fraud, returns an approval or flag decision.
    

    
    transaction_id = str(uuid.uuid4())

    # Run all fraud rules against the transaction
    # Returns either "approved" or "flagged" (with reason)
    status, reason = evaluate_transaction(transaction)

    
    if status == "flagged":
        # push to SQS for Lambda to pick up
        try:
            push_flagged_transaction(
                transaction_id=transaction_id,
                account_id=transaction.account_id,
                amount=transaction.amount,
                reason=reason,
                timestamp=transaction.timestamp,
            )
        except Exception as e:
            # Print for now
            # In production, log this to CloudWatch
            print(f"Warning: Failed to push to SQS: {e}")

    return TransactionResponse(
        transaction_id=transaction_id,
        account_id=transaction.account_id,
        amount=transaction.amount,
        status=status,
        reason=reason if reason else None,
        timestamp=transaction.timestamp,
    )