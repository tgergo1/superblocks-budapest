"""Static map exports, including high resolution tiling."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple

import geopandas as gpd
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)


def _ensure_path(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def tiled_edge_plot(
    edges: gpd.GeoDataFrame,
    output_path: str | Path,
    *,
    size: Tuple[float, float] = (12.0, 12.0),
    dpi: int = 200,
    num_tiles: int = 1,
    linewidth: float = 0.6,
    color_column: str | None = None,
    facecolor: str = "black",
    edgecolor: str = "white",
) -> Path:
    """Render a static figure of the street network, optionally tiled."""

    if edges.empty:
        raise ValueError("No edges supplied for static plot")

    bounds = edges.total_bounds
    x_min, y_min, x_max, y_max = bounds
    x_range = x_max - x_min
    y_range = y_max - y_min

    path = _ensure_path(output_path)

    if num_tiles <= 1:
        fig, ax = plt.subplots(figsize=size, dpi=dpi)
        _plot_tile(ax, edges, bounds, linewidth, color_column)
        ax.axis("off")
    else:
        fig, axes = plt.subplots(num_tiles, num_tiles, figsize=(size[0] * num_tiles, size[1] * num_tiles), dpi=dpi)
        if num_tiles == 1:
            axes = np.array([[axes]])
        for row in range(num_tiles):
            for col in range(num_tiles):
                ax = axes[row][col]
                llx = x_min + (col / num_tiles) * x_range
                urx = x_min + ((col + 1) / num_tiles) * x_range
                lly = y_min + (row / num_tiles) * y_range
                ury = y_min + ((row + 1) / num_tiles) * y_range
                tile_bounds = (llx, lly, urx, ury)
                _plot_tile(ax, edges, tile_bounds, linewidth, color_column)
                ax.axis("off")
        plt.subplots_adjust(wspace=0, hspace=0)

    fig.patch.set_facecolor(facecolor)
    for ax in fig.axes:
        ax.set_facecolor(facecolor)

    plt.savefig(path, dpi=dpi, facecolor=facecolor, edgecolor=edgecolor, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    logger.info("Saved static map to %s", path)
    return path


def _plot_tile(
    ax,
    edges: gpd.GeoDataFrame,
    bounds: Tuple[float, float, float, float],
    linewidth: float,
    color_column: str | None,
) -> None:
    llx, lly, urx, ury = bounds
    subset = edges.cx[llx:urx, lly:ury]
    if subset.empty:
        subset = edges
    if color_column and color_column in subset.columns:
        values = subset[color_column].astype(float)
        vmin = float(values.min())
        vmax = float(values.max())
        if vmin == vmax:
            colours = [mcolors.to_hex(cm.viridis(0.9))] * len(subset)
        else:
            norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
            colours = [mcolors.to_hex(cm.viridis(norm(val))) for val in values]
        subset.plot(ax=ax, linewidth=linewidth, color=colours)
    else:
        subset.plot(ax=ax, linewidth=linewidth, color="#FFFFFF")
    ax.set_xlim(llx, urx)
    ax.set_ylim(lly, ury)
