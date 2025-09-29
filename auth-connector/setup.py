from setuptools import setup, find_packages

setup(
    name="auth-connector",
    version="1.0.0",
    author="Analytics Team",
    description="Universal authentication module for microservices",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28.0",
        "PyJWT>=2.4.0",
        "Flask>=2.0.0",
    ],
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)