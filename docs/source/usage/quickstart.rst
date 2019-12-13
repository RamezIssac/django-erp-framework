Getting started
===============

.. note::
   These instructions assume familiarity with virtual environments , the
   `Django web framework <https://www.djangoproject.com/>`_ and setting up an `PostgreSQL <https://www.postgresql.org/download//>`_ database.

   It also assumes familiarities with some basic accounting principles and terms such as double entry , debit and credit , and few other.



Dependencies
------------

* `Python 3 <https://www.python.org/downloads/>`_
* `PostgreSQL <https://www.postgresql.org/download//>`_


Quick install
-------------

1. Create a virtual environment and install ra-framework from github repository.

.. code-block:: console

    $ pip install git+git@github.com:ra-systems/ra.git@master#egg=django-ra
      Or over https
    $ pip install git+https://github.com/ra-systems/RA.git



2. Once Ra installed, it provides a command to generate a new project.

.. code-block:: console

    $ ra-admin start myproject

This will create a new folder `myproject`, based on a template containing everything you need to get started.
You can always integrate ra framework to your existing project, please refer to :ref:`integrating_into_django`

3. Database

   .. note::
    Ra only support Postgresql.

    As Django's `QuerySet.distinct(*fields) <https://docs.djangoproject.com/en/2.2/ref/models/querysets/#django.db.models.query.QuerySet.distinct>`_ is supported only on Postgres.
    ``distinct(*fields)`` is used by the reporting engine.

Create a postgres database, and assign its details to ``DATABASES`` setting

4. Run the usual comamnds needed for any django project

.. code-block:: console

    $ ./manage.py migrate
    $ ./manage.py createsuperuser
    $ ./manage.py runserver


5. Voila !! Your site should now up and running at `http://localhost:8000`. Enter your super user credentials and login.




.. toctree::
    :maxdepth: 1
    usseage/tutorial_1
    integrating_into_django