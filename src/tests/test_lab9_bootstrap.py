"""M4: paired bootstrap operates on matched item means, not independently sampled rows."""

import pytest

from lab9.stats import paired_bootstrap

pytestmark = pytest.mark.student


def test_bootstrap_preserves_pairing_and_pr_minus_baseline_direction():
    # Every paired improvement is 0.25; pairing makes the CI exactly 0.25 as well.
    assert paired_bootstrap([0.25, 0.5, 0.75], [0.0, 0.25, 0.5]) == pytest.approx((0.25, 0.25, 0.25), abs=1e-12)
    assert paired_bootstrap([0.0, 0.25, 0.5], [0.25, 0.5, 0.75]) == pytest.approx((-0.25, -0.25, -0.25), abs=1e-12)


@pytest.mark.parametrize("a,b", [([], []), ([1], [1, 0]), ([1], [0]),
                                ([[1, 0]], [[0, 0]]), ([1, float("nan")], [0, 0]),
                                ([1, 0], [0, float("inf")])])
def test_bootstrap_rejects_unpaired_or_nonfinite_item_means(a, b):
    with pytest.raises(ValueError):
        paired_bootstrap(a, b)


@pytest.mark.parametrize("kwargs", [{"n_resamples": 0}, {"confidence": 1.0}])
def test_bootstrap_rejects_invalid_sampling_parameters(kwargs):
    with pytest.raises(ValueError):
        paired_bootstrap([0, 1], [1, 0], **kwargs)
