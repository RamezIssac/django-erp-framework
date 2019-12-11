# Ra Framework

Work in Progress

A framework to create business application, erp solutions with comprehensible UI and strong reporting mechanism.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes. See deployment for notes on how to deploy the project on a live system.

### Prerequisites

PostgresSql server database up and running.

### Installing

A full documentation is available on  /docs/quickstart 
A quick version
```
pip install -e git+git@github.com:ra-systems/ra.git@master#egg=django-ra
django-admin startproject myproject
```


## Running the docs
To build the docs you'd need sphinx installed, either on your system or on the 
virtualEnv `pip install -U sphinx` 
https://www.sphinx-doc.org/en/master/usage/installation.html

    $ pip install sphinx_rtd_theme
    $ cd docs/
    $ sphinx-build source build -b html

    

## Running the tests

To run the test suite, first, create and activate a virtual environment. Then
install some requirements and run the tests::

    $ cd tests
    $ python -m pip install -e ..
    $ python -m pip install -r requirements/py3.txt
    $ ./runtests.py
    # For Coverage report
    $ coverage run --include=../* runtests.py 
    

For more information about the test suite, see
https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/unit-tests/.
