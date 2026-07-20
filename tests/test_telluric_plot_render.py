"""
Rendering tests for the telluric-position page.

These drive the real plotting code against the packaged GIANO-B sky
transmission file and inspect the resulting figure, so they catch a panel that
silently stops drawing the eccentric information.
"""

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.backends.backend_pdf import PdfPages
from pathlib import Path

import phase_telluric_plot as tp

from test_telluric_drv import OBSERVATORY, T14_H, make_event, make_target


SKY_FITS = (Path(__file__).resolve().parents[1]
            / "src" / "spino" / "data" / "sky_transmission.fits")

LAM_RANGE_NM = (2359.0, 2426.0)
RV_GRID_KMS = (-50.0, 50.0, 1.5)


@pytest.fixture(autouse=True)
def _quiet_warnings():
    tp._warned_planets.clear()
    yield
    plt.close("all")


def render(target, tmp_path):
    with PdfPages(tmp_path / "page.pdf") as pdf:
        fig = tp.plot_telluric_position(
            make_event(), OBSERVATORY, target,
            vsys_kms=target["v_sys_kms"], sky_fits_path=str(SKY_FITS),
            lam_range_nm=LAM_RANGE_NM, rv_grid_kms=RV_GRID_KMS,
            pad_hours=1.0, exp_time_s=300.0, pdf=pdf,
            kp_kms=target["kp_kms"],
        )
    assert fig is not None, "plot_telluric_position must return its figure"
    return fig


def all_labels(fig):
    labels = []
    for ax in fig.axes:
        for artist in ax.get_children():
            label = getattr(artist, "get_label", lambda: "")()
            if isinstance(label, str) and label and not label.startswith("_"):
                labels.append(label)
    return labels


def texts(fig):
    """All figure text, wherever it lives."""
    inside = [t.get_text() for ax in fig.axes for t in ax.texts]
    return "\n".join(inside + [t.get_text() for t in fig.texts])


class TestInfoBoxPlacement:
    """The info box used to sit inside the left panel and cover the curves."""

    def test_info_box_is_not_drawn_inside_any_panel(self, tmp_path):
        fig = render(make_target(ecc=0.218, omega_p_deg=18.0), tmp_path)

        inside = [t.get_text() for ax in fig.axes for t in ax.texts]
        assert not any("v_{\\rm sys}" in s or "v_sys" in s for s in inside)

    def test_info_box_is_attached_to_the_figure(self, tmp_path):
        fig = render(make_target(ecc=0.218, omega_p_deg=18.0), tmp_path)

        assert any("v_{\\rm sys}" in t.get_text() for t in fig.texts)

    def test_info_box_stays_compact(self, tmp_path):
        """Wide lines instead of a tall stack, so it does not eat the page."""
        fig = render(make_target(ecc=0.218, omega_p_deg=18.0), tmp_path)

        body = "\n".join(t.get_text() for t in fig.texts)
        assert len(body.splitlines()) <= 4


def star_curve(fig):
    for line in fig.axes[0].get_lines():
        if line.get_label().startswith("Star"):
            return line.get_xdata(), line.get_ydata()
    raise AssertionError("stellar CC curve not found")


class TestStellarCurve:
    """
    The stellar CC used to be resampled through a spline defined only on the
    CC grid, so when the star fell outside +-50 km/s its peak was clipped and
    the wings degenerated into a flat line (scipy ext=3).
    """

    def _target_with_star_outside_the_grid(self):
        target = make_target(ecc=None)
        target["v_sys_kms"] = -80.0   # vtot ends up well below -50 km/s
        return target

    def test_peak_is_visible_when_the_star_falls_outside_the_cc_grid(
        self, tmp_path,
    ):
        fig = render(self._target_with_star_outside_the_grid(), tmp_path)

        x, y = star_curve(fig)
        peak_x = float(x[np.argmax(y)])
        lo, hi = fig.axes[0].get_xlim()
        assert lo <= peak_x <= hi, (
            f"stellar peak at {peak_x:.1f} outside xlim ({lo:.1f}, {hi:.1f})"
        )

    def test_curve_reaches_the_same_maximum_as_the_telluric_one(
        self, tmp_path,
    ):
        """A translated copy, not a truncated or flattened one."""
        fig = render(self._target_with_star_outside_the_grid(), tmp_path)

        _, y_star = star_curve(fig)
        telluric = [ln for ln in fig.axes[0].get_lines()
                    if ln.get_label().startswith("Telluric")][0]
        assert np.max(y_star) == pytest.approx(
            np.max(telluric.get_ydata()), abs=1e-12,
        )

    def test_has_no_flat_extrapolated_tail(self, tmp_path):
        fig = render(self._target_with_star_outside_the_grid(), tmp_path)

        _, y = star_curve(fig)
        # ext=3 produced long runs of exactly the boundary value
        longest_run = max(
            len(list(group))
            for _, group in __import__("itertools").groupby(np.round(y, 12))
        )
        assert longest_run < 5, f"{longest_run} identical consecutive samples"

    def test_is_offset_from_the_telluric_curve_by_vtot(self, tmp_path):
        fig = render(self._target_with_star_outside_the_grid(), tmp_path)

        x_star, y_star = star_curve(fig)
        telluric = [ln for ln in fig.axes[0].get_lines()
                    if ln.get_label().startswith("Telluric")][0]
        shift = x_star - telluric.get_xdata()
        assert np.allclose(shift, shift[0]), "not a rigid translation"
        assert np.allclose(y_star, telluric.get_ydata())


class TestAxisLimits:
    """Everything drawn must be visible, not clipped by the CC grid range."""

    def _left_panel_xlim(self, fig):
        return fig.axes[0].get_xlim()

    def test_includes_the_stellar_velocity_even_when_far_outside_the_grid(
        self, tmp_path,
    ):
        # v_sys chosen so the star lands well beyond the +-50 km/s CC grid
        target = make_target(ecc=None)
        target["v_sys_kms"] = 140.0
        fig = render(target, tmp_path)

        # the star sits near v_sys - <v_bary>, i.e. around +110..+140 km/s
        lo, hi = self._left_panel_xlim(fig)
        assert hi > 100.0, f"star clipped: xlim = ({lo}, {hi})"

    def test_includes_the_circular_band_of_an_eccentric_target(self, tmp_path):
        target = make_target(ecc=0.44, omega_p_deg=20.0)
        fig = render(target, tmp_path)

        lo, hi = self._left_panel_xlim(fig)
        xs = [
            child.get_path().vertices[:, 0]
            for child in fig.axes[0].get_children()
            if getattr(child, "get_label", lambda: "")() ==
            "Planet RV, circular approx."
        ]
        assert xs, "circular reference band not drawn"
        band_lo, band_hi = float(np.min(xs[0])), float(np.max(xs[0]))
        assert lo <= band_lo and hi >= band_hi, (
            f"circular band clipped: xlim = ({lo}, {hi}), "
            f"band = ({band_lo}, {band_hi})"
        )

    def test_still_covers_the_full_cc_grid(self, tmp_path):
        fig = render(make_target(ecc=None), tmp_path)

        lo, hi = self._left_panel_xlim(fig)
        assert lo <= RV_GRID_KMS[0] and hi >= RV_GRID_KMS[1]


def legend_entries(fig):
    """(label, colour) for every entry actually shown in a legend."""
    out = []
    for ax in fig.axes:
        legend = ax.get_legend()
        if legend is None:
            continue
        for handle, text in zip(legend.legend_handles, legend.get_texts()):
            colour = None
            for getter in ("get_color", "get_facecolor", "get_edgecolor"):
                if hasattr(handle, getter):
                    colour = getattr(handle, getter)()
                    break
            out.append((text.get_text(), matplotlib.colors.to_hex(
                colour if np.ndim(colour) <= 1 else colour[0])))
    return out


class TestPalette:
    """One colour, one meaning: the figure must not reuse a hue for two
    unrelated quantities, since that is what makes it unreadable at a glance."""

    @pytest.mark.parametrize("kwargs", [
        dict(ecc=None),
        dict(ecc=0.218, omega_p_deg=18.0),
        dict(ecc=0.218, omega_p_deg=None),
    ], ids=["circular", "keplerian", "envelope"])
    def test_no_colour_carries_two_different_labels(self, kwargs, tmp_path):
        fig = render(make_target(**kwargs), tmp_path)

        by_colour = {}
        for label, colour in legend_entries(fig):
            by_colour.setdefault(colour, set()).add(label)
        clashes = {c: ls for c, ls in by_colour.items() if len(ls) > 1}
        assert not clashes, f"colour reused for different meanings: {clashes}"

    def test_transit_duration_is_not_the_stellar_colour(self, tmp_path):
        """T14 is a time interval; the star is a velocity.  Same blue for both
        made the two panels read as if they showed the same thing."""
        fig = render(make_target(ecc=None), tmp_path)

        entries = dict(legend_entries(fig))
        star = [c for lbl, c in entries.items() if lbl.startswith("Star")]
        t14 = [c for lbl, c in entries.items() if "T_{14}" in lbl]
        assert star and t14
        assert star[0] != t14[0]

    def test_envelope_trace_is_drawn_as_the_circular_solution(self, tmp_path):
        """With omega unknown the drawn line IS the circular one, so it must
        carry the circular colour, not the planet's."""
        fig = render(make_target(ecc=0.218, omega_p_deg=None), tmp_path)

        traces = [ln for ln in fig.axes[1].get_lines()
                  if ln.get_label().startswith("Planet RV")]
        assert traces
        assert matplotlib.colors.to_hex(traces[0].get_color()) == "#777777"


class TestLegendCompleteness:

    @pytest.mark.parametrize("kwargs", [
        dict(ecc=None),
        dict(ecc=0.218, omega_p_deg=18.0),
        dict(ecc=0.218, omega_p_deg=None),
    ], ids=["circular", "keplerian", "envelope"])
    def test_every_labelled_artist_reaches_a_legend(self, kwargs, tmp_path):
        fig = render(make_target(**kwargs), tmp_path)

        shown = {label for label, _ in legend_entries(fig)}
        for label in all_labels(fig):
            assert label in shown, f"{label!r} drawn but missing from legend"

    def test_transit_duration_band_is_visible_in_the_legend(self, tmp_path):
        """At alpha 0.08 the T14 patch rendered as a white square."""
        fig = render(make_target(ecc=None), tmp_path)

        patches = [h for ax in fig.axes if ax.get_legend()
                   for h, t in zip(ax.get_legend().legend_handles,
                                   ax.get_legend().get_texts())
                   if "T_{14}" in t.get_text()]
        assert patches
        assert patches[0].get_alpha() is None or patches[0].get_alpha() >= 0.25


class TestAxisLabels:

    def test_left_panel_names_the_reference_frame(self, tmp_path):
        fig = render(make_target(ecc=None), tmp_path)

        assert "Earth frame" in fig.axes[0].get_xlabel()

    def test_right_panel_states_where_the_tellurics_sit(self, tmp_path):
        fig = render(make_target(ecc=None), tmp_path)

        assert "0" in fig.axes[1].get_xlabel()
        assert "tellur" in fig.axes[1].get_xlabel().lower()

    def test_phase_axis_says_it_is_relative_to_transit(self, tmp_path):
        """Values are unwrapped into [-0.5, 0.5), which is not orbital phase."""
        fig = render(make_target(ecc=None), tmp_path)

        assert "transit" in fig.axes[1].get_ylabel().lower()


class TestLabelSymmetry:

    def test_keplerian_band_names_itself_keplerian(self, tmp_path):
        """Its grey counterpart says 'circular', so this one must say what it
        is instead of leaving the reader to infer it."""
        fig = render(make_target(ecc=0.218, omega_p_deg=18.0), tmp_path)

        joined = " ".join(all_labels(fig)).lower()
        assert "keplerian" in joined

    def test_time_window_is_stated_once_with_its_unit(self, tmp_path):
        """Stated in the right panel's title rather than repeated in every
        legend entry, and with the unit spelled out."""
        fig = render(make_target(ecc=None), tmp_path)

        title = fig.axes[1].get_title()
        assert "T$_1$" in title and "T$_4$" in title
        assert "min" in title

    def test_the_same_solution_has_the_same_name_in_both_panels(self, tmp_path):
        fig = render(make_target(ecc=0.218, omega_p_deg=18.0), tmp_path)

        labels = [lbl for lbl, _ in legend_entries(fig)]
        keplerian = [s for s in labels if "Keplerian" in s]
        assert len(keplerian) == 2, "band and trace must share one name"
        assert keplerian[0] == keplerian[1]

    def test_step_is_reported_from_the_actual_parameter(self, tmp_path):
        """The title used to hard-code '200s' regardless of the real step."""
        target = make_target(ecc=None)
        with PdfPages(tmp_path / "p.pdf") as pdf:
            fig = tp.plot_telluric_position(
                make_event(), OBSERVATORY, target,
                vsys_kms=target["v_sys_kms"], sky_fits_path=str(SKY_FITS),
                lam_range_nm=LAM_RANGE_NM, rv_grid_kms=RV_GRID_KMS,
                pad_hours=1.0, exp_time_s=300.0, pdf=pdf,
                kp_kms=target["kp_kms"], drv_step_s=50.0,
            )

        assert "50" in fig.axes[1].get_title()


class TestCircularTarget:

    def test_draws_no_circular_reference_curve(self, tmp_path):
        """Nothing to compare against when the orbit is already circular, so
        no separate 'approx.' curve should appear."""
        fig = render(make_target(ecc=None), tmp_path)

        assert not any("approx" in s.lower() for s in all_labels(fig))

    def test_still_draws_the_planet_band_and_the_delta_rv_trace(self, tmp_path):
        fig = render(make_target(ecc=None), tmp_path)

        # the band on the left panel and the trace on the right one
        assert any(a.get_label().startswith("Planet RV")
                   for a in fig.axes[0].get_children())
        assert any(ln.get_label().startswith("Planet RV")
                   for ln in fig.axes[1].get_lines())


class TestEccentricKnownOmega:

    def test_overlays_the_circular_reference(self, tmp_path):
        fig = render(make_target(ecc=0.218, omega_p_deg=18.0), tmp_path)

        assert any("circular" in s.lower() for s in all_labels(fig))

    def test_info_box_quotes_both_semi_amplitudes_and_the_deviation(
        self, tmp_path,
    ):
        fig = render(make_target(ecc=0.218, omega_p_deg=18.0), tmp_path)

        body = texts(fig)
        assert "119.88" in body            # Kp / sqrt(1 - e^2)
        assert "117.00" in body            # circular Kp
        assert "0.218" in body             # the eccentricity in play
        assert "circ" in body.lower()

    def test_info_box_no_longer_mentions_the_instrument(self, tmp_path):
        fig = render(make_target(ecc=0.218, omega_p_deg=18.0), tmp_path)

        assert "GIANO" not in texts(fig)


class TestEccentricUnknownOmega:

    def test_draws_the_omega_envelope_band(self, tmp_path):
        fig = render(make_target(ecc=0.218, omega_p_deg=None), tmp_path)

        assert any("omega" in s.lower() or "\\omega" in s
                   for s in all_labels(fig))

    def test_does_not_promise_a_separate_circular_curve_on_the_phase_panel(
        self, tmp_path,
    ):
        """Under an envelope the drawn line IS the circular one, so a second
        'circular approx.' entry would point at an invisible curve."""
        fig = render(make_target(ecc=0.218, omega_p_deg=None), tmp_path)

        phase_panel = fig.axes[1]
        entries = [
            artist.get_label() for artist in phase_panel.get_children()
            if isinstance(getattr(artist, "get_label", lambda: None)(), str)
            and artist.get_label().startswith("circular")
        ]
        assert entries == []

    def test_info_box_says_omega_is_unknown(self, tmp_path):
        fig = render(make_target(ecc=0.218, omega_p_deg=None), tmp_path)

        body = texts(fig).lower()
        assert "unknown" in body or "envelope" in body
