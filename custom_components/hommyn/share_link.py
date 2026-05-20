"""Parse Hommyn `rusklimat://device-share/...` URLs.

The Hommyn app's "Share device" button produces a deep link like:

    rusklimat://device-share/rusclimate/13/206ef16d0558
        ?token=aa5c45a91f0afd9b7bfcca0da44cad0e
        &name=Ballu%20Ice%20Peak
        &attributes_model=ballu_ice_peak_dc

The path encodes vendor / devtype / MAC; the query string carries the
32-hex MQTT clientId (`token`) plus optional display metadata. That's all
we need to start mirroring the device — no cloud login required.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


class ShareLinkError(ValueError):
    """Raised when a share link cannot be parsed."""


@dataclass(frozen=True, slots=True)
class ShareLink:
    """Parsed contents of a rusklimat:// share link."""

    vendor: str            # always "rusclimate" in practice
    device_type: int       # 13 for Ballu Ice Peak, 46 ventilation, 69 breezer, ...
    mac: str               # 12-hex lowercase (no separators), e.g. "206ef16d0558"
    token: str             # 32-hex clientId on the broker
    name: str | None       # display name from the app, may be None
    model: str | None      # attributes_model attribute, may be None

    @property
    def topic_prefix(self) -> str:
        """`rusclimate/{type}/{token}` — base prefix for state/control topics."""
        return f"{self.vendor}/{self.device_type}/{self.token}"

    @property
    def unique_id(self) -> str:
        """Stable identifier for the Home Assistant entity/device registry."""
        return f"{self.vendor}_{self.device_type}_{self.mac}"


_HEX12 = re.compile(r"^[0-9a-fA-F]{12}$")
_HEX32 = re.compile(r"^[0-9a-fA-F]{32}$")


def parse_share_link(raw: str) -> ShareLink:
    """Parse a `rusklimat://device-share/...` URL.

    Raises:
        ShareLinkError: if the URL is malformed or required fields are missing.
    """
    raw = raw.strip()
    if not raw:
        raise ShareLinkError("empty link")

    parsed = urlparse(raw)
    if parsed.scheme != "rusklimat":
        raise ShareLinkError(f"unexpected scheme {parsed.scheme!r}, want 'rusklimat'")

    # urlparse puts "device-share" in .netloc because of how custom schemes
    # collapse "rusklimat://device-share/foo" → netloc=device-share, path=/foo.
    if parsed.netloc != "device-share":
        raise ShareLinkError(f"unexpected host {parsed.netloc!r}, want 'device-share'")

    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) != 3:
        raise ShareLinkError(
            f"path must be vendor/devtype/mac, got {parsed.path!r}"
        )
    vendor, devtype_raw, mac = segments

    try:
        devtype = int(devtype_raw)
    except ValueError as exc:
        raise ShareLinkError(f"devtype must be integer, got {devtype_raw!r}") from exc

    mac = mac.lower()
    if not _HEX12.match(mac):
        raise ShareLinkError(f"mac must be 12 hex chars, got {mac!r}")

    query = parse_qs(parsed.query, keep_blank_values=False)
    token_list = query.get("token", [])
    if not token_list:
        raise ShareLinkError("missing `token` in query string")
    token = token_list[0].lower()
    if not _HEX32.match(token):
        raise ShareLinkError(f"token must be 32 hex chars, got {token!r}")

    name = (query.get("name") or [None])[0]
    if name:
        # The app URL-encodes "/" as %2F and pads display name with leading
        # whitespace ("Electrolux Smartline/ Ballu Eco Smart/ Ice Peak").
        name = name.replace("/ ", " / ").strip()

    model = (query.get("attributes_model") or [None])[0]

    return ShareLink(
        vendor=vendor,
        device_type=devtype,
        mac=mac,
        token=token,
        name=name,
        model=model,
    )
