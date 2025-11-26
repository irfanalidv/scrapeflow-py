from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="scrapeflow-py",
    version="0.1.1",
    author="Irfan Ali",
    description="An opinionated scraping workflow engine built on Playwright",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/irfanalidv/scrapeflow-py",
    license="MIT",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "playwright>=1.40.0",
        "aiohttp>=3.9.0",
        "tenacity>=8.2.0",
    ],
    include_package_data=True,
)

