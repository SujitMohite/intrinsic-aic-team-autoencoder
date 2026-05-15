from setuptools import setup

PKG = "data_collection_v2_recorder"

setup(
    name=PKG,
    version="0.1.0",
    packages=[PKG],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{PKG}"]),
        (f"share/{PKG}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="team-autoencoder",
    maintainer_email="smohite@sharkninja.com",
    description="v2 rclpy recorder for AIC keystone data collection",
    license="MIT",
    entry_points={
        "console_scripts": [
            f"recorder_node = {PKG}.recorder_node:main",
        ],
    },
)
