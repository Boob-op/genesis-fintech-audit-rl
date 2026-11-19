"""Privileged answer adapter; never import into an ordinary worker."""

from fintech_audit_rl.schemas.actions import Finding, Submit
from fintech_audit_rl.schemas.private import TruthIssue
from fintech_audit_rl.schemas.public import Manifest


def oracle_submit(manifest: Manifest, issues: list[TruthIssue]) -> Submit:
    """Make a structurally valid answer from evaluator-owned truth."""
    findings = [
        Finding(
            type=issue.type,
            affected_ids=list(issue.affected_ids),
            claimed_amount_minor=issue.expected_amount_minor,
            currency=issue.currency,
            evidence_ids=list(issue.evidence_sets[0]),
            explanation="Public documents support this discrepancy.",
        )
        for issue in issues
    ]
    return Submit(episode_id=manifest.episode_id, findings=findings)
