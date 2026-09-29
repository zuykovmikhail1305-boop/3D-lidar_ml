r"""
Перенос весов из обучения в artifacts/model.pt - только сама модель, без оптимизатора.

    python export_weights.py ..\runs_unet\epoch_005_train_loss_0.0312.pt

Файл эпохи из train_unet.py весит ~93 МБ: в нём ещё состояние оптимизатора и
расписания. Для прогона нужна только модель - ~31 МБ. Старый model.pt
сохраняется как model.pt.bak.

После смены весов пересчитайте карту привычек модели:

    python calibrate.py <запись>

Зависимости: torch.
"""

import argparse
import os
import shutil

import torch

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("weights", help="файл эпохи из runs_unet")
    p.add_argument("--out", default=os.path.join(HERE, "artifacts", "model.pt"))
    args = p.parse_args()

    ck = torch.load(args.weights, map_location="cpu")
    slim = {"model": {k: v.float() for k, v in ck["model"].items()},
            "base": ck.get("base") or ck.get("args", {}).get("base", 32),
            "epoch": ck.get("epoch"), "source": os.path.basename(args.weights), "train": ck.get("train")}
    if os.path.exists(args.out):
        shutil.copy2(args.out, args.out + ".bak")
    torch.save(slim, args.out)
    print("эпоха %s -> %s (%.1f МБ)" % (slim["epoch"], args.out, os.path.getsize(args.out) / 1e6))
    print("не забудьте: python calibrate.py <запись> - карта привычек у каждой модели своя")


if __name__ == "__main__":
    main()
