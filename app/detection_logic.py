
from app.models import Transaction, TransactionType
from datetime import datetime, timezone

# Thresholds 
LARGE_WITHDRAWAL_THRESHOLD = 10000.00
MAX_FAILED_LOGINS = 3 
GEO_VELOCITY_MINUTES = 30

# For now store "last transaction" — in production this would be a database
# Use in-memory dictionary keyed by account_id
recent_transactions: dict = {}

def check_large_withdrawal(transaction: Transaction) -> tuple[bool, str]:

    #Flag any withdrawal over $10,000
    
    if (
        transaction.transaction_type == TransactionType.WITHDRAWAL
        and transaction.amount > LARGE_WITHDRAWAL_THRESHOLD
    ):
        return True, f"Withdrawal of ${transaction.amount} exceeds threshold of ${LARGE_WITHDRAWAL_THRESHOLD}"
    return False, ""


def check_geo_velocity(transaction: Transaction) -> tuple[bool, str]:
    # Flag if same account transacts from a different location within 30 minutes of their last transaction.
    # This checks for stolen card usage across regions.
    
    account_id = transaction.account_id

    if account_id not in recent_transactions:
        # No history for this account, can't flag, store and move on
        return False, ""

    last = recent_transactions[account_id]
    last_location = last["location"]
    last_time = last["timestamp"]

    # Make both timestamps timezone-aware for safe comparison
    current_time = transaction.timestamp
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    if last_time.tzinfo is None:
        last_time = last_time.replace(tzinfo=timezone.utc)

    minutes_apart = abs((current_time - last_time).total_seconds() / 60)

    if last_location != transaction.location and minutes_apart < GEO_VELOCITY_MINUTES:
        return True, (
            f"Transaction from '{transaction.location}' only {minutes_apart:.1f} mins "
            f"after transaction from '{last_location}'"
        )
    return False, ""


def check_failed_logins(transaction: Transaction) -> tuple[bool, str]:
    failed_attempts = transaction.failed_login_attempts or 0
    if failed_attempts > MAX_FAILED_LOGINS:
        return True, f"{failed_attempts} failed login attempts before transaction"
    return False, ""

def evaluate_transaction(transaction: Transaction) -> tuple[str, str]:
    #Whichever rule fires first flags the transaction.
    #store this transaction as the latest for the account.
    
    rules = [
        check_large_withdrawal,
        check_geo_velocity,
        check_failed_logins,
    ]

    for rule in rules:
        flagged, reason = rule(transaction)
        if flagged:
            # Update recent transaction history before returning
            _store_recent(transaction)
            return "flagged", reason

    
    _store_recent(transaction)
    return "approved", ""


def _store_recent(transaction: Transaction):
    #Store the latest transaction per account 

    # Prefixed with _ to signal this is an internal helper, not called from outside.
    
    recent_transactions[transaction.account_id] = {
        "location": transaction.location,
        "timestamp": transaction.timestamp,
    }