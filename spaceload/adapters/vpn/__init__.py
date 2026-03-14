"""VPN adapters for ctx."""

from spaceload.adapters.vpn.base import VPNAdapter, VPNState, retry_connect
from spaceload.adapters.vpn.registry import VPNAdapterRegistry

__all__ = ["VPNAdapter", "VPNState", "retry_connect", "VPNAdapterRegistry"]
