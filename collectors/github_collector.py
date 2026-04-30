"""GitHub collector — releases, tags, high-signal PRs."""

import logging
from datetime import datetime, timedelta, timezone

from collectors.base import BaseCollector
from collectors.release_context import extract_eip_context, extract_release_context
from config.loader import get_chains, get_sources, get_env

logger = logging.getLogger(__name__)

# PR titles matching these are noise — skip
NOISE_KEYWORDS = [
    "chore", "deps", "bump", "fix flaky", "test:", "ci:", "typo",
    "merge pull request", "update readme", "formatting", "lint",
    "codeowners", "workflow", "changelog", "version bump",
    "refactor", "style:", "perf:",
    # Routine code patterns (exact prefix matching in _check_high_signal_prs)
]

# Exact title prefixes that are routine PR noise (checked separately)
ROUTINE_PREFIXES = [
    "fix:", "fix(", "feat:", "feat(", "build:", "build(",
    "core/vm:", "core/eth:", "core/p2p:", "core/state:",
    "core/types:", "core/sync:",
    "backport ", "update release-drafter",
]

# PR titles/labels matching these are high-signal — EIP/fork/security/audit only
SIGNAL_KEYWORDS = [
    "eip", "bip", "simd", "fork", "audit", "breaking",
    "security", "hard fork", "soft fork", "consensus",
    "finality", "governance", "proposal", "mainnet",
]


class GitHubCollector(BaseCollector):
    """Monitors GitHub for releases, tags, and high-signal PRs.

    Tracks:
    - New releases/tags (version bumps)
    - High-signal PRs (EIPs, forks, security, audits, breaking changes)
    - New releases published within 48h

    Does NOT track:
    - Commit counts (meaningless without context)
    - Dependency bumps (noise)
    - Test/CI changes (not user-facing)
    """

    CATEGORY = "TECH_EVENT"

    def __init__(self, max_retries: int = 3, backoff_base: int = 2):
        super().__init__(name="GitHub", max_retries=max_retries, backoff_base=backoff_base)

        sources_cfg = get_sources()
        gh_cfg = sources_cfg.get("github", {})
        self.api_base = gh_cfg.get("api_base", "https://api.github.com")

        self._token = get_env("GITHUB_TOKEN", "")
        # Treat common placeholder values as empty
        if self._token in ("***", "", "None", "null"):
            self._token = ""
        # Fall back to gh CLI token if env var is empty
        if not self._token:
            try:
                import subprocess
                result = subprocess.run(
                    ["gh", "auth", "token"],
                    capture_output=True, text=True, timeout=5, check=False,
                )
                candidate = result.stdout.strip()
                if candidate and not candidate.startswith("no oauth"):
                    self._token = candidate
                    logger.info("[GitHub] Authenticated via gh CLI token")
            except Exception:
                pass
        if self._token:
            self.session.headers.update({
                "Authorization": f"token {self._token}",
                "Accept": "application/vnd.github+json",
            })
        else:
            logger.warning("[GitHub] No GITHUB_TOKEN set — using unauthenticated access (60 req/h)")

        self._chains_cfg = get_chains()

    def _make_signal(self, chain: str, description: str, reliability: float, evidence: dict) -> dict:
        return {
            "chain": chain,
            "category": self.CATEGORY,
            "description": description,
            "source": "GitHub",
            "reliability": min(max(reliability, 0.0), 1.0),
            "evidence": evidence,
        }

    def _check_new_releases(self, chain: str, repo: str) -> list[dict]:
        """Check for new releases or tags published within 48h."""
        signals = []

        # Try GitHub Releases first
        url = f"{self.api_base}/repos/{repo}/releases/latest"
        data = self.fetch_with_retry(url)
        if data and isinstance(data, dict):
            tag = data.get("tag_name", "")
            name = data.get("name", tag)
            published_at = data.get("published_at")
            html_url = data.get("html_url", "")
            prerelease = data.get("prerelease", False)

            if published_at:
                try:
                    pub_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    age_hours = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600
                    if age_hours <= 48:
                        release_type = "pre-release" if prerelease else "release"
                        desc = f"New {release_type}: {name or tag} ({repo})"
                        if age_hours < 1:
                            desc += f" — {int(age_hours * 60)}m ago"
                        else:
                            desc += f" — {age_hours:.1f}h ago"
                        signals.append(self._make_signal(
                            chain=chain,
                            description=desc,
                            reliability=0.95 if not prerelease else 0.8,
                            evidence={
                                "metric": "new_release",
                                "repo": repo,
                                "tag": tag,
                                "name": name,
                                "published_at": published_at,
                                "html_url": html_url,
                                "prerelease": prerelease,
                            },
                        ))
                except (ValueError, AttributeError):
                    pass

        # Also check tags for repos without GitHub Releases
        # Only report if GitHub Releases didn't already catch it
        if not signals:
            url = f"{self.api_base}/repos/{repo}/tags"
            data = self.fetch_with_retry(url, params={"per_page": 5})
            if data and isinstance(data, list) and len(data) >= 2:
                latest_tag = data[0]["name"]
                # Find the previous tag with a different major version
                prev_tag = None
                for t in data[1:]:
                    if t["name"] != latest_tag:
                        prev_tag = t["name"]
                        break
                if prev_tag and latest_tag != prev_tag:
                    # Only report MAJOR version changes
                    if self._is_major_release(latest_tag, prev_tag):
                        release_ctx = extract_release_context(latest_tag, prev_tag, repo)
                        signals.append(self._make_signal(
                            chain=chain,
                            description=f"Major release: {latest_tag} (was {prev_tag}) — {repo}",
                            reliability=0.9,
                            evidence={
                                "metric": "major_release",
                                "repo": repo,
                                "tag": latest_tag,
                                "prev_tag": prev_tag,
                                "release_context": release_ctx,
                            },
                        ))

        return signals

    def _is_major_release(self, tag: str, prev_tag: str) -> bool:
        """Check if this is a major version bump (not minor/patch)."""
        import re
        ver_match = re.search(r'v?(\d+)\.(\d+)', tag)
        prev_match = re.search(r'v?(\d+)\.(\d+)', prev_tag)
        if not ver_match or not prev_match:
            return False
        major, minor = int(ver_match.group(1)), int(ver_match.group(2))
        prev_major, prev_minor = int(prev_match.group(1)), int(prev_match.group(2))
        # Major version increase OR significant minor bump (0.x → 1.x pattern)
        if major > prev_major:
            return True
        # Also flag minor bumps for pre-1.0 projects (0.4 → 0.5 is significant)
        if major == 0 and prev_major == 0 and minor > prev_minor:
            return True
        return False

    def _check_high_signal_prs(self, chain: str, repo: str) -> list[dict]:
        """Find high-signal merged PRs (EIPs, forks, security, audits)."""
        signals = []

        url = f"{self.api_base}/repos/{repo}/pulls"
        params = {"state": "closed", "sort": "updated", "direction": "desc", "per_page": 30}
        data = self.fetch_with_retry(url, params=params)
        if not data or not isinstance(data, list):
            return signals

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)

        for pr in data:
            if not pr.get("merged_at"):
                continue
            try:
                merged_dt = datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
            if merged_dt < cutoff:
                continue

            title = pr.get("title", "")
            title_lower = title.lower()
            labels = [l["name"].lower() for l in pr.get("labels", [])]
            labels_str = " ".join(labels)

            # Skip noise (substring match)
            if any(n in title_lower for n in NOISE_KEYWORDS):
                continue

            # Skip routine PR prefixes (prefix match only — "fix:" not "fix migrations")
            if any(title_lower.startswith(p) for p in ROUTINE_PREFIXES):
                continue

            # Check for signal
            is_signal = False
            signal_type = "feature"
            for kw in SIGNAL_KEYWORDS:
                if kw in title_lower or kw in labels_str:
                    is_signal = True
                    if "security" in kw or "audit" in kw:
                        signal_type = "security"
                    elif "fork" in kw or "eip" in kw or "bip" in kw:
                        signal_type = "upgrade"
                    elif "breaking" in kw:
                        signal_type = "breaking"
                    break

            if not is_signal:
                continue

            # Fetch EIP context for upgrade PRs
            eip_context = ""
            if signal_type in ("upgrade", "breaking"):
                eip_context = extract_eip_context(title, repo)

            signals.append(self._make_signal(
                chain=chain,
                description=f"{title[:80]} ({repo})",
                reliability=0.8,
                evidence={
                    "metric": "high_signal_pr",
                    "repo": repo,
                    "pr_title": title,
                    "pr_url": pr.get("html_url", ""),
                    "signal_type": signal_type,
                    "labels": labels,
                    "merged_at": pr["merged_at"][:10],
                    "eip_context": eip_context,
                },
            ))

        return signals[:2]  # max 2 high-signal PRs per repo

    def collect(self) -> list[dict]:
        """Collect GitHub signals for all chains with github_repos configured."""
        signals = []

        for chain_name, chain_cfg in self._chains_cfg.items():
            repos = chain_cfg.get("github_repos")
            if not repos or not isinstance(repos, list):
                continue

            for repo in repos:
                if not repo or not isinstance(repo, str):
                    continue

                # Check for new releases/tags
                signals.extend(self._check_new_releases(chain_name, repo))

                # Check for high-signal PRs
                signals.extend(self._check_high_signal_prs(chain_name, repo))

        logger.info(f"[GitHub] Collected {len(signals)} signals")
        return signals
