"""Visualise the tunnel LiDAR rosbag2 dataset.

Sensor convention used throughout (verified from the data):
    +x  lateral / right      -y  direction of travel (forward)      +z  up
Plots report "forward distance" as -y so that ahead is positive.

Examples
--------
    python visualize.py overview
    python visualize.py frame roundT_doubleT --index 120
    python visualize.py rangeimage roundT_pressureGate_roundT -i 60
    python visualize.py map squareT_platform_squareT_switch --stride 10
    python visualize.py animate doubleT_platform --stride 4 --fps 10
    python visualize.py export roundT_doubleT -i 0 --format ply
"""
import argparse
import os
import sys
import glob

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rosbag_pc2 import open_bag, xyz  # noqa: E402
import theme as theme  # noqa: E402

DEFAULT_ROOT = r'D:\hack\extracted'
N_RINGS = 128


# --------------------------------------------------------------------------- #
# dataset plumbing
# --------------------------------------------------------------------------- #
def find_bags(root):
    """Map bag name -> bag directory, for both single-file and split bags."""
    bags = {}
    for meta in glob.glob(os.path.join(root, '**', 'metadata.yaml'), recursive=True):
        d = os.path.dirname(meta)
        bags[os.path.basename(d)] = d
    return bags


def bag_size(bag_dir):
    return sum(os.path.getsize(f)
               for f in glob.glob(os.path.join(bag_dir, '*.db3'))) / 1e9


def resolve(root, name):
    bags = find_bags(root)
    if name in bags:
        return bags[name]
    matches = [k for k in bags if name.lower() in k.lower()]
    if len(matches) == 1:
        return bags[matches[0]]
    raise SystemExit('unknown scenario %r; available: %s'
                     % (name, ', '.join(sorted(bags))))


def valid_mask(points):
    """Zero-filled slots mark 'no return' in this dataset; drop them."""
    v = np.stack([points['x'], points['y'], points['z']], axis=-1)
    return np.isfinite(v).all(1) & (np.abs(v).sum(1) > 1e-6)


def as_arrays(points):
    """Structured array -> (xyz, intensity, ring) with invalid returns removed."""
    m = valid_mask(points)
    v = np.stack([points['x'], points['y'], points['z']], axis=-1)[m].astype(np.float32)
    return v, points['intensity'][m].astype(np.float32), points['ring'][m]


def range_image(points, key='range'):
    """Reshape a message into a (ring, azimuth) image.

    Point order in these bags is column-major: index = column * 128 + ring.
    """
    if key == 'range':
        img = np.sqrt(points['x'].astype(np.float64) ** 2
                      + points['y'].astype(np.float64) ** 2
                      + points['z'].astype(np.float64) ** 2)
    elif key == 'intensity':
        img = points['intensity'].astype(np.float64)
    elif key == 'height':
        img = points['z'].astype(np.float64)
    else:
        raise ValueError(key)
    invalid = ~valid_mask(points)
    img = img.copy()
    img[invalid] = np.nan
    img = img.reshape(-1, N_RINGS).T          # (ring, column)
    return crop_columns(img)


def crop_columns(img):
    """Trim azimuth columns that carry no return at all (bags with a 100 deg FOV)."""
    filled = np.isfinite(img).any(axis=0)
    if not filled.any():
        return img
    lo, hi = np.flatnonzero(filled)[[0, -1]]
    return img[:, lo:hi + 1]


def masked(img):
    return np.ma.masked_invalid(img)


def save(fig, out, ink):
    os.makedirs(os.path.dirname(os.path.abspath(out)) or '.', exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches='tight', facecolor=ink['surface'])
    plt.close(fig)
    print('wrote', out)


# --------------------------------------------------------------------------- #
# panels
# --------------------------------------------------------------------------- #
def auto_half_width(values, lo=3.0, hi=14.0, pct=99.8):
    """Tight but outlier-tolerant half-extent, so narrow tunnels fill the panel."""
    if not len(values):
        return lo
    return float(np.clip(np.ceil(np.percentile(np.abs(values), pct)), lo, hi))


def panel_bev(ax, v, colour, ink, cmap, label, fwd_max=60.0, half_width=None):
    """Top-down view: forward distance on x, lateral offset on y."""
    fwd, lat = -v[:, 1], v[:, 0]
    in_range = (fwd > 0) & (fwd < fwd_max)
    if half_width is None:
        half_width = auto_half_width(lat[in_range])
    keep = in_range & (np.abs(lat) < half_width)
    sc = ax.scatter(fwd[keep], lat[keep], c=colour[keep], s=0.12, cmap=cmap,
                    vmin=0, vmax=fwd_max, linewidths=0, rasterized=True)
    ax.plot(0, 0, marker='^', ms=9, color=ink['primary'],
            markeredgecolor=ink['surface'], markeredgewidth=1.2, zorder=5)
    ax.set_xlabel('forward distance  −y  [m]')
    ax.set_ylabel('lateral  x  [m]')
    ax.set_title('Top-down (BEV)')
    ax.set_aspect('equal')
    ax.set_xlim(0, fwd_max)
    ax.set_ylim(-half_width, half_width)
    cb = ax.figure.colorbar(sc, ax=ax, pad=0.01, fraction=0.03)
    cb.set_label(label, fontsize=8)
    cb.ax.tick_params(labelsize=7, color=ink['grid'])
    cb.outline.set_edgecolor(ink['grid'])
    return sc


def panel_side(ax, v, colour, ink, cmap, label, fwd_max=60.0, half_height=None):
    """Side elevation: forward distance on x, height on y."""
    fwd, up = -v[:, 1], v[:, 2]
    keep = (fwd > 0) & (fwd < fwd_max)
    if half_height is None:
        half_height = auto_half_width(up[keep])
    sc = ax.scatter(fwd[keep], up[keep], c=colour[keep], s=0.12,
                    cmap=cmap, linewidths=0, rasterized=True)
    ax.axhline(0, color=ink['grid'], lw=0.8)
    ax.set_xlabel('forward distance  −y  [m]')
    ax.set_ylabel('height  z  [m]')
    ax.set_title('Side elevation')
    ax.set_aspect('equal')
    ax.set_xlim(0, fwd_max)
    ax.set_ylim(-half_height, half_height)
    return sc


def panel_cross_section(ax, v, ink, series, at=10.0, slab=0.5):
    """Tunnel profile in the x-z plane, from a thin slab at a fixed distance."""
    fwd = -v[:, 1]
    sel = np.abs(fwd - at) < slab
    ax.scatter(v[sel, 0], v[sel, 2], s=2.0, color=series[0],
               linewidths=0, rasterized=True)
    ax.plot(0, 0, marker='+', ms=10, color=ink['primary'], zorder=5)
    ax.set_xlabel('lateral  x  [m]')
    ax.set_ylabel('height  z  [m]')
    ax.set_title('Cross-section at %.0f m  (±%.1f m slab, %d pts)' % (at, slab, sel.sum()))
    ax.set_aspect('equal')


def panel_range_image(ax, points, ink, key='range', vmax=None):
    img = masked(range_image(points, key))
    cmap = plt.get_cmap(theme.RAMP[key]).copy()
    cmap.set_bad(ink['grid'])
    # Height is signed (the sensor sits above the floor), so it gets its own
    # lower bound instead of being clipped at zero like range and intensity.
    lo = np.percentile(img.compressed(), 1) if key == 'height' else 0
    im = ax.imshow(img, aspect='auto', cmap=cmap, origin='upper',
                   interpolation='nearest', vmin=lo,
                   vmax=vmax or np.percentile(img.compressed(), 99))
    ax.set_xlabel('azimuth column')
    ax.set_ylabel('ring  (0 = +14.4°, 127 = −25.1°)')
    ax.set_title('Range image — %s' % key)
    ax.grid(False)
    cb = ax.figure.colorbar(im, ax=ax, pad=0.01, fraction=0.03)
    cb.set_label('%s [%s]' % (key, 'm' if key != 'intensity' else '0–255'), fontsize=8)
    cb.ax.tick_params(labelsize=7)
    cb.outline.set_edgecolor(ink['grid'])
    return im


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_overview(args):
    ink = theme.apply(args.mode)
    series = theme.SERIES[args.mode]
    bags = find_bags(args.root)
    if not bags:
        raise SystemExit('no .db3 bags under %s' % args.root)

    rows = []
    for name, db in bags.items():
        r = open_bag(db)
        meta, pts = r.read(0)
        v, inten, _ = as_arrays(pts)
        ts = r.timestamps
        dur = (ts[-1] - ts[0]) / 1e9
        rows.append(dict(name=name, frames=len(r), duration=dur,
                         hz=(len(r) - 1) / dur if dur else 0,
                         points=meta['n_points'], valid=len(v),
                         frame_id=meta['frame_id'],
                         size_gb=bag_size(db),
                         dt=np.diff(ts) / 1e9, t0=ts[0]))
        r.close()
    rows.sort(key=lambda d: d['name'])

    hdr = '%-38s %7s %9s %7s %10s %9s %-14s %7s' % (
        'scenario', 'frames', 'duration', 'rate', 'pts/frame', 'valid', 'frame_id', 'size')
    print(hdr)
    print('-' * len(hdr))
    for d in rows:
        print('%-38s %7d %8.1fs %6.1fHz %10d %8.0f%% %-14s %6.1fGB' % (
            d['name'], d['frames'], d['duration'], d['hz'], d['points'],
            100 * d['valid'] / d['points'], d['frame_id'], d['size_gb']))
    print('-' * len(hdr))
    print('%-38s %7d %8.1fs %30s %6.1fGB' % (
        'TOTAL', sum(d['frames'] for d in rows), sum(d['duration'] for d in rows),
        '', sum(d['size_gb'] for d in rows)))

    fig = plt.figure(figsize=(13, 7.5))
    gs = GridSpec(2, 2, figure=fig, hspace=0.45, wspace=0.25)
    names = [d['name'] for d in rows]
    ypos = np.arange(len(rows))[::-1]

    # One measure per axes, one series each -> a single colour, no legend needed.
    ax = fig.add_subplot(gs[0, 0])
    ax.barh(ypos, [d['frames'] for d in rows], color=series[0], height=0.62)
    for y, d in zip(ypos, rows):
        ax.text(d['frames'] + 12, y, str(d['frames']), va='center',
                fontsize=8, color=ink['secondary'])
    ax.set_yticks(ypos, names, fontsize=8)
    ax.set_xlabel('messages')
    ax.set_title('Frames per scenario')
    ax.grid(axis='y', visible=False)

    ax = fig.add_subplot(gs[0, 1])
    ax.barh(ypos, [d['duration'] for d in rows], color=series[1], height=0.62)
    for y, d in zip(ypos, rows):
        ax.text(d['duration'] + 1.2, y, '%.0fs' % d['duration'], va='center',
                fontsize=8, color=ink['secondary'])
    ax.set_yticks(ypos, [''] * len(rows))
    ax.set_xlabel('seconds')
    ax.set_title('Recording length')
    ax.grid(axis='y', visible=False)

    ax = fig.add_subplot(gs[1, :])
    t_min = min(d['t0'] for d in rows)
    for y, d in zip(ypos, rows):
        start = (d['t0'] - t_min) / 1e9
        ax.barh(y, d['duration'], left=start, height=0.5, color=series[2])
    ax.set_yticks(ypos, names, fontsize=8)
    ax.set_xlabel('seconds since first recording')
    ax.set_title('Recording timeline — all six runs were captured in one session')
    ax.grid(axis='y', visible=False)

    fig.suptitle('Tunnel LiDAR dataset — %d bags, %d frames, %.1f GB'
                 % (len(rows), sum(d['frames'] for d in rows),
                    sum(d['size_gb'] for d in rows)),
                 fontsize=12, y=0.98)
    save(fig, args.out or 'out/overview.png', ink)


def cmd_frame(args):
    ink = theme.apply(args.mode)
    series = theme.SERIES[args.mode]
    r = open_bag(resolve(args.root, args.scenario))
    idx = args.index if args.index >= 0 else len(r) // 2
    idx = min(idx, len(r) - 1)
    meta, pts = r.read(idx)
    v, inten, ring = as_arrays(pts)

    # Both strip panels keep a 1:1 metric aspect, so give each row a height in
    # proportion to its own extent — otherwise a narrow tunnel leaves the panel
    # collapsed inside an over-tall cell.
    near = (-v[:, 1] > 0) & (-v[:, 1] < args.far)
    half_w = args.width or auto_half_width(v[near, 0])
    half_h = auto_half_width(v[near, 2])
    span = 12.0                                    # plotted width in inches
    h_bev = span * 2 * half_w / args.far
    h_side = span * 2 * half_h / args.far
    h_bottom = 4.2

    fig = plt.figure(figsize=(15, h_bev + h_side + h_bottom + 2.2))
    gs = GridSpec(3, 2, figure=fig, height_ratios=[h_bev, h_side, h_bottom],
                  hspace=0.45, wspace=0.2)

    colour = np.linalg.norm(v, axis=1)
    panel_bev(fig.add_subplot(gs[0, :]), v, colour, ink,
              theme.RAMP['range'], 'range [m]', args.far, half_w)
    panel_side(fig.add_subplot(gs[1, :]), v, v[:, 2], ink,
               theme.RAMP['height'], 'height [m]', args.far, half_h)
    panel_cross_section(fig.add_subplot(gs[2, 0]), v, ink, series, at=args.at)
    panel_range_image(fig.add_subplot(gs[2, 1]), pts, ink, 'range')

    fig.suptitle('%s — frame %d/%d   t=+%.2f s   %d of %d returns valid (%.0f%%)'
                 % (args.scenario, idx, len(r) - 1,
                    (r.timestamps[idx] - r.timestamps[0]) / 1e9,
                    len(v), meta['n_points'], 100 * len(v) / meta['n_points']),
                 fontsize=12)
    r.close()
    save(fig, args.out or 'out/%s_frame%04d.png' % (args.scenario, idx), ink)


def cmd_rangeimage(args):
    ink = theme.apply(args.mode)
    r = open_bag(resolve(args.root, args.scenario))
    idx = args.index if args.index >= 0 else len(r) // 2
    meta, pts = r.read(min(idx, len(r) - 1))

    fig, axes = plt.subplots(3, 1, figsize=(14, 9), constrained_layout=True)
    for ax, key in zip(axes, ('range', 'intensity', 'height')):
        panel_range_image(ax, pts, ink, key)
    fig.suptitle('%s — frame %d — 128 rings × %d azimuth columns'
                 % (args.scenario, idx, range_image(pts).shape[1]), fontsize=12)
    r.close()
    save(fig, args.out or 'out/%s_range%04d.png' % (args.scenario, idx), ink)


def cmd_map(args):
    """Stack frames into one cloud. No odometry in these bags, so this is a
    sensor-frame overlay: static structure sharpens, moving parts smear."""
    ink = theme.apply(args.mode)
    r = open_bag(resolve(args.root, args.scenario))
    chunks, n = [], 0
    for i in range(0, len(r), args.stride):
        _, pts = r.read(i)
        v, inten, _ = as_arrays(pts)
        if args.subsample > 1:
            v, inten = v[::args.subsample], inten[::args.subsample]
        chunks.append((v, inten))
        n += 1
        if args.limit and n >= args.limit:
            break
    r.close()
    v = np.concatenate([c[0] for c in chunks])
    inten = np.concatenate([c[1] for c in chunks])
    print('accumulated %d frames -> %d points' % (n, len(v)))

    fwd, lat, up = -v[:, 1], v[:, 0], v[:, 2]
    keep = (fwd > 0) & (fwd < args.far)
    fig, axes = plt.subplots(3, 1, figsize=(15, 11), constrained_layout=True)

    cmap = theme.RAMP['density']
    for ax, (a, b, ylab, title) in zip(axes, [
            (fwd, lat, 'lateral  x  [m]', 'Top-down density'),
            (fwd, up, 'height  z  [m]', 'Side elevation density'),
            (fwd, np.hypot(lat, up), 'radial distance from axis  [m]',
             'Unrolled profile — tunnel radius along the run')]):
        h = ax.hexbin(a[keep], b[keep], gridsize=(560, 90), cmap=cmap,
                      bins='log', mincnt=1, linewidths=0)
        ax.set_xlabel('forward distance  −y  [m]')
        ax.set_ylabel(ylab)
        ax.set_title(title)
        ax.grid(False)
        cb = fig.colorbar(h, ax=ax, pad=0.01, fraction=0.025)
        cb.set_label('points (log)', fontsize=8)
        cb.ax.tick_params(labelsize=7)
        cb.outline.set_edgecolor(ink['grid'])

    fig.suptitle('%s — %d frames overlaid in the sensor frame (%d points)'
                 % (args.scenario, n, len(v)), fontsize=12)
    save(fig, args.out or 'out/%s_map.png' % args.scenario, ink)


def cmd_animate(args):
    from matplotlib.animation import FuncAnimation, PillowWriter
    ink = theme.apply(args.mode)
    r = open_bag(resolve(args.root, args.scenario))
    frames = list(range(0, len(r), args.stride))
    if args.limit:
        frames = frames[:args.limit]

    fig, (ax_bev, ax_cs) = plt.subplots(
        1, 2, figsize=(14, 5), gridspec_kw=dict(width_ratios=[3, 1]),
        constrained_layout=True)
    cmap = plt.get_cmap(theme.RAMP['range'])

    def draw(i):
        ax_bev.clear()
        ax_cs.clear()
        _, pts = r.read(i)
        v, _, _ = as_arrays(pts)
        fwd, lat = -v[:, 1], v[:, 0]
        keep = (fwd > 0) & (fwd < args.far) & (np.abs(lat) < 12)
        ax_bev.scatter(fwd[keep], lat[keep], c=np.linalg.norm(v, axis=1)[keep],
                       s=0.12, cmap=cmap, vmin=0, vmax=args.far,
                       linewidths=0, rasterized=True)
        ax_bev.plot(0, 0, marker='^', ms=9, color=ink['primary'], zorder=5)
        ax_bev.set_xlim(0, args.far)
        ax_bev.set_ylim(-12, 12)
        ax_bev.set_aspect('equal')
        ax_bev.set_xlabel('forward distance  −y  [m]')
        ax_bev.set_ylabel('lateral  x  [m]')
        ax_bev.set_title('%s — frame %d/%d  t=+%.1fs'
                         % (args.scenario, i, len(r) - 1,
                            (r.timestamps[i] - r.timestamps[0]) / 1e9))
        panel_cross_section(ax_cs, v, ink, theme.SERIES[args.mode], at=args.at)
        ax_cs.set_xlim(-6, 6)
        ax_cs.set_ylim(-6, 6)
        return ()

    out = args.out or 'out/%s.gif' % args.scenario
    os.makedirs(os.path.dirname(os.path.abspath(out)) or '.', exist_ok=True)
    anim = FuncAnimation(fig, draw, frames=frames, blit=False)
    anim.save(out, writer=PillowWriter(fps=args.fps),
              savefig_kwargs=dict(facecolor=ink['surface']))
    plt.close(fig)
    r.close()
    print('wrote %s (%d frames)' % (out, len(frames)))


def scan_profiles(reader, stride, nbins=180, at=15.0, slab=4.0, progress=True):
    """Radius-vs-angle around the tunnel axis for every sampled frame.

    Returns (indices, profiles[n, nbins], scalars dict). The tunnel axis is -y,
    so the angle runs around it: 0 deg = right wall, +90 = crown, 180 = left
    wall, -90 = invert. Stacking these columns turns a long traverse into one
    image where each kind of section reads as its own band.

    The lookahead has to be far enough for the +14.4 deg top beam to clear the
    crown: at 8 m it only reaches z = 2 m and the crown is missing, at 15 m it
    reaches 3.9 m and angular coverage is complete.
    """
    idxs = list(range(0, len(reader), stride))
    prof = np.full((len(idxs), nbins), np.nan, dtype=np.float32)
    rad_med = np.zeros(len(idxs))
    width = np.zeros(len(idxs))
    height = np.zeros(len(idxs))
    valid = np.zeros(len(idxs))
    reach = np.zeros(len(idxs))
    edges = np.linspace(-180, 180, nbins + 1)

    for n, i in enumerate(idxs):
        _, pts = reader.read(i)
        v, _, _ = as_arrays(pts)
        fwd = -v[:, 1]
        valid[n] = len(v)
        reach[n] = np.percentile(fwd, 99.9) if len(v) else 0
        sel = np.abs(fwd - at) < slab
        s = v[sel]
        if len(s) < 200:
            continue
        r = np.hypot(s[:, 0], s[:, 2])
        ang = np.degrees(np.arctan2(s[:, 2], s[:, 0]))
        b = np.clip(np.digitize(ang, edges) - 1, 0, nbins - 1)
        # Farthest return per angular bin = the lining, not clutter in front of
        # it. Accumulate into zeros, not NaN: np.maximum propagates NaN, so a
        # NaN-filled row would stay NaN. Empty bins become NaN afterwards.
        row = np.zeros(nbins)
        np.maximum.at(row, b, r)
        row[row == 0] = np.nan
        prof[n] = row
        rad_med[n] = np.nanmedian(row)
        width[n] = s[:, 0].max() - s[:, 0].min()
        height[n] = s[:, 2].max() - s[:, 2].min()
        if progress and n % 50 == 0:
            print('  scanned %d/%d frames' % (n, len(idxs)), flush=True)

    return (np.array(idxs), prof,
            dict(rad_med=rad_med, width=width, height=height,
                 valid=valid, reach=reach))


def cmd_timeline(args):
    """One picture of a whole traverse: how the tunnel section evolves with time."""
    ink = theme.apply(args.mode)
    series = theme.SERIES[args.mode]
    bag_dir = resolve(args.root, args.scenario)
    cache = args.cache or os.path.join(
        'out', '%s_timeline_s%d_at%d.npz' % (args.scenario, args.stride, args.at))

    if os.path.exists(cache) and not args.rescan:
        z = np.load(cache)
        idxs, prof = z['idxs'], z['prof']
        sc = {k: z[k] for k in ('rad_med', 'width', 'height', 'valid', 'reach')}
        t = z['t']
        total = int(z['total']) if 'total' in z else int(idxs[-1]) + 1
        print('loaded cached scan from', cache)
    else:
        r = open_bag(bag_dir)
        print('scanning %d frames (stride %d) of %s…' % (len(r), args.stride, args.scenario))
        idxs, prof, sc = scan_profiles(r, args.stride, at=args.at, slab=args.slab)
        t = (r.timestamps[idxs] - r.timestamps[0]) / 1e9
        total = len(r)
        r.close()
        os.makedirs(os.path.dirname(os.path.abspath(cache)) or '.', exist_ok=True)
        np.savez_compressed(cache, idxs=idxs, prof=prof, t=t,
                            total=len(r), **sc)
        print('cached scan to', cache)

    minutes = t / 60.0
    fig, axes = plt.subplots(3, 1, figsize=(15, 10), constrained_layout=True,
                             height_ratios=[2.0, 1.0, 1.0], sharex=True)

    cmap = plt.get_cmap(theme.RAMP['range']).copy()
    cmap.set_bad(ink['grid'])
    img = np.ma.masked_invalid(prof.T)
    im = axes[0].imshow(img, aspect='auto', origin='lower', cmap=cmap,
                        interpolation='nearest',
                        extent=[minutes[0], minutes[-1], -180, 180],
                        vmin=1, vmax=np.nanpercentile(prof, 98))
    axes[0].set_yticks([-180, -90, 0, 90, 180],
                       ['левая стена', 'лоток', 'правая стена', 'свод', 'левая стена'])
    axes[0].set_ylabel('угол вокруг оси тоннеля')
    axes[0].set_title('Развёртка обделки за весь проезд — радиус на %.0f м впереди' % args.at)
    axes[0].grid(False)
    cb = fig.colorbar(im, ax=axes[0], pad=0.01, fraction=0.025)
    cb.set_label('радиус [м]', fontsize=8)
    cb.ax.tick_params(labelsize=7)
    cb.outline.set_edgecolor(ink['grid'])

    axes[1].plot(minutes, sc['rad_med'], color=series[0], lw=1.4, label='медианный радиус')
    axes[1].plot(minutes, sc['width'], color=series[1], lw=1.4, label='ширина')
    axes[1].plot(minutes, sc['height'], color=series[2], lw=1.4, label='высота')
    axes[1].set_ylabel('метры')
    axes[1].set_title('Габариты сечения')
    axes[1].legend(ncol=3, loc='upper right')

    axes[2].plot(minutes, sc['valid'] / 1000.0, color=series[0], lw=1.4,
                 label='валидных точек, тыс.')
    axes[2].plot(minutes, sc['reach'], color=series[1], lw=1.4,
                 label='дальность видимости, м')
    axes[2].set_xlabel('время записи [мин]')
    axes[2].set_title('Заполненность кадра')
    axes[2].legend(ncol=2, loc='upper right')

    fig.suptitle('%s — %d кадров, %.1f мин (просмотрен каждый %d-й)'
                 % (args.scenario, total, minutes[-1], args.stride),
                 fontsize=12)
    save(fig, args.out or 'out/%s_timeline.png' % args.scenario, ink)


def cmd_export(args):
    """Dump one frame for CloudCompare / Open3D / MeshLab."""
    r = open_bag(resolve(args.root, args.scenario))
    idx = min(args.index if args.index >= 0 else 0, len(r) - 1)
    _, pts = r.read(idx)
    v, inten, ring = as_arrays(pts)
    r.close()
    out = args.out or 'out/%s_%04d.%s' % (args.scenario, idx, args.format)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or '.', exist_ok=True)

    if args.format == 'npy':
        np.save(out, np.column_stack([v, inten, ring.astype(np.float32)]))
    elif args.format == 'ply':
        with open(out, 'wb') as fh:
            fh.write(('ply\nformat binary_little_endian 1.0\n'
                      'element vertex %d\n'
                      'property float x\nproperty float y\nproperty float z\n'
                      'property float intensity\nproperty ushort ring\n'
                      'end_header\n' % len(v)).encode())
            rec = np.empty(len(v), dtype=[('x', '<f4'), ('y', '<f4'), ('z', '<f4'),
                                          ('intensity', '<f4'), ('ring', '<u2')])
            rec['x'], rec['y'], rec['z'] = v[:, 0], v[:, 1], v[:, 2]
            rec['intensity'], rec['ring'] = inten, ring
            fh.write(rec.tobytes())
    elif args.format == 'pcd':
        with open(out, 'wb') as fh:
            fh.write(('# .PCD v0.7\nVERSION 0.7\nFIELDS x y z intensity\n'
                      'SIZE 4 4 4 4\nTYPE F F F F\nCOUNT 1 1 1 1\n'
                      'WIDTH %d\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\n'
                      'POINTS %d\nDATA binary\n' % (len(v), len(v))).encode())
            fh.write(np.column_stack([v, inten]).astype('<f4').tobytes())
    print('wrote %s (%d points)' % (out, len(v)))


# --------------------------------------------------------------------------- #
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)

    def add_common(sp):
        sp.add_argument('--root', default=DEFAULT_ROOT,
                        help='folder holding the bag directories')
        sp.add_argument('--mode', default='light', choices=['light', 'dark'])
        sp.add_argument('--out', help='output path (defaults under ./out/)')
        return sp

    s = add_common(sub.add_parser('overview', help='summary table + dataset figure'))
    s.set_defaults(func=cmd_overview)

    def add_scenario(sp):
        add_common(sp)
        sp.add_argument('scenario', help='scenario name or unique substring')

    s = sub.add_parser('frame', help='four-panel view of a single sweep')
    add_scenario(s)
    s.add_argument('-i', '--index', type=int, default=-1, help='frame index (-1 = middle)')
    s.add_argument('--far', type=float, default=60.0, help='forward clip [m]')
    s.add_argument('--at', type=float, default=10.0, help='cross-section distance [m]')
    s.add_argument('--width', type=float, default=0.0,
                   help='BEV lateral half-width [m] (0 = fit to data)')
    s.set_defaults(func=cmd_frame)

    s = sub.add_parser('rangeimage', help='range / intensity / height images')
    add_scenario(s)
    s.add_argument('-i', '--index', type=int, default=-1)
    s.set_defaults(func=cmd_rangeimage)

    s = sub.add_parser('map', help='overlay many frames into one cloud')
    add_scenario(s)
    s.add_argument('--stride', type=int, default=5)
    s.add_argument('--limit', type=int, default=0, help='max frames (0 = all)')
    s.add_argument('--subsample', type=int, default=3, help='keep every Nth point')
    s.add_argument('--far', type=float, default=80.0)
    s.set_defaults(func=cmd_map)

    s = sub.add_parser('animate', help='animated GIF of the run')
    add_scenario(s)
    s.add_argument('--stride', type=int, default=3)
    s.add_argument('--limit', type=int, default=120)
    s.add_argument('--fps', type=int, default=10)
    s.add_argument('--far', type=float, default=50.0)
    s.add_argument('--at', type=float, default=10.0)
    s.set_defaults(func=cmd_animate)

    s = sub.add_parser('timeline', help='whole-traverse profile (for long runs)')
    add_scenario(s)
    s.add_argument('--stride', type=int, default=10, help='scan every Nth frame')
    s.add_argument('--at', type=float, default=15.0,
                   help='lookahead for the section [m]; below ~12 m the crown falls '
                        'outside the vertical field of view')
    s.add_argument('--slab', type=float, default=4.0, help='half-thickness of the slab [m]')
    s.add_argument('--cache', help='path for the cached scan (.npz)')
    s.add_argument('--rescan', action='store_true', help='ignore any cached scan')
    s.set_defaults(func=cmd_timeline)

    s = sub.add_parser('export', help='dump a frame to ply / pcd / npy')
    add_scenario(s)
    s.add_argument('-i', '--index', type=int, default=0)
    s.add_argument('--format', default='ply', choices=['ply', 'pcd', 'npy'])
    s.set_defaults(func=cmd_export)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
