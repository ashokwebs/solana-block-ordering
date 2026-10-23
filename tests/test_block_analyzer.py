"""Unit tests for block analyzer and transaction parsing."""

import pytest
from solana_auditor.block_analyzer import parse_block, JITO_TIP_ACCOUNTS


def test_parse_block_and_locks():
    """Test parsing transactions, write locks, and priority fee derivation."""
    mock_raw_block = {
        "blockTime": 1792745000,
        "rewards": [{"pubkey": "TestLeader1111111111111111111111111111111111", "rewardType": "Fee"}],
        "transactions": [
            {
                "meta": {
                    "fee": 5000,
                    "computeUnitsConsumed": 10000,
                    "err": None
                },
                "transaction": {
                    "signatures": ["5sig111111111111111111111111111111111111111111111111111111111111111111111111111111111111"],
                    "message": {
                        "header": {
                            "numRequiredSignatures": 1,
                            "numReadonlySignedAccounts": 0,
                            "numReadonlyUnsignedAccounts": 1
                        },
                        "accountKeys": [
                            "AccountPayer1111111111111111111111111111111",
                            "WritableTarget11111111111111111111111111111",
                            "ReadonlyProgram1111111111111111111111111111"
                        ],
                        "instructions": []
                    }
                }
            },
            {
                "meta": {
                    "fee": 105000,
                    "computeUnitsConsumed": 20000,
                    "err": None
                },
                "transaction": {
                    "signatures": ["5sig222222222222222222222222222222222222222222222222222222222222222222222222222222222222"],
                    "message": {
                        "header": {
                            "numRequiredSignatures": 1,
                            "numReadonlySignedAccounts": 0,
                            "numReadonlyUnsignedAccounts": 0
                        },
                        "accountKeys": [
                            "AccountPayer2222222222222222222222222222222",
                            list(JITO_TIP_ACCOUNTS)[0]
                        ],
                        "instructions": []
                    }
                }
            }
        ]
    }

    parsed = parse_block(mock_raw_block, slot=123456)
    assert parsed.slot == 123456
    assert parsed.leader_pubkey == "TestLeader1111111111111111111111111111111111"
    assert parsed.total_transactions == 2
    assert parsed.non_vote_transactions == 2

    tx0 = parsed.transactions[0]
    assert tx0.fee_lamports == 5000
    assert tx0.effective_fee_per_cu == 0.0
    assert "AccountPayer1111111111111111111111111111111" in tx0.write_locks
    assert "WritableTarget11111111111111111111111111111" in tx0.write_locks
    assert "ReadonlyProgram1111111111111111111111111111" not in tx0.write_locks
    assert tx0.is_jito_tip is False

    tx1 = parsed.transactions[1]
    assert tx1.fee_lamports == 105000
    assert tx1.effective_fee_per_cu > 0.0
    assert tx1.is_jito_tip is True
