"""Shared plot styling for the tunnel LiDAR visualisations.

Sequential data (range, intensity, height) uses perceptually uniform ramps that
go light -> dark in one direction. `cividis` is the CVD-safe default; `magma`
and `viridis` are kept for contrast-heavy renders. Rainbow maps (`jet`, `hsv`)
are deliberately absent.
"""
import matplotlib as mpl

# Categorical slots, used in fixed order and never cycled.
SERIES = {
    'light': ['#2a78d6', '#eb6834', '#1baf7a'],
    'dark': ['#3987e5', '#d95926', '#199e70'],
}

INK = {
    'light': dict(surface='#fcfcfb', primary='#0b0b0b',
                  secondary='#52514e', grid='#d8d7d2'),
    'dark': dict(surface='#1a1a19', primary='#ffffff',
                 secondary='#c3c2b7', grid='#3a3a38'),
}

# Sequential ramps by the quantity they encode.
RAMP = {
    'range': 'cividis',      # distance: CVD-safe, light -> dark
    'intensity': 'magma',    # reflectivity: wide dynamic range
    'height': 'viridis',     # elevation above sensor
    'density': 'magma',      # accumulated point density
}


def apply(mode='light'):
    """Install the plot theme and return the ink dict for that mode."""
    ink = INK[mode]
    mpl.rcParams.update({
        'figure.facecolor': ink['surface'],
        'axes.facecolor': ink['surface'],
        'savefig.facecolor': ink['surface'],
        'text.color': ink['primary'],
        'axes.labelcolor': ink['secondary'],
        'axes.edgecolor': ink['grid'],
        'axes.titlecolor': ink['primary'],
        'axes.titlesize': 10,
        'axes.titleweight': 'normal',
        'axes.labelsize': 9,
        'axes.grid': True,
        'axes.spines.top': False,
        'axes.spines.right': False,
        'grid.color': ink['grid'],
        'grid.linewidth': 0.5,
        'grid.alpha': 0.6,
        'xtick.color': ink['secondary'],
        'ytick.color': ink['secondary'],
        'xtick.labelsize': 8,
        'ytick.labelsize': 8,
        'legend.frameon': False,
        'legend.fontsize': 8,
        'lines.linewidth': 2.0,
        'font.size': 9,
    })
    return ink
