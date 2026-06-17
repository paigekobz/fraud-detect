
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class TransactionType(Enum):
    WITHDRAWAL = "withdrawal"
    DEPOSIT = "deposit"
    TRANSFER = "transfer"

class Transaction(BaseModel):
    account_id: str
    amount: float
    transaction_type: TransactionType
    location: str
    timestamp: datetime
    failed_login_attempts: Optional[int] = 0

class TransactionResponse(BaseModel):
    transaction_id: str
    account_id: str
    amount: float
    reason: Optional[str] = None
    timestamp: datetime
    status: str  # will be either "approved" or "flagged"