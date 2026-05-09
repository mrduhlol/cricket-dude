from setuptools import setup

setup(
    name="cricket-dude",

    version="1.5.0",

    description=(
        "Retro live cricket terminal "
        "with real-time scores and commentary"
    ),

    author="mrdhulol",

    py_modules=["cricket_dude"],

    install_requires=[
        "rich>=13.0.0",
        "requests>=2.28.0",
    ],

    entry_points={
        "console_scripts": [
            "cricket-dude=cricket_dude:main",
        ],
    },

    python_requires=">=3.9",

    keywords=[
        "cricket",
        "terminal",
        "tui",
        "live-score",
        "cli",
    ],

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)