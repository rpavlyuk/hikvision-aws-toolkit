"""The setup script."""
from setuptools import setup, Extension, find_packages

with open('README.md') as readme_file:
    readme = readme_file.read()

requirements = [ 'boto3' ]

setup_requirements = [ ]

test_requirements = [ ]

exec_scripts=['scripts/hk-aws-tool.py']

setup(
    author="Roman Pavlyuk",
    author_email='roman.pavlyuk@gmail.com',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GPL v3.0',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.7',
    ],
    description='A set of tools to manage files stored by Hikvision devices on the file share',
    install_requires=requirements,
    license='GPLv3',
    long_description=readme,
    include_package_data=True,
    long_description_content_type="text/markdown",
    keywords='hikvision camera aws python cgi interface',
    name='hkawstoolkit',
    packages=['hkawstoolkit'],
    setup_requires=setup_requirements,
    url='https://github.com/rpavlyuk/hikvision-aws-toolkit',
    version='1.0',
    zip_safe=False,
    scripts=exec_scripts
)