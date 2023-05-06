.. image:: https://img.shields.io/pypi/v/django-erp-framework.svg
    :target: https://pypi.org/project/django-erp-framework

.. image:: https://img.shields.io/pypi/pyversions/django-erp-framework.svg
    :target: https://pypi.org/project/django-erp-framework

.. image:: https://img.shields.io/readthedocs/ra-framework
    :target: https://django-erp-framework.readthedocs.io/

.. image:: https://api.travis-ci.org/ra-systems/RA.svg?branch=master
    :target: https://travis-ci.org/ra-systems/django-erp-framework

.. image:: https://img.shields.io/codecov/c/github/ra-systems/django-erp-framework
    :target: https://codecov.io/gh/ra-systems/django-erp-framework





Django ERP Framework
====================

A light-weight, effective, Django based framework to create various business applications, resource planing and management systems.

Offers a ready made platform where you can start to create data entry pages and attach various reports to them.

Features
--------

- Admin theme jazzmin support
- A widget system to display various reports on a page.
- Extendable and customizable
- Python 3.6 / 3.7 / 3.8/ Django 2.2, 3.0 Compatible
- Slick reporting integration for time series reports anf other



Installation
------------

.. code-block:: console

    $ pip install django-erp-framework


Quick start
-----------

1. Create a virtual environment and install Django Ra ERP from Pypi

    .. code-block:: console

        $ virtualenv ra-erp
        $ source ra-erp/bin/activate
        $ pip install django-erp-framework

2. Once installed, Ra provides a command to generate a new project, which would contains all the dependencies needed.

    .. code-block:: console

        $ ra-admin start my_project_name

    You can always integrate Ra to your existing project, it's fairly simple. Here is the guide `Integrating into an existing django project <https://django-erp-framework.readthedocs.io/en/latest/usage/integrating_into_django.html>`_

3. Let's run the preparation commands and get started !

    .. code-block:: console

        $ ./manage.py migrate
        $ ./manage.py createsuperuser
        $ ./manage.py runserver



Documentation
-------------

Available on `Read The Docs <https://django-erp-framework.readthedocs.io/en/latest/>`_

Please Proceed to the tutorial `Create a sales application Part 1 <https://django-erp-framework.readthedocs.io/en/latest/usage/tutorial_1.html>`_


Testing and contribution
------------------------

To run the test suite, first, create and activate a virtual environment. Then
clone the repo, install the test requirements and run the tests::

    # 1. Clone and install requirements
    $ git clone git+git@github.com:ra-systems/django-erp-framework.git
    $ cd tests
    $ python -m pip install -e ..
    $ python -m pip install -r requirements/py3.txt

    # 2. Set the test database connection details in the environment
    $ export DATABASE_NAME=<database name>
    $ export DATABASE_USER=<database user>
    $ export DATABASE_PASSWORD=<database password if any>

    # 3. Run the tests
    $ ./runtests.py
    # And for Coverage report
    $ coverage run --include=../* runtests.py [-k]
    $ coverage html
    

For more information on contributing, we honor `Django's guidelines <https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/unit-tests/>`_.

