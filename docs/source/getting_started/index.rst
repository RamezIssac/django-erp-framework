Getting started
===============


Installation
------------

.. code-block:: bat

    $ pip install django-erp-framework

Create an empty project form scratch
------------------------------------

1. Create a virtual environment and install django-erp-framework from Pypi

.. code-block:: bat

    $ mkvirtualenv ra-env (or use `virtualenv ra-env` if you don't have mkvirtualenv)

    $ pip install django-erp-framework

2. Ra provides a command to generate a new project with all needed settings in place.

.. code-block:: bash

    $ ra-admin start project_name

This will create a django project under the directory `project_name`.

3. Run the usual commands needed for any django project

.. code-block:: bash

    $ ./manage.py migrate
    $ ./manage.py createsuperuser
    $ ./manage.py runserver


4. Done !! Your site should now up and running at `http://localhost:8000`. Enter your super user credentials and login.

Integrating into an existing Project
------------------------------------
Please follow to the next section :ref:`integrating_into_django`

Running the tests
-----------------

To run the test suite, first, create and activate a virtual environment. Then
clone the repo, install the test requirements and run the tests::

    $ git clone git+git@github.com:ra-systems/django-erp-framework.git
    $ cd cd ra/tests
    $ python -m pip install -e ..
    $ python -m pip install -r requirements/py3.txt
    $ ./runtests.py
    # For Coverage report
    $ coverage run --include=../* runtests.py [-k]
    $ coverage html


For more information about the test suite and contribution, we honor https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/unit-tests/.



.. toctree::
    :maxdepth: 1

    integrating_into_django
    components


