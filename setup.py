"""Setup script for MSR-Scientist."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme = Path("README.md").read_text(encoding="utf-8") if Path("README.md").exists() else ""

setup(
    name="msr-scientist",
    version="0.1.0",
    description="A minimalist self-evolving researcher agent",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="MSR-Scientist Contributors",
    url="https://github.com/zhimin-z/MSR-Scientist",
    packages=find_packages(),
    install_requires=[
        "openai>=1.0.0",
        "anthropic>=0.18.0",
    ],
    extras_require={
        "latex": ["pylatex>=1.4.0"],
    },
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "msr-scientist=msr_scientist.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
