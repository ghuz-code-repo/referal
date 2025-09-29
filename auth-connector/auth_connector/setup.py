from setuptools import setup, find_packages

setup(
    name="auth-connector",
    version="1.0.0",
    description="Universal authentication and authorization connector for microservices",
    author="Analytics Team",
    packages=find_packages(),
    py_modules=['auth_connector'],
    install_requires=[
        "requests>=2.28.0",
        "PyJWT>=2.4.0",
    ],
    extras_require={
        "flask": ["flask>=2.0.0"],
        "fastapi": ["fastapi>=0.68.0"],
        "django": ["django>=3.2.0"],
    },
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)