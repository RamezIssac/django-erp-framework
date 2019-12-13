Ra Framework
============

*Work in Progress*

A light-weight effective Django based framework to create business application and various resource planing systems,
equipped with a reporting engine and a responsive dashboard.


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
You can always integrate ra framework to your existing project, please refer to :ref:`integrating_into_django`

3. Database

.. note::

    Ra only support Postgresql.

    As Django's `QuerySet.distinct(*fields) <https://docs.djangoproject.com/en/2.2/ref/models/querysets/#django.db.models.query.QuerySet.distinct>`_ is supported only on Postgres.
    ``distinct(*fields)`` is used by the reporting engine.

Create a postgres database, and assign its details to ``DATABASES`` setting

4. Run the usual commands needed for any django project

.. code-block:: console

    $ ./manage.py migrate
    $ ./manage.py createsuperuser
    $ ./manage.py runserver


5. Voila !! Your site should now up and running at `http://localhost:8000`. Enter your super user credentials and login.

.. image:: docs/images/dashboard.png


Documentation
-------------

Available on `Read The Docs <https://ra-framework.readthedocs.io/en/latest/>`_

Please Proceed to the tutorial `*Create a sales application Part 1 <https://ra-framework.readthedocs.io/en/latest/usage/tutorial_1.html>`_


Running the tests
-----------------

To run the test suite, first, create and activate a virtual environment. Then
clone the repo, install the test requirements and run the tests::

    $ git clone git+git@github.com:ra-systems/RA.git
    $ cd cd ra/tests
    $ python -m pip install -e ..
    $ python -m pip install -r requirements/py3.txt
    $ ./runtests.py
    # For Coverage report
    $ coverage run --include=../* runtests.py [-k]
    $ coverage html
    

For more information about the test suite and contribution, we honor https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/unit-tests/.
