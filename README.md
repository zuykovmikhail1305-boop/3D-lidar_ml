# 3D-lidar_ml

Кросс-платформенное десктопное приложение для визуализации облака точек LiDAR (тоннель метро) и отображения вероятностей препятствий на дистанциях 300 / 200 / 100 м от ML-модели.

# Инструкция по запуску
Контейнер с готовым решением можно запустить двумя способами. Первый — развертывание окружения для разработки. Оно предназначается только для разработки решения. Рекомендуется использовать второй способ, а именно запуск готового образа. После запуска откроется приложение, в котором нужно будет нажать кнопку "Стрим". После чего можно начинать воспроизводить bag файл.
**Важно: модель-детектор и приложение работают в 42 ROS DOMAIN ID**

## Окружение для разработки
Чтобы запустить решение необходимо выполнить следующие команды в корне проекта:
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
Для запуска модели-детектора нужно выполнить:
```bash
ros2 run model model
```
Для запуска модели-детектора нужно выполнить:
```bash
ros2 run 3D-lidar-windowUI ui
```

## Сборка готового образа
Другой способ запуска контейнера — это сборка и последующий запуск образа, содержащего в себе все необходимое для работы модели-детектора и графического приложения визуализации.
```bash
docker build -t 3d-lidar-dev --build-arg USERNAME=<USERNAME> --build-arg USER_UID=<USER_UID> .
docker build -f release.Dockerfile -t 3d-lidar-release --build-arg USERNAME=<USERNAME> --build-arg USER_UID=<USER_UID> .
```
Вместо &lt;USERNAME&gt; и &lt;USER_UID&gt; рекомендуется подставить имя текущего пользователя и его uid соответственно во избежания конфликтов прав доступа.

## Запуск готового образа
Для того чтобы запустить контейнер из готового образа, необходимо выполнить следующие команду:
```bash
docker run -it --network host --ipc host --pid host --device /dev/dri:/dev/dri -v /tmp/.X11-unix:/tmp/.X11-unix 3d-lidar-release:latest
ros2 run model model & ros2 run 3D-lidar-windowUI ui
```

# Описание проекта

## Структура проекта

| Путь | Назначение |
|---|---|
| [`model/model`](src/model/model) | Исходный код детектора |
| [`3D-lidar-windowUI/app`](src/3D-lidar-windowUI/app) | Исходный код приложения (PySide6) |
| [`3D-lidar-windowUI/form.ui/app`](src/3D-lidar-windowUI/app/form.ui) | Компоновка окна (Qt Designer), источник истины для `ui_form.py` |
| [`3D-lidar-windowUI/mainwindow.py/app`](src/3D-lidar-windowUI/app/mainwindow.py) | Главное окно: карточки зон, таблица, тёмная тема, демо-стрим |
| [`3D-lidar-windowUI/zonetable_model.py/app`](src/3D-lidar-windowUI/app/zonetable_model.py) | `QAbstractTableModel` — источник истины вероятностей |
| [`3D-lidar-windowUI/core/constants.py/app`](src/3D-lidar-windowUI/app/core/constants.py) | Пороги, статусы, цвета (чистая логика) |
