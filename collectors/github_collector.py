"""GitHub collector — releases, commit activity signals."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from collectors.base import BaseCollector
from config.loader import get_chains, get_baselines, get_sources, get_env

logger = logging.getLogger(__name__)


class GitHubCollector(BaseCollector):
    """Monitors GitHub repos for releases and commit activity.

    Detects:
    - New releases (comparing against last known release)
    - Significant commit activity spikes (commits in last 7d vs prior 7d)

    Uses GITHUB_TOKEN env var for authentication (5000 req/h vs 60 unauthenticated).
    """

    CATEGORY = "TECH_EVENT"

    def __init__(self, max_retries: int = 3, backoff_base: int = 2):
        super().__init__(name="GitHub", max_retries=max_retries, backoff_base=backoff_base)

        sources_cfg = get_sources()
        gh_cfg = sources_cfg.get("github", {})
        self.api_base = gh_cfg.get("api_base", "https://api.github.com")

        self._token = get_env("GITHUB_TOKEN", "")
        if self._token:
            self.session.headers.update({
                "Authorization": f"token {self._token}",
                "Accept": "application/vnd.github+json",
            })
        else:
            logger.warning("[GitHub] No GITHUB_TOKEN set — using unauthenticated access (60 req/h)")

        self._chains_cfg = get_chains()
        self._baselines_cfg = get_baselines()

    def _make_signal(
        self,
        chain: str,
        description: str,
        reliability: float,
        evidence: dict,
    ) -> dict:
        return {
            "chain": chain,
            "category": self.CATEGORY,
            "description": description,
            "source": "GitHub",
            "reliability": min(max(reliability, 0.0), 1.0),
            "evidence": evidence,
        }

    def _check_latest_release(self, chain: str, repo: str, baseline: dict) -> list[dict]:
        """Fetch latest release and detect if it's new (within 48h)."""
        signals: list[dict] = []
        url = f"{self.api_base}/repos/{repo}/releases/latest"
        data = self.fetch_with_retry(url)
        if not data:
            return signals

        tag = data.get("tag_name", "")
        name = data.get("name", tag)
        published_at = data.get("published_at")
        html_url = data.get("html_url", "")
        prerelease = data.get("prerelease", False)
        draft = data.get("draft", False)

        if draft or not published_at:
            return signals

        try:
            pub_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return signals

        now = datetime.now(timezone.utc)
        age_hours = (now - pub_dt).total_seconds() / 3600

        # Only flag releases published within the last 48 hours
        if age_hours > 48:
            return signals

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
                "age_hours": round(age_hours, 1),
            },
        ))

        return signals

    def _check_commit_activity(self, chain: str, repo: str, baseline: dict) -> list[dict]:
        """Compare commits in last 7 days vs prior 7 days for activity spike."""
        signals: list[dict] = []
        now = datetime.now(timezone.utc)

        # Fetch commits from last 14 days
        since_14d = (now - timedelta(days=14)).isoformat()
        url = f"{self.api_base}/repos/{repo}/commits"
        params = {"since": since_14d, "per_page": 100}
        data = self.fetch_with_retry(url, params=params)
        if not data or not isinstance(data, list):
            return signals

        cutoff_7d = now - timedelta(days=7)
        recent_commits = 0
        prior_commits = 0

        for commit in data:
            date_str = commit.get("commit", {}).get("committer", {}).get("date")
            if not date_str:
                continue
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
            if dt >= cutoff_7d:
                recent_commits += 1
            else:
                prior_commits += 1

        if prior_commits == 0:
            # New repo or first activity — only flag if significant recent commits
            if recent_commits >= 20:
                signals.append(self._make_signal(
                    chain=chain,
                    description=f"Burst of {recent_commits} commits in 7d ({repo})",
                    reliability=0.6,
                    evidence={
                        "metric": "commit_burst",
                        "repo": repo,
                        "commits_7d": recent_commits,
                        "commits_prior_7d": prior_commits,
                    },
                ))
            return signals

        ratio = recent_commits / prior_commits
        # Spike if 2x+ increase and at least 10 recent commits (avoid noise from small repos)
        if ratio >= 2.0 and recent_commits >= 10:
            signals.append(self._make_signal(
                chain=chain,
                description=f"Commit activity spike: {recent_commits} commits in 7d vs {prior_commits} prior 7d ({repo})",
                reliability=0.75,
                evidence={
                    "metric": "commit_activity_spike",
                    "repo": repo,
                    "commits_7d": recent_commits,
                    "commits_prior_7d": prior_commits,
                    "ratio": round(ratio, 2),
                },
            ))

        return signals

    def collect(self) -> list[dict]:
        """Collect GitHub signals for all chains with github_repos configured.

        Returns:
            List of signal dicts with keys: chain, category, description,
            source, reliability, evidence.
        """
        signals: list[dict] = []

        for chain_name, chain_cfg in self._chains_cfg.items():
            repos = chain_cfg.get("github_repos")
            if not repos or not isinstance(repos, list):
                continue

            baseline = self._baselines_cfg.get(chain_name, {})

            for repo in repos:
                if not repo or not isinstance(repo, str):
                    continue

                signals.extend(self._check_latest_release(chain_name, repo, baseline))
                signals.extend(self._check_commit_activity(chain_name, repo, baseline))

        logger.info(f"[GitHub] Collected {len(signals)} signals")
        return signals
