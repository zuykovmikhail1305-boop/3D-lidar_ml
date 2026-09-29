# 3D-lidar_ml

Кросс-платформенное десктопное приложение для визуализации облака точек LiDAR (тоннель метро) и отображения вероятностей препятствий на дистанциях 300 / 200 / 100 м от ML-модели.

## Структура проекта

| Путь | Назначение |
|---|---|
| [`plans/architecture.md`](plans/architecture.md) | Архитектура и план имплементации |
| [`3D-lidar-windowUI/`](3D-lidar-windowUI/) | Исходный код приложения (PySide6) |
| [`3D-lidar-windowUI/form.ui`](3D-lidar-windowUI/form.ui) | Компоновка окна (Qt Designer), источник истины для `ui_form.py` |
| [`3D-lidar-windowUI/mainwindow.py`](3D-lidar-windowUI/mainwindow.py) | Главное окно: карточки зон, таблица, тёмная тема, демо-стрим |
| [`3D-lidar-windowUI/zonetable_model.py`](3D-lidar-windowUI/zonetable_model.py) | `QAbstractTableModel` — источник истины вероятностей |
| [`3D-lidar-windowUI/core/constants.py`](3D-lidar-windowUI/core/constants.py) | Пороги, статусы, цвета (чистая логика) |

## Установка (Фаза 0)

```powershell
cd 3D-lidar-windowUI
py -3.11 -m venv .venv          # или другой Python >= 3.10
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## Запуск (Фаза 1)

```powershell
cd 3D-lidar-windowUI
.venv\Scripts\python.exe mainwindow.py
```

- **«▶ Стрим»** — запускает временный демо-поток: mock-вероятности обновляют карточки зон и таблицу каждую секунду (в Фазе 5 будет заменён на `MLDataSource`).
- Справа — контейнер под 3D-вьюпорт (PyVista/`QtInteractor` появится в Фазе 3).

Смоук-тест без GUI (генерирует `_smoke_preview.png`):

```powershell
.venv\Scripts\python.exe -m _smoke_test
```

## Статус реализации

- [x] Фаза 0 — окружение и зависимости
- [x] Фаза 1 — каркас UI (карточки зон, таблица, тёмная тема)
- [ ] Фаза 2 — слой данных (парсеры PCD/PLY/KITTI, синтетический тоннель, тесты)
- [ ] Фаза 3 — 3D-рендеринг облака точек (PyVista)
- [ ] Фаза 4 — зоны 100/200/300 м и оверлеи препятствий
- [ ] Фаза 5 — ML-интеграция (контракт JSON, `ObstacleMonitor`)
- [ ] Фаза 6 — потоки и стриминг
- [ ] Фаза 7 — полировка и упаковка (PyInstaller)