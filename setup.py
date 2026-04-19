from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="aeoru_ai",
    version="0.1.0",
    description="AI Assistant for ERPNext - Natural language CRUD operations",
    author="Aeoru",
    author_email="dev@aeoru.io",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
