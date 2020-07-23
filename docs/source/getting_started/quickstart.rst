Quick Start
===========

Installation
------------

.. code-block:: console

    $ pip install django-ra-erp

Create your first Ra project
-----------------------------

1. Create a virtual environment and install ra-framework from Pypi

.. code-block::console

    $ mkvirtualenv ra-env (or use `virtualenv ra-env` if you don't have mkvirtualenv)
    $ pip install django-ra-erp

2. Once Ra installed, it provides a command to generate a new project.

.. code-block:: console

    $ ra-admin start myproject

This will create a new project folder `myproject`, based on a template containing everything you need to get started.
You can always integrate ra framework to your existing project, please refer to :ref:`integrating_into_django`

3. Run the usual commands needed for any django project

.. code-block:: console

    $ ./manage.py migrate
    $ ./manage.py createsuperuser
    $ ./manage.py runserver


4. Voila !! Your site should now up and running at `http://localhost:8000`. Enter your super user credentials and login.

5. As soon as you're done with the tutorial, you'll be seeing something like this

.. image:: https://rasystems.io/static/images/raframework/dashboard.png
    :target: https://rasystems.io/static/images/raframework/dashboard.png
    :alt: Landing Ra framework Dashboard


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

