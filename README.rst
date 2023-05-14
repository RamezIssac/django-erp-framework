.. image:: https://img.shields.io/pypi/v/django-erp-framework.svg
    :target: https://pypi.org/project/django-erp-framework

.. image:: https://img.shields.io/pypi/pyversions/django-erp-framework.svg
    :target: https://pypi.org/project/django-erp-framework

.. image:: https://img.shields.io/readthedocs/django-erp-framework
    :target: https://django-erp-framework.readthedocs.io/

.. image:: https://img.shields.io/codecov/c/github/ra-systems/django-erp-framework
    :target: https://codecov.io/gh/ra-systems/django-erp-framework





Django ERP Framework
====================

A light-weight, effective, Django based framework to create various business applications, resource planing and management systems.

Offers a ready made platform where you can start to create data entry pages and attach various reports to them.

Features
--------

* A Reporting Engine that can generate reports like time series , crosstab , and more. from any model.
* Charting capabilities built in to turn reports into attractive charts.
* Widget system to create dashboards and display bits of the reports results or its charts on any page you want.
* Customizable and easily extensible.
* Django Jazzmin theme ready (& can be used with any django admin theme)
* Python 3.8 / 3.9 / 3.10 , Django 3.2 +



Installation
------------

.. code-block:: console

    $ pip install django-erp-framework


Quick start
-----------

1. Create a virtual environment and install Django Ra ERP from Pypi

    .. code-block:: console

        $ virtualenv venv
        $ source ra-erp/bin/activate
        $ pip install django-erp-framework

Check out the getting started on Read The Docs `Integrating into an existing django project <https://django-erp-framework.readthedocs.io/en/latest/getting_started/index.html>`_


Demo
----

You can checkout a demo application `here <https://my-shop.django-erp-framework.com>`_.

Code is available on `Github <https://github.com/RamezIssac/my-shop>`_.



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

