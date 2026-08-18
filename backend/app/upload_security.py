from __future__ import annotations

import ipaddress
import re
import os
import socket
from urllib.parse import urlparse

from fastapi import HTTPException


# --- Magic bytes signatures for file type verification ---

MAGIC_BYTES: dict[str, list[bytes]] = {
    "application/pdf": [b"%PDF"],
    "text/csv": [],
    "text/plain": [],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [
        b"PK\x03\x04",
    ],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
        b"PK\x03\x04",
    ],
}

# --- Allowed MIME types per endpoint ---

GENERATE_ALLOWED_MIMES: set[str] = {"application/pdf"}

INVESTIGATE_ALLOWED_MIMES: set[str] = {
    "application/pdf",
    "text/csv",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# --- Blocked hosts for SSRF prevention ---

BLOCKED_HOSTS: set[str] = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "[::1]",
    "metadata.google.internal",
}


def validate_upload(
    file_bytes: bytes,
    filename: str,
    claimed_mime: str,
    allowed_mimes: set[str],
    max_bytes: int,
) -> tuple[bytes, str]:
    """Validate an uploaded file for size, type, magic bytes, and filename safety.

    Returns (safe_bytes, sanitized_filename) or raises HTTPException.
    """
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=413, detail="File exceeds maximum allowed size."
        )

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="File is empty.")

    if claimed_mime not in allowed_mimes:
        raise HTTPException(status_code=400, detail="File type not accepted.")

    validate_magic_bytes(file_bytes, claimed_mime)

    safe_name = sanitize_filename(filename)
    return file_bytes, safe_name


def validate_magic_bytes(file_bytes: bytes, claimed_mime: str) -> None:
    """Check that file content matches declared MIME type via magic bytes.

    Skips validation for types with no defined signatures (text/plain, text/csv).
    """
    signatures = MAGIC_BYTES.get(claimed_mime)
    if signatures is None:
        return
    if not signatures:
        return
    if not any(file_bytes.startswith(sig) for sig in signatures):
        raise HTTPException(
            status_code=400, detail="File content does not match declared type."
        )


def sanitize_filename(filename: str) -> str:
    """Remove path traversal, null bytes, and dangerous patterns from filename."""
    # Strip null bytes
    filename = filename.replace("\x00", "")

    # Strip path separators
    filename = filename.replace("/", "").replace("\\", "")

    # Take only the basename (handles any remaining path components)
    filename = os.path.basename(filename)

    # Remove leading dots (hidden files) and spaces
    filename = filename.lstrip(". ")

    # Only allow safe characters: alphanumeric, dots, hyphens, underscores
    filename = re.sub(r"[^\w.\-]", "_", filename)

    # Ensure non-empty
    if not filename:
        filename = "upload"

    # Truncate to 200 chars preserving extension
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        max_name_len = 200 - len(ext)
        if max_name_len > 0:
            filename = name[:max_name_len] + ext
        else:
            filename = name[:200]

    return filename


def validate_url_input(url: str) -> str:
    """Validate user-supplied URL to prevent SSRF attacks.

    Returns the cleaned URL or raises HTTPException with 400.
    """
    url = url.strip()

    if not url:
        raise HTTPException(status_code=400, detail="URL must not be empty.")

    # Length limit
    if len(url) > 2048:
        raise HTTPException(status_code=400, detail="URL exceeds maximum length.")

    parsed = urlparse(url)

    # Scheme validation
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400, detail="Only HTTP and HTTPS URLs are accepted."
        )

    # Embedded credentials check (userinfo component)
    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="URL not allowed.")

    # Host validation
    hostname = parsed.hostname or ""
    if not hostname:
        raise HTTPException(status_code=400, detail="URL must have a valid hostname.")

    # Block known internal/metadata hosts
    if hostname.lower() in BLOCKED_HOSTS:
        raise HTTPException(status_code=400, detail="URL not allowed.")

    # Port restriction (only 80 and 443 allowed)
    port = parsed.port
    if port is not None and port not in (80, 443):
        raise HTTPException(status_code=400, detail="URL not allowed.")

    # Check if hostname is a literal IP address
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
            raise HTTPException(status_code=400, detail="URL not allowed.")
    except ValueError:
        # Not an IP literal — it's a domain name, resolve via DNS
        pass

    # DNS resolution with 5s timeout to catch domains resolving to private IPs
    try:
        original_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(5.0)
        try:
            addr_infos = socket.getaddrinfo(hostname, None)
        finally:
            socket.setdefaulttimeout(original_timeout)
    except (socket.gaierror, socket.timeout, OSError):
        raise HTTPException(status_code=400, detail="URL not allowed.")

    for addr_info in addr_infos:
        resolved_ip_str = addr_info[4][0]
        try:
            resolved_ip = ipaddress.ip_address(resolved_ip_str)
            if (
                resolved_ip.is_private
                or resolved_ip.is_loopback
                or resolved_ip.is_reserved
                or resolved_ip.is_link_local
            ):
                raise HTTPException(status_code=400, detail="URL not allowed.")
        except ValueError:
            continue

    return url
