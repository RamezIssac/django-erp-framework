import os

from setuptools import setup

# exec(open('ra/version.py').read())

README = open(os.path.join(os.path.dirname(__file__), 'README.md')).read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

# class build_with_submodules(install):
# def run(self):
# if path.exists('.git'):
#             check_call(['git', 'submodule', 'init'])
#             check_call(['git', 'submodule', 'update'])
#         install.run(self)


setup(
    name='django-ra',
    version='0.0.5',
    packages=['ra'],
    include_package_data=True,
    # cmdclass={
    #     'install': build_with_submodules,
    # },
    license='AGPLv3 License',
    description='A Framework to record, monitor and analyze business accounts,  batteries included.',
    long_description=README,
    url='http://rasystems.io/',
    author='Ramez Issac',
    author_email='ramez@rasystems.io',
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Framework :: Django',
        'Framework :: Django :: 2.0',
        'Framework :: Django :: 2.1',
        'Framework :: Django :: 2.2',
        'Framework :: Wagtail',
        'Topic :: Internet :: WWW/HTTP :: Site Management',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    install_requires=['docutils>=0.3',
                      'pytz',
                      'django==2.2.7',
                      'psycopg2-binary',
                      'simplejson',
                      'django-crequest==2018.5.11',
                      'django-tabular-permissions==2.3',
                      'django-select2==7.1.1',
                      'django-crispy-forms==1.8.0',
                      'dateutils==0.6.7',
                      'django-mptt==0.10.0',
                      'unicodecsv==0.14.1',
                      'django-braces==1.13',
                      'django-compressor==2.3',
                      'swapper==1.1.1',

                      'python-memcached',
                      'django-reversion>=3.0',
                      'django-session-security', 'Pillow',
                      ],

    entry_points={
        'console_scripts': ['ra-admin=ra.project_template.ra:main'],
    }

)
