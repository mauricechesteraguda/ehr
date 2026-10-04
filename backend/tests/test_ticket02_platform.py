"""type-10042026-Maurice: Ticket02 documentation contracts, written RED first."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
def _ticket02_docs() -> str:
    """type-10042026-Maurice: Read the operator documentation contract."""
    return "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in ("platform/README.md", "platform/docs/decisions/README.md")
    )


def test_TC_PLAT_0005_kind_bootstrap_happy_path() -> None:
    """TC-PLAT-0005: docs define the demo kind bootstrap boundary."""
    docs = _ticket02_docs()
    assert "kind" in docs.lower()
    assert "Helm" in docs
    assert "demo" in docs.lower()
    assert "ephemeral" in docs.lower()


def test_TC_PLAT_0006_kind_bootstrap_retry_and_cleanup() -> None:
    """TC-PLAT-0006: docs state bounded retry and idempotent cleanup expectations."""
    docs = _ticket02_docs().lower()
    assert "bounded" in docs and "retry" in docs
    assert "idempotent" in docs and "cleanup" in docs


def test_TC_PLAT_0007_kind_failed_migration_gate() -> None:
    """TC-PLAT-0007: docs define migration failure as a rollout gate."""
    docs = _ticket02_docs().lower()
    assert "migration" in docs and "gate" in docs
    assert "not promoted" in docs or "blocks" in docs


def test_TC_PLAT_0008_kind_unhealthy_rollout_gate() -> None:
    """TC-PLAT-0008: docs define readiness failure and preserved healthy capacity."""
    docs = _ticket02_docs().lower()
    assert "readiness" in docs and "promotion" in docs
    assert "healthy capacity" in docs
