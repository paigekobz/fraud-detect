from datetime import datetime, timedelta, timezone

from app.models import Transaction, TransactionType
from app.detection_logic import (
    check_large_withdrawal,
    check_geo_velocity,
    check_failed_logins,
    evaluate_transaction,
    recent_transactions,
)


def make_transaction(
    account_id="ACC123",
    amount=100,
    transaction_type=TransactionType.WITHDRAWAL,
    location="Vancouver",
    timestamp=None,
    failed_login_attempts=0,
):
    return Transaction(
        account_id=account_id,
        amount=amount,
        transaction_type=transaction_type,
        location=location,
        timestamp=timestamp or datetime.now(timezone.utc),
        failed_login_attempts=failed_login_attempts,
    )


def setup_function():
    recent_transactions.clear()


def test_large_withdrawal_is_flagged():
    transaction = make_transaction(amount=15000)

    flagged, reason = check_large_withdrawal(transaction)

    assert flagged
    assert "exceeds threshold" in reason


def test_large_deposit_is_not_flagged():
    transaction = make_transaction(
        amount=15000,
        transaction_type=TransactionType.DEPOSIT,
    )

    flagged, reason = check_large_withdrawal(transaction)

    assert flagged is False
    assert reason == ""


def test_failed_login_rule_flags_transaction():
    transaction = make_transaction(failed_login_attempts=5)

    flagged, reason = check_failed_logins(transaction)

    assert flagged
    assert "failed login" in reason


def test_geo_velocity_flags_different_locations():
    now = datetime.now(timezone.utc)

    first = make_transaction(
        location="Vancouver",
        timestamp=now,
    )

    evaluate_transaction(first)

    second = make_transaction(
        location="Toronto",
        timestamp=now + timedelta(minutes=10),
    )

    flagged, reason = check_geo_velocity(second)

    assert flagged
    assert "Transaction from" in reason


def test_transaction_is_approved_when_no_rules_fire():
    transaction = make_transaction(
        amount=500,
        transaction_type=TransactionType.DEPOSIT,
        failed_login_attempts=0,
    )

    status, reason = evaluate_transaction(transaction)

    assert status == "approved"
    assert reason == ""

def test_first_matching_rule_is_returned():
    transaction = make_transaction(
        amount=15000,
        failed_login_attempts=10,
    )

    status, reason = evaluate_transaction(transaction)

    assert status == "flagged"
    assert "exceeds threshold" in reason