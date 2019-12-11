Getting started
===============

.. note::
   These instructions assume familiarity with virtual environments and the
   `Django web framework <https://www.djangoproject.com/>`_.

    It also assumes familiarities with basic accounting principles and terms such as double entry , debit and credit , and few other.



Dependencies needed for installation
------------------------------------

* `Python 3 <https://www.python.org/downloads/>`_
* `PostgreSQL <https://www.postgresql.org/download//>`_


Quick install
-------------

Run the following in a virtual environment of your choice:

.. code-block:: console

    $ pip install django-ra
    Or clone repo
    $ pip install git+git@github.com:ra-systems/ra.git@master#egg=django-ra


(Installing outside a virtual environment may require ``sudo``.)

Once installed, Ra provides a command similar to Django's ``django-admin startproject`` to generate a new site/project:

.. code-block:: console

    $ ra-admin start myproject

This will create a new folder ``myproject``, based on a template containing everything you need to get started.

.. note::
    For now, Ra only support Postgresql.
    So you'd need to create a database and assign its name, user & password in `DATABASES` before moving on.

..
  More information on that template is available in
  :doc:`the project template reference </reference/project_template>`.

Inside your ``myproject`` folder, run the setup steps necessary for any Django project:

.. code-block:: console

    $ pip install -r requirements.txt
    $ ./manage.py migrate
    $ ./manage.py createsuperuser
    $ ./manage.py runserver

Your site is now accessible at ``http://localhost:8000``.
Enter your super user credentials and login.


.. toctree::
    :maxdepth: 1
    usseage/tutorial_1
    integrating_into_django