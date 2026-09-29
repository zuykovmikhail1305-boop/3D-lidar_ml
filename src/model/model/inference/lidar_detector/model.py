"""
U-Net восстановления развёртки лидара: архитектура и прогон одного кадра.

Архитектура и подготовка входа - те же, что при обучении (train_unet.py в
корне репозитория), иначе веса не подойдут. Менять здесь что-то можно только
вместе с обучением.

Вход сети - 4 канала картинки 128 x 1024:

    дальность      log(1 + r) / log(1 + 250), 0 где пусто
    интенсивность  / 255, 0 где пусто
    занятость      1, если во входе есть точка
    заполнение     пустые пиксели залиты ближайшей точкой слева в том же луче

Выход - 3 канала: поправка дальности к входу (или к заполнению в пустых
пикселях), логит «здесь должна быть точка», логит «входная точка - мусор».

Зависимости: torch, numpy.
"""

import math

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

R_MAX = 250.0
LOG_MAX = math.log1p(R_MAX)


def to_norm(r):
    return torch.log1p(r) / LOG_MAX


def to_metres(n):
    # ограничение обязательно: exp раздувает любую ошибку сети
    return torch.expm1(n.clamp(0.0, 1.0) * LOG_MAX)


def left_fill(r):
    """Каждому пустому пикселю - ближайшая точка слева в том же луче."""
    b, h, w = r.shape
    idx = torch.arange(w, device=r.device).expand(b, h, w)
    idx = torch.where(r > 0, idx, torch.zeros_like(idx))
    idx = torch.cummax(idx, dim=-1).values
    return torch.gather(r, -1, idx)


class Block(nn.Module):
    def __init__(self, c_in, c_out):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(c_in, c_out, 3, padding=1, bias=False), nn.BatchNorm2d(c_out), nn.ReLU(inplace=True),
            nn.Conv2d(c_out, c_out, 3, padding=1, bias=False), nn.BatchNorm2d(c_out), nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.net(x)


class UNet(nn.Module):
    """U-Net на 4 уровня: 128 x 1024 -> 8 x 64 в самом низу."""

    def __init__(self, c_in=4, c_out=3, base=32):
        super().__init__()
        ch = [base, base * 2, base * 4, base * 8, base * 16]
        self.down = nn.ModuleList()
        prev = c_in
        for c in ch:
            self.down.append(Block(prev, c))
            prev = c
        self.up = nn.ModuleList()
        self.up_conv = nn.ModuleList()
        for c_hi, c_lo in zip(ch[::-1][:-1], ch[::-1][1:]):
            self.up.append(nn.ConvTranspose2d(c_hi, c_lo, 2, stride=2))
            self.up_conv.append(Block(c_lo * 2, c_lo))
        self.head = nn.Conv2d(ch[0], c_out, 1)

    def forward(self, x):
        skips = []
        for i, blk in enumerate(self.down):
            x = blk(x)
            if i < len(self.down) - 1:
                skips.append(x)
                x = F.max_pool2d(x, 2)
        for up, conv, skip in zip(self.up, self.up_conv, skips[::-1]):
            x = conv(torch.cat([up(x), skip], dim=1))
        return self.head(x)


def load_model(path, device=None):
    """Файл весов -> (модель в режиме eval, устройство, описание весов).

    Понимает и облегчённый файл из artifacts/ ({"model", "base", ...}), и полный
    файл эпохи из обучения ({"model", "opt", "args": {"base"}, ...}).
    """
    device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
    ck = torch.load(path, map_location=device)
    base = ck.get("base") or ck.get("args", {}).get("base", 32)
    model = UNet(4, 3, base).to(device).eval()
    model.load_state_dict(ck["model"])
    meta = {k: v for k, v in ck.items() if k not in ("model", "opt", "sched")}
    return model, device, meta


@torch.no_grad()
def restore(model, device, r_in, i_in):
    """Прогон кадров через сеть.

    r_in - дальность входа, м (кадров, 128, 1024) или (128, 1024), 0 - пусто;
    i_in - интенсивность 0..255 той же формы.
    Возвращает numpy той же формы: дальность ответа модели, м (0 - точки нет),
    вероятность «точка есть», вероятность «входная точка - мусор».
    """
    single = np.ndim(r_in) == 2
    r = torch.as_tensor(np.asarray(r_in, np.float32), device=device)
    it = torch.as_tensor(np.asarray(i_in, np.float32), device=device) / 255.0
    if single:
        r, it = r[None], it[None]
    valid = (r > 0).float()
    x = torch.stack([to_norm(r) * valid, it * valid, valid, to_norm(left_fill(r))], dim=1)
    out = model(x).float()
    # сеть предсказывает поправку к базе: к входу, где точка есть, и к заполнению, где её нет
    rng = torch.where(valid > 0, x[:, 0], x[:, 3]) + out[:, 0]
    occ = torch.sigmoid(out[:, 1])
    junk = torch.sigmoid(out[:, 2]) * valid
    keep = (occ > 0.5) & ~((junk > 0.5) & (valid > 0))
    r_out = torch.where(keep, to_metres(rng), torch.zeros_like(rng))
    res = [t.cpu().numpy() for t in (r_out, occ, junk)]
    return tuple(a[0] for a in res) if single else tuple(res)
