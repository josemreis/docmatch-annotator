
from setuptools import setup, find_packages
from io import open
from os import path
import pathlib
# The directory containing this file
HERE = pathlib.Path(__file__).parent
# The text of the README file
README = (HERE / "README.md").read_text()
# automatically captured required modules for install_requires in requirements.txt and as well as configure dependency links
with open(path.join(HERE, 'requirements.txt'), encoding='utf-8') as f:
    all_reqs = f.read().split('\n')
install_requires = [x.strip() for x in all_reqs if ('git+' not in x) and (
    not x.startswith('#')) and (not x.startswith('-'))]
dependency_links = [x.strip().replace('git+', '') for x in all_reqs \
                    if 'git+' not in x]

setup(
 name = 'docmatch-annotator',
 description = 'A simple document matching annotation framework using only csv files, a text editor, and a terminal window',
 version = '0.0.1',
 packages = find_packages(), # list of all packages
 install_requires = install_requires,
 python_requires='>=2.7', # any python greater than 2.7
 entry_points={
     'console_scripts': [
         'docmatch-annotator=docmatch_annotator:main'
     ]
},
author="José Reis",
long_description=README,
long_description_content_type="text/markdown",
url='https://github.com/josemreis/docmatch-annotator',
dependency_links=dependency_links
)