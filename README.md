# 3D-lidar_ml

Кросс-платформенное десктопное приложение для визуализации облака точек LiDAR (тоннель метро) и отображения вероятностей препятствий на дистанциях 300 / 200 / 100 м от ML-модели.

## Структура проекта

| Путь | Назначение |
|---|---|
| [`plans/architecture.md`](plans/architecture.md) | Архитектура и план имплементации |
| [`3D-lidar-windowUI/`](3D-lidar-windowUI/) | Исходный код приложения (PySide6) |
| [`3D-lidar-windowUI/form.ui`](3D-lidar-windowUI/form.ui) | Компоновка окна (Qt Designer), источник истины для `ui_form.py` |
| [`3D-lidar-windowUI/mainwindow.py`](3D-lidar-windowUI/mainwindow.py) | Главное окно: карточки зон, таблица, тёмная тема, демо-стрим, интеграция рендера |
| [`3D-lidar-windowUI/zonetable_model.py`](3D-lidar-windowUI/zonetable_model.py) | `QAbstractTableModel` — источник истины вероятностей |
| [`3D-lidar-windowUI/core/constants.py`](3D-lidar-windowUI/core/constants.py) | Пороги, статусы, цвета (чистая логика) |
| [`3D-lidar-windowUI/data/frame.py`](3D-lidar-windowUI/data/frame.py) | `PointCloudFrame` — контейнер скана LiDAR |
| [`3D-lidar-windowUI/data/processor.py`](3D-lidar-windowUI/data/processor.py) | Воксельный фильтр, децимация, раскраска (NumPy) |
| [`3D-lidar-windowUI/data/sources.py`](3D-lidar-windowUI/data/sources.py) | Загрузчики PCD/PLY/KITTI, синтетический тоннель |
| [`3D-lidar-windowUI/rendering/pointcloud_renderer.py`](3D-lidar-windowUI/rendering/pointcloud_renderer.py) | PyVista-рендерер: QtInteractor, колоризация, камеры, FPS |
| [`3D-lidar-windowUI/samples/tunnel_300m.pcd`](3D-lidar-windowUI/samples/tunnel_300m.pcd) | Сгенерированный пример облака тоннеля (364k точек) |
| [`3D-lidar-windowUI/samples/tunnel_preview.png`](3D-lidar-windowUI/samples/tunnel_preview.png) | Offscreen-рендер этого облака (turbo по дистанции) |

## Установка (Фаза 0)

```powershell
cd 3D-lidar-windowUI
py -3.11 -m venv .venv          # или другой Python >= 3.10
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## Запуск

```powershell
cd 3D-lidar-windowUI
.venv\Scripts\python.exe mainwindow.py
```

- **«▶ Стрим»** — временный демо-поток: mock-вероятности обновляют карточки зон и таблицу каждую секунду (в Фазе 5 будет заменён на `MLDataSource`).
- **«Открыть файл»** (или меню «Файл → Открыть облако точек…») загружает `.pcd` / `.ply` / `.bin` (KITTI), применяет воксельный фильтр (ползунок «Воксель, м») и отображает облако в 3D-вьюпорте справа.

Возможности 3D-вьюпорта (Фаза 3):
- вращение / зум / панорама мышью (орбитальная камера);
- раскраска по расстоянию / интенсивности / высоте (переключатели в панели слева);
- меню «Вид»: сброс камеры, фронт, сверху; пол и оси координат;
- счётчик FPS и число точек в статус-баре.

## Тесты и инструменты

Юнит-тесты слоя данных (23 шт.):

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

Смоук-тест без GUI (генерирует `_smoke_preview.png`, проверяет карточки, таблицу, рендерер):

```powershell
.venv\Scripts\python.exe -m _smoke_test
```

Сгенерировать пример облака тоннеля (PCD, 300 м, препятствие на 280 м) вместе с offscreen-превью:

```powershell
.venv\Scripts\python.exe samples\generate_sample_tunnel.py
```

## Статус реализации

- [x] Фаза 0 — окружение и зависимости
- [x] Фаза 1 — каркас UI (карточки зон, таблица, тёмная тема)
- [x] Фаза 2 — слой данных (парсеры PCD/PLY/KITTI, синтетический тоннель, тесты)
- [x] Фаза 3 — 3D-рендеринг облака точек (PyVista)
- [ ] Фаза 4 — зоны 100/200/300 м и оверлеи препятствий
- [ ] Фаза 5 — ML-интеграция (контракт JSON, `ObstacleMonitor`)
- [ ] Фаза 6 — потоки и стриминг
- [ ] Фаза 7 — полировка и упаковка (PyInstaller)