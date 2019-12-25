.. image:: https://img.shields.io/pypi/v/django-ra.svg
    :target: https://pypi.org/project/django-ra

.. image:: https://img.shields.io/pypi/pyversions/django-ra.svg
    :target: https://pypi.org/project/django-ra

.. image:: https://img.shields.io/readthedocs/ra-framework
    :target: https://ra-framework.readthedocs.io/

.. image:: https://api.travis-ci.org/ra-systems/RA.svg?branch=master
    :target: https://travis-ci.org/ra-systems/RA

.. image:: https://img.shields.io/codecov/c/github/ra-systems/RA
    :target: https://codecov.io/gh/ra-systems/RA



Ra Framework
============

A light-weight effective Django based framework to create business application and various resource planing systems,
equipped with a reporting engine and a responsive dashboard.

Features
--------

- A responsive dashboard built on top of Django's admin.
- Reporting Engine that filters and compute several types of reports with simple lines of code.
- A charting capabilities to turn reports into attractive charts.
- A widget system to display reports and its charts on dashboard home , or on object's `view` pages.
- Tools and goodies to extend and customize the framework behavior from top to bottom.
- Python 3.6 / 3.7 / 3.8
- Django 2.2, 3.0 Compatible


Dependencies
------------
* `Python 3 <https://www.python.org/downloads/>`_
* `PostgreSQL <https://www.postgresql.org/download//>`_


Installation
------------

.. code-block:: console

    $ pip install django-ra


Quick start
-----------

1. Create a virtual environment and install ra-framework from Pypi

    .. code-block:: console

        $ pip install django-ra

2. Once Ra installed, it provides a command to generate a new project.

    .. code-block:: console

        $ ra-admin start myproject

    This will create a new project folder `myproject`, based on a template containing everything you need to get started.
    You can always integrate ra framework to your existing project, please refer to the docs `Integrating into an existing django project <https://ra-framework.readthedocs.io/en/latest/usage/integrating_into_django.html>`_

3. Create a postgres database, and assign its details to ``DATABASES`` setting

    .. note::

        Ra only support Postgresql.

        As Django's `QuerySet.distinct(*fields) <https://docs.djangoproject.com/en/2.2/ref/models/querysets/#django.db.models.query.QuerySet.distinct>`_ is supported only on Postgres.
        ``distinct(*fields)`` is used by the reporting engine.


4. Run the usual commands needed for any django project

    .. code-block:: console

        $ ./manage.py migrate
        $ ./manage.py createsuperuser
        $ ./manage.py runserver


5. Voila!! Your site should now up and running at `http://localhost:8000`. Enter your super user credentials and login.

.. image:: https://rasystems.io/static/images/raframework/dashboard.png
    :target: https://rasystems.io/static/images/raframework/dashboard.png
    :alt: Landing Ra framework Dashboard


Documentation
-------------

Available on `Read The Docs <https://ra-framework.readthedocs.io/en/latest/>`_

Please Proceed to the tutorial `Create a sales application Part 1 <https://ra-framework.readthedocs.io/en/latest/usage/tutorial_1.html>`_


Testing and contribution
------------------------

To run the test suite, first, create and activate a virtual environment. Then
clone the repo, install the test requirements and run the tests::

    # 1. Clone and install requirements
    $ git clone git+git@github.com:ra-systems/RA.git
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

