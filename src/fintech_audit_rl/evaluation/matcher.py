"""Publicly specified one-to-one matching, independent of issue generation."""

from collections.abc import Iterable

from fintech_audit_rl.schemas.actions import Finding
from fintech_audit_rl.schemas.private import TruthIssue


def match_count(
    findings: Iterable[Finding],
    issues: Iterable[TruthIssue],
    public_ids: set[str],
    tolerance_minor: int = 0,
) -> int:
    """Maximum cardinality matching; duplicate findings cannot reuse an issue."""
    answers = list(findings)
    targets = list(issues)
    if type(tolerance_minor) is not int or tolerance_minor < 0:
        raise ValueError("tolerance must be a nonnegative integer")
    edges: list[list[int]] = []
    for finding in answers:
        affected = set(finding.affected_ids)
        evidence = set(finding.evidence_ids)
        candidates = []
        if evidence <= public_ids and affected <= public_ids:
            for index, issue in enumerate(targets):
                if (
                    finding.type == issue.type
                    and affected == set(issue.affected_ids)
                    and finding.currency == issue.currency
                    and abs(finding.claimed_amount_minor - issue.expected_amount_minor)
                    <= tolerance_minor
                    and any(set(allowed) <= evidence for allowed in issue.evidence_sets)
                ):
                    candidates.append(index)
        edges.append(candidates)
    owner: dict[int, int] = {}

    def augment(answer: int, visited: set[int]) -> bool:
        for target in edges[answer]:
            if target in visited:
                continue
            visited.add(target)
            if target not in owner or augment(owner[target], visited):
                owner[target] = answer
                return True
        return False

    # Maximum cardinality is independent of order; tie choice is not exposed.
    for answer in range(len(answers)):
        augment(answer, set())
    return len(owner)
