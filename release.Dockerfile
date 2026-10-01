FROM 3d-lidar-dev:latest

ARG USERNAME=ros2user
ARG USER_UID=1000
ARG USER_GID=$USER_UID

COPY --chown=$USER_UID:$USER_GID ./src /home/ws/src

ENV ROS_DOMAIN_ID=42
ENV ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ENV DISPLAY=:0
ENV LIBGL_ALWAYS_SOFTWARE=1
ENV QT_API=pyside6
ENV QT_QPA_PLATFORM=xcb

RUN rosdep update
RUN rosdep install --from-paths src --ignore-src -r -y
RUN pip install pyvistaqt
RUN colcon build

USER root
RUN echo "source /home/ws/install/setup.bash" >> /home/$USERNAME/.bashrc
USER $USERNAME
