import pytest
from hypothesis import HealthCheck, given, note, settings

from capistry.compare import Comparable, Comparer

from .util import strategy as st


@settings(suppress_health_check=(HealthCheck.too_slow,))
@given(st.tapers() | st.surfaces() | st.stems())
def test_metrics(surface: Comparable):
    layout = surface.metrics

    assert layout
    assert layout.owner == surface
    assert layout.groups

    for group in layout.groups:
        note(group)
        assert group.title
        assert group.metrics
        for metric in group.metrics:
            assert metric.name


def test_comparer_comparable_req():
    with pytest.raises(ValueError, match="At least one comparable required"):
        Comparer()
