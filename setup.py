"""Sovereign Vision - package setup.

Installs the `sovereign` core package and the `dashboard` / `demo` modules
in editable mode so judges can run the demo immediately after `pip install -e .`.
"""
from __future__ import annotations

from pathlib import Path

from setuptools import find_packages, setup

HERE = Path(__file__).parent
README = (HERE / "README.md").read_text(encoding="utf-8") if (HERE / "README.md").exists() else ""

setup(
    name="sovereign-vision",
    version="1.0.0",
    description=(
        "The first on-device enterprise vision system that is "
        "GDPR-compliant by design, not by policy."
    ),
    long_description=README,
    long_description_content_type="text/markdown",
    author="Karthik Barma",
    author_email="karthik@thebarmaeffect.dev",
    url="https://github.com/TheBarmaEffect/sovereign-vision",
    license="AGPL-3.0",
    python_requires=">=3.10",
    packages=find_packages(exclude=("tests", "tests.*", "demo", "demo.*")),
    include_package_data=True,
    install_requires=[
        "numpy>=2.0",
        "opencv-python>=4.10",
        "Pillow>=10.0",
        "rich>=13.0",
        "pydantic>=2.0",
        "structlog>=24.0",
    ],
    extras_require={
        "mlx": ["mlx>=0.18"],
        "dev": ["pytest>=8.0", "pytest-cov>=5.0", "ruff>=0.8", "mypy>=1.13"],
    },
    entry_points={
        "console_scripts": [
            "sovereign-vision=demo.run_demo:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Legal Industry",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: MacOS",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Security",
    ],
    keywords=[
        "computer-vision",
        "yolo",
        "mlx",
        "apple-silicon",
        "privacy",
        "gdpr",
        "constitutional-ai",
        "on-device",
        "enterprise",
    ],
)
