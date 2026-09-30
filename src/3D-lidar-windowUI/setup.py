from setuptools import find_packages, setup

package_name = '3D-lidar-windowUI'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=[
        'setuptools',
        'PySide6>=6.6',
        'numpy>=1.26',
        'pyvista>=0.43',
        'pyvistaqt>=0.11',
        'pydantic>=2.5',
        'pytest>=8.0'
    ],
    zip_safe=True,
    maintainer='hackhaton',
    maintainer_email='ebudarin0@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'ui = app.mainwindow:main'
        ],
    },
)
