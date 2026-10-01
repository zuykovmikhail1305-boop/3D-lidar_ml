# 3D-lidar_ml

Кросс-платформенное десктопное приложение для визуализации облака точек LiDAR (тоннель метро) и отображения вероятностей препятствий на дистанциях 300 / 200 / 100 м от ML-модели.

# Инструкция по запуску
Контейнер с готовым решением можно запустить двумя способами. Первый — развертывание окружения для разработки. Оно предназначается только для разработки решения. Рекомендуется использовать второй способ, а именно запуск готового образа.
**Важно: модель-детектор и приложение работают в 42 ROS DOMAIN ID**

## Окружение для разработки
Чтобы запустить решение необходимо выполнить следующие комманды в корне проекта:
```bash
docker compose up -d
docker compose attach ros2
```
Затем внутри контейнера необходимо установить зависимости и собрать проект:
```bash
rosdep update
rosdep install --from-paths src --ignore-src -r -y
pip install pyvistaqt
colcon build
source install/setup.bash
```
Для запуска модели-детектора нунжно выполнить:
```bash
ros2 run model model
```
Для запуска модели-детектора нунжно выполнить:
```bash
ros2 run 3D-lidar-windowUI ui
```

## Сборка готового образа
Другой способ запуска контейнера — это сборка и последующий запуск образа, содержащего в себе все необходимое для работы модели-детектора и графического приложения визуализации.
```bash
docker build -t 3d-lidar-dev --build-arg USERNAME=<USERNAME> --build-arg USER_UID=<USER_UID> .
docker build -f release.Dockerfile -t 3d-lidar-release --build-arg USERNAME=<USERNAME> --build-arg USER_UID=<USER_UID> .
```
Вместо <USERNAME> и <USER_UID> рекомендуется подставить имя пользователя и его uid соответственно во избежания конфликтов прав доступа.

## Запуск готового образа
Для того чтобы запустить контейнер из готового образа, необходимо выполнить следующие комманду:
```bash
docker run -it --network host --ipc host --pid host -v /tmp/.X11-unix:/tmp/.X11-unix 3d-lidar-release:latest
ros2 run model model & ros2 run 3D-lidar-windowUI ui
```

# Описание проекта

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
