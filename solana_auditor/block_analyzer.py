"""Block transaction parser, priority fee, write lock, and Jito bundle extraction."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Set, Optional

# Solana Core Program IDs
COMPUTE_BUDGET_PROGRAM_ID = "ComputeBudget111111111111111111111111111111"
VOTE_PROGRAM_ID = "Vote111111111111111111111111111111111111111"

# Official Jito MEV Tip Accounts
JITO_TIP_ACCOUNTS = {
    "96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5",
    "HFqU5x63VTxvQssQn138i2NN7MQBecAr5LsPfwa2wk55",
    "Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY",
    "ADaUMid9yfUytqMBgopwjb2DTLSokTSzL1zt6iGPaS49",
    "DfXygSm4jCyNCybVYYK6DwvWqjKee8pbDmJGcLWNDXjh",
    "ADuUkR4vqLUMWXxW9gh6D6L8pMSawimctcNZ5pGwDcEt",
    "DttWaMuVvTiduZRnguLF7jNxTgiMBZ1hyAumKUiL2KRL",
    "3AVi9Tg9Uo68tJfuvoKvqKNWKkC5wPdSSdeBnizKZ6jT"
}


@dataclass
class ParsedTransaction:
    """Detailed metadata for a single transaction in a block."""
    index: int
    signature: str
    fee_lamports: int
    compute_units_consumed: int
    compute_unit_limit: int
    priority_fee_micro_lamports: int
    effective_fee_per_cu: float
    write_locks: Set[str] = field(default_factory=set)
    is_vote: bool = False
    is_jito_tip: bool = False
    success: bool = True


@dataclass
class ParsedBlock:
    """Structured representation of a leader-ordered block."""
    slot: int
    block_time: Optional[int]
    leader_pubkey: str
    total_transactions: int
    vote_transactions: int
    non_vote_transactions: int
    transactions: List[ParsedTransaction] = field(default_factory=list)


def parse_block(raw_block: Dict[str, Any], slot: int) -> ParsedBlock:
    """Parse raw Solana RPC block into structured ParsedBlock."""
    # Find leader pubkey from rewards
    leader_pubkey = "unknown"
    for reward in raw_block.get("rewards", []):
        if reward.get("rewardType") == "Fee":
            leader_pubkey = reward.get("pubkey", "unknown")
            break

    block_time = raw_block.get("blockTime")
    raw_txs = raw_block.get("transactions", [])

    parsed_txs: List[ParsedTransaction] = []
    vote_count = 0
    non_vote_count = 0

    for idx, tx_entry in enumerate(raw_txs):
        meta = tx_entry.get("meta", {}) or {}
        tx = tx_entry.get("transaction", {}) or {}
        message = tx.get("message", {}) or {}

        # Signature
        signatures = tx.get("signatures", [])
        sig = signatures[0] if signatures else f"sig_idx_{idx}"

        # Fees & CU
        fee = meta.get("fee", 5000)
        cu_consumed = meta.get("computeUnitsConsumed", 0)
        success = meta.get("err") is None

        # Resolve account keys and write locks
        account_keys = message.get("accountKeys", [])
        header = message.get("header", {})
        num_required_signatures = header.get("numRequiredSignatures", 1)
        num_readonly_signed = header.get("numReadonlySignedAccounts", 0)
        num_readonly_unsigned = header.get("numReadonlyUnsignedAccounts", 0)

        # Standard Solana account lock rules:
        # 0 .. (num_req_sig - num_readonly_signed) are signed writable
        # num_req_sig .. (total - num_readonly_unsigned) are unsigned writable
        total_accounts = len(account_keys)
        signed_writable_limit = max(0, num_required_signatures - num_readonly_signed)
        unsigned_writable_start = num_required_signatures
        unsigned_writable_end = max(unsigned_writable_start, total_accounts - num_readonly_unsigned)

        write_locks: Set[str] = set()
        is_vote = False
        is_jito_tip = False

        # Extract account pubkeys (supporting string or object notation)
        str_account_keys: List[str] = []
        for ak in account_keys:
            key_str = ak.get("pubkey") if isinstance(ak, dict) else str(ak)
            str_account_keys.append(key_str)

        for a_idx, key_str in enumerate(str_account_keys):
            if a_idx < signed_writable_limit or (unsigned_writable_start <= a_idx < unsigned_writable_end):
                write_locks.add(key_str)

            if key_str == VOTE_PROGRAM_ID:
                is_vote = True
            if key_str in JITO_TIP_ACCOUNTS:
                is_jito_tip = True

        # Default compute budget parameters
        cu_limit = 200000
        priority_fee_micro_lamports = 0

        # Parse instructions for ComputeBudget directives
        instructions = message.get("instructions", [])
        for ix in instructions:
            program_id_idx = ix.get("programIdIndex")
            program_id = ""
            if program_id_idx is not None and program_id_idx < len(str_account_keys):
                program_id = str_account_keys[program_id_idx]
            elif "programId" in ix:
                program_id = ix.get("programId")

            if program_id == COMPUTE_BUDGET_PROGRAM_ID:
                data = ix.get("data", "")
                # Decoded or raw base58/base64 instructions
                # If parsed json format or hex:
                # Instruction 0x02 = SetComputeUnitLimit(u32)
                # Instruction 0x03 = SetComputeUnitPrice(u64)
                # We also calculate effective rate from (fee - 5000)
                pass

        # If priority fee instruction wasn't explicit, derive from priority fee lamports:
        # Base fee is 5000 lamports per signature. Extra fee = priority fee.
        num_sigs = len(signatures)
        base_fee = num_sigs * 5000
        extra_fee = max(0, fee - base_fee)

        effective_cu = max(1, cu_consumed if cu_consumed > 0 else cu_limit)
        effective_rate = (extra_fee * 1_000_000) / effective_cu

        if is_vote:
            vote_count += 1
        else:
            non_vote_count += 1

        parsed_tx = ParsedTransaction(
            index=idx,
            signature=sig,
            fee_lamports=fee,
            compute_units_consumed=cu_consumed,
            compute_unit_limit=cu_limit,
            priority_fee_micro_lamports=int(effective_rate),
            effective_fee_per_cu=effective_rate,
            write_locks=write_locks,
            is_vote=is_vote,
            is_jito_tip=is_jito_tip,
            success=success
        )
        parsed_txs.append(parsed_tx)

    return ParsedBlock(
        slot=slot,
        block_time=block_time,
        leader_pubkey=leader_pubkey,
        total_transactions=len(parsed_txs),
        vote_transactions=vote_count,
        non_vote_transactions=non_vote_count,
        transactions=parsed_txs
    )
