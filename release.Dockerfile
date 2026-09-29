FROM 3d-lidar-dev:latest

ARG USERNAME=ros2user

COPY ./src /home/ws/src

ENV ROS_DOMAIN_ID=42
ENV ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ENV DISPLAY=:0
ENV LIBGL_ALWAYS_SOFTWARE=1

RUN colcon build

USER root
RUN echo "source /home/ws/install/setup.bash" >> /home/$USERNAME/.bashrc
USER $USERNAME
