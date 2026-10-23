"""Solana JSON-RPC client with retry and rate-limiting."""

import time
import json
import requests
from typing import Any, Dict, List, Optional


class SolanaRpcClient:
    """Robust Solana JSON-RPC client."""

    DEFAULT_RPC = "https://api.mainnet-beta.solana.com"

    def __init__(self, rpc_url: Optional[str] = None, timeout: int = 15, max_retries: int = 4):
        self.rpc_url = rpc_url or self.DEFAULT_RPC
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.request_id = 1

    def call(self, method: str, params: Optional[List[Any]] = None) -> Any:
        """Call a Solana JSON-RPC method with exponential backoff on rate limits."""
        payload = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or []
        }
        self.request_id += 1

        delay = 1.0
        for attempt in range(self.max_retries):
            try:
                response = self.session.post(
                    self.rpc_url,
                    json=payload,
                    timeout=self.timeout,
                    headers={"Content-Type": "application/json", "User-Agent": "SolanaBlockOrderAuditor/1.0"}
                )
                if response.status_code == 429:
                    time.sleep(delay)
                    delay *= 2.0
                    continue

                response.raise_for_status()
                data = response.json()
                if "error" in data:
                    err = data["error"]
                    # If rate limit code -32005
                    if isinstance(err, dict) and err.get("code") in (-32005, 429):
                        time.sleep(delay)
                        delay *= 2.0
                        continue
                    raise RuntimeError(f"Solana RPC Error ({method}): {err}")

                return data.get("result")

            except (requests.RequestException, json.JSONDecodeError) as e:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"Solana RPC request failed after {self.max_retries} attempts: {e}")
                time.sleep(delay)
                delay *= 2.0

        raise RuntimeError(f"Solana RPC call timed out / exhausted retries for {method}")

    def get_slot(self) -> int:
        return self.call("getSlot")

    def get_epoch_info(self) -> Dict[str, Any]:
        return self.call("getEpochInfo")

    def get_cluster_nodes(self) -> List[Dict[str, Any]]:
        return self.call("getClusterNodes")

    def get_leader_schedule(self, slot: Optional[int] = None, identity: Optional[str] = None) -> Dict[str, List[int]]:
        params: List[Any] = [slot]
        if identity:
            params.append({"identity": identity})
        return self.call("getLeaderSchedule", params)

    def get_block(self, slot: int, transaction_details: str = "full") -> Optional[Dict[str, Any]]:
        """Fetch block with supported transaction version 1."""
        config = {
            "encoding": "json",
            "maxSupportedTransactionVersion": 1,
            "transactionDetails": transaction_details,
            "rewards": True
        }
        try:
            return self.call("getBlock", [slot, config])
        except RuntimeError as e:
            if "was skipped" in str(e).lower() or "-32007" in str(e) or "-32009" in str(e):
                return None
            raise
