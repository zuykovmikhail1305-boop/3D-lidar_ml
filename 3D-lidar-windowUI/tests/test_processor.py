"""Tests for the point cloud processor (voxel filter, decimation, coloring)."""

from __future__ import annotations

import numpy as np
import pytest

from data.frame import PointCloudFrame
from data.processor import (
    PointCloudProcessor,
    colorize_by_distance,
    colorize_by_scalar,
    decimate,
    voxel_downsample,
)


def test_voxel_downsample_centroid() -> None:
    xyz = np.array(
        [[0.1, 0.1, 0.1], [0.2, 0.2, 0.2], [0.15, 0.15, 0.15]], dtype=np.float32
    )
    intensity = np.array([1.0, 2.0, 3.0], dtype=np.float32)

    out_xyz, out_int = voxel_downsample(xyz, 0.5, intensity)

    assert out_xyz.shape == (1, 3)
    np.testing.assert_allclose(out_xyz[0], [0.15, 0.15, 0.15], atol=1e-5)
    np.testing.assert_allclose(out_int[0], 2.0, atol=1e-5)


def test_voxel_downsample_reduces_count() -> None:
    rng = np.random.default_rng(0)
    xyz = rng.uniform(0.0, 10.0, (10_000, 3)).astype(np.float32)

    out_xyz, _ = voxel_downsample(xyz, 2.0)

    assert out_xyz.shape[0] < xyz.shape[0]
    # 10x10x10 cube with leaf 2 => at most 5^3 = 125 voxels.
    assert out_xyz.shape[0] <= 125


def test_voxel_downsample_empty() -> None:
    xyz = np.empty((0, 3), dtype=np.float32)
    out_xyz, out_int = voxel_downsample(xyz, 0.5)
    assert out_xyz.shape == (0, 3)
    assert out_int is None


def test_voxel_downsample_invalid_leaf() -> None:
    with pytest.raises(ValueError):
        voxel_downsample(np.zeros((3, 3), np.float32), 0.0)


def test_decimate_caps_to_max() -> None:
    rng = np.random.default_rng(1)
    xyz = rng.uniform(0.0, 1.0, (1000, 3)).astype(np.float32)
    intensity = np.linspace(0.0, 1.0, 1000).astype(np.float32)

    out_xyz, out_int = decimate(xyz, 100, intensity, np.random.default_rng(2))

    assert out_xyz.shape == (100, 3)
    assert out_int.shape == (100,)
    assert len(np.unique(out_xyz, axis=0)) == 100  # no duplicate points


def test_decimate_returns_input_when_fits() -> None:
    xyz = np.zeros((10, 3), dtype=np.float32)
    out_xyz, _ = decimate(xyz, 100)
    assert out_xyz is xyz


def test_processor_pipeline_respects_limit() -> None:
    rng = np.random.default_rng(3)
    xyz = rng.uniform(0.0, 50.0, (20_000, 3)).astype(np.float32)
    intensity = rng.uniform(0.0, 1.0, 20_000).astype(np.float32)
    frame = PointCloudFrame(xyz=xyz, intensity=intensity, frame_id="test")

    processed = PointCloudProcessor(leaf_size=1.0, max_points=500, seed=1).process(frame)

    assert processed.num_points <= 500
    assert processed.intensity is not None
    assert processed.intensity.shape == (processed.num_points,)
    assert processed.frame_id == "test"


def test_processor_skips_voxel_when_leaf_zero() -> None:
    xyz = np.zeros((50, 3), dtype=np.float32)
    frame = PointCloudFrame(xyz=xyz)
    processed = PointCloudProcessor(leaf_size=0.0, max_points=10, seed=0).process(frame)
    assert processed.num_points == 10  # only decimation applied


def test_frame_validation() -> None:
    with pytest.raises(ValueError):
        PointCloudFrame(xyz=np.zeros((5, 2), dtype=np.float32))
    with pytest.raises(ValueError):
        PointCloudFrame(
            xyz=np.zeros((5, 3), dtype=np.float32),
            intensity=np.zeros(4, dtype=np.float32),
        )


def test_frame_num_points_and_bounds() -> None:
    frame = PointCloudFrame(
        xyz=np.array([[0, 0, 0], [10, -2, 3]], dtype=np.float32)
    )
    assert frame.num_points == 2
    mn, mx = frame.bounds()
    np.testing.assert_array_equal(mn, [0, -2, 0])
    np.testing.assert_array_equal(mx, [10, 0, 3])


def test_colorize_by_distance_shape_and_range() -> None:
    xyz = np.array([[0, 0, 0], [5, 0, 0], [10, 0, 0]], dtype=np.float32)
    rgb = colorize_by_distance(xyz)
    assert rgb.shape == (3, 3)
    assert rgb.dtype == np.uint8
    assert rgb.max() <= 255
    assert (rgb[0] != rgb[2]).any()  # near vs far produce different colors


def test_colorize_by_scalar_manual_range() -> None:
    values = np.array([0.0, 0.25, 0.5, 0.75, 1.0], dtype=np.float32)
    rgb = colorize_by_scalar(values, 0.0, 1.0)
    assert rgb.shape == (5, 3)
    assert rgb.dtype == np.uint8
    assert (rgb[0] != rgb[-1]).any()