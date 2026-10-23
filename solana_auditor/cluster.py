"""Cluster discovery and validator client categorization."""

from typing import Dict, List, Any
from .client import SolanaRpcClient


class ValidatorFamily:
    AGAVE = "Agave / Solana Labs"
    JITO = "Jito-Solana"
    FIREDANCER = "Firedancer / Frankendancer"
    UNKNOWN = "Unknown / Other"


def classify_client_version(version: str) -> str:
    """Classify node client version into major client family."""
    if not version:
        return ValidatorFamily.UNKNOWN
    v = version.strip()
    if v.startswith("26."):
        return ValidatorFamily.FIREDANCER
    if v.startswith("4."):
        return ValidatorFamily.JITO
    if v.startswith("1.") or v.startswith("2."):
        return ValidatorFamily.AGAVE
    return ValidatorFamily.UNKNOWN


class ClusterDiscovery:
    """Discovers and filters validators by client software family."""

    def __init__(self, client: SolanaRpcClient):
        self.client = client

    def discover_validators_by_client(self) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch all cluster nodes, cross-reference with vote accounts, and bucket by clientId."""
        raw_votes = self.client.call("getVoteAccounts")
        current_votes = {v["nodePubkey"]: v for v in raw_votes.get("current", [])}

        nodes = self.client.get_cluster_nodes()
        categorized: Dict[str, List[Dict[str, Any]]] = {
            ValidatorFamily.AGAVE: [],
            ValidatorFamily.JITO: [],
            ValidatorFamily.FIREDANCER: [],
            ValidatorFamily.UNKNOWN: []
        }

        for node in nodes:
            pubkey = node.get("pubkey")
            if not pubkey or pubkey not in current_votes:
                continue

            vote_entry = current_votes[pubkey]
            node["activated_stake"] = vote_entry.get("activatedStake", 0)

            cid = node.get("clientId", "")
            ver = node.get("version", "")

            if "Firedancer" in cid or "Frankendancer" in cid or ver.startswith("26."):
                categorized[ValidatorFamily.FIREDANCER].append(node)
            elif "Jito" in cid:
                categorized[ValidatorFamily.JITO].append(node)
            elif "Agave" in cid:
                categorized[ValidatorFamily.AGAVE].append(node)
            else:
                categorized[ValidatorFamily.UNKNOWN].append(node)

        # Sort each family by stake descending
        for fam in categorized:
            categorized[fam].sort(key=lambda x: x.get("activated_stake", 0), reverse=True)

        return categorized

    def get_validator_leader_slots(self, validator_pubkey: str) -> List[int]:
        """Get absolute slot numbers where the given validator was leader in the current epoch."""
        epoch_info = self.client.get_epoch_info()
        absolute_slot = epoch_info["absoluteSlot"]
        slot_index = epoch_info["slotIndex"]
        epoch_start_slot = absolute_slot - slot_index

        schedule = self.client.get_leader_schedule(identity=validator_pubkey)
        if not schedule or validator_pubkey not in schedule:
            return []

        relative_slots = schedule[validator_pubkey]
        absolute_slots = [epoch_start_slot + rel for rel in relative_slots]

        # Return slots that have already passed (past blocks)
        past_slots = [s for s in absolute_slots if s < absolute_slot]
        past_slots.sort(reverse=True)
        return past_slots
