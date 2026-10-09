from decimal import Decimal
import pytest
from app.financials import post_balanced_transaction

def test_ledger_rejects_imbalance():
    with pytest.raises(ValueError):
        post_balanced_transaction("x","USD",[{"account_id":"a","debit":Decimal("10.00")},{"account_id":"b","credit":Decimal("9.99")}])

def test_ledger_balances_exact_decimal():
    result=post_balanced_transaction("x2","USD",[{"account_id":"a","debit":Decimal("10.10")},{"account_id":"b","credit":Decimal("10.10")}])
    assert result["balanced"] is True
    assert result["debits"]=="10.10"
