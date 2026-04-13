"""Release context fetcher — fetches EIP descriptions and release notes."""

import logging
import re
import requests

logger = logging.getLogger(__name__)

# EIP description cache (fetched once per run)
_eip_cache: dict[str, str] = {}


def fetch_eip_description(eip_number: str) -> str:
    """Fetch EIP title and summary from eips.ethereum.org."""
    if eip_number in _eip_cache:
        return _eip_cache[eip_number]

    try:
        # GitHub raw EIP file
        url = f"https://raw.githubusercontent.com/ethereum/EIPs/master/EIPS/eip-{eip_number}.md"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            # Try with zero-padded
            url = f"https://raw.githubusercontent.com/ethereum/EIPs/master/EIPS/eip-{int(eip_number):04d}.md"
            resp = requests.get(url, timeout=10)

        if resp.status_code == 200:
            content = resp.text
            # Extract title
            title_match = re.search(r'^title:\s*(.+)$', content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else ""

            # Extract abstract (first paragraph after "## Abstract")
            abstract_match = re.search(
                r'## Abstract\s*\n\s*\n(.*?)(?:\n\s*\n|\n##)', content, re.DOTALL
            )
            abstract = ""
            if abstract_match:
                abstract = abstract_match.group(1).strip()
                # Clean up markdown
                abstract = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', abstract)  # remove links
                abstract = abstract.replace('\n', ' ').strip()
                if len(abstract) > 200:
                    abstract = abstract[:197] + "..."

            result = f"{title}. {abstract}" if title else ""
            _eip_cache[eip_number] = result
            return result
    except Exception as e:
        logger.debug(f"Failed to fetch EIP-{eip_number}: {e}")

    _eip_cache[eip_number] = ""
    return ""


def extract_eip_context(pr_title: str, repo: str) -> str:
    """Extract EIP numbers from PR title and fetch their descriptions."""
    # Match EIP-XXXX, BIP-XXXX, SIMD-XXXX patterns
    eip_matches = re.findall(r'(?:EIP|eip|BIP|bip|SIMD|simd)[- ](\d+)', pr_title)

    contexts = []
    for eip_num in eip_matches[:2]:  # max 2 EIPs per PR
        desc = fetch_eip_description(eip_num)
        if desc:
            contexts.append(f"EIP-{eip_num}: {desc}")

    return "; ".join(contexts)


def extract_release_context(tag: str, prev_tag: str, repo: str) -> str:
    """Generate a human-readable description of what changed between tags."""
    # Extract version numbers
    version_match = re.search(r'v?(\d+\.\d+\.?\d*)', tag)
    prev_match = re.search(r'v?(\d+\.\d+\.?\d*)', prev_tag)

    if not version_match or not prev_match:
        return ""

    ver = version_match.group(1)
    prev = prev_match.group(1)

    # Major version bump
    major = int(ver.split('.')[0])
    prev_major = int(prev.split('.')[0])
    if major > prev_major:
        return f"Major version upgrade ({prev} → {ver}). Breaking changes likely."

    # Minor version bump
    minor = int(ver.split('.')[1]) if len(ver.split('.')) > 1 else 0
    prev_minor = int(prev.split('.')[1]) if len(prev.split('.')) > 1 else 0
    if minor > prev_minor:
        return f"Minor release ({prev} → {ver}). New features."

    # Patch
    return f"Patch release ({prev} → {ver}). Bug fixes."
