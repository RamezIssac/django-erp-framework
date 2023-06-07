# Changelog
All notable changes to this project are/will be documented in this file.

## [1.5.2] - 2023-06-07
- Added Jazzmin integration as an option
- Added settings for custom dashboard base template, admin_site_access_permission, report_access_function 
- Simplified creating a widget for a report
- Simplified integrating erp framework with your project
- Align own ReportView to Slick Reporting ReportView
- Removed ReportList View, top_search app, and unused js plugins
- Changed report URL to be app_label/report_lug
- Enhanced demo app and documentation

## [1.5.0] - 2023-05-28
- A makeover and renaming the project to django-erp-framework.


## [1.2.0] - 2020-11-24
- Update slick_reporting to version >= 0.4

## [1.1.1]
# Updated
- Fixed duplicated `jazzmin` in installed apps in the project skeleton

## [1.1.0]
# Updated
- Fixed issues with documentation and project skeleton.

## [1.0.0]
#Added
- Reporting Engine is moved to its own new package [Slick Reporting](https://github.com/ra-systems/django-slick-reporting).   
- Framework no longer depends Postgres Database specifically.
- Update underlying AdminLTE Theme to 3.0.5  


## [v0.1.1] - 2020-01-12
### Added
- Documentation for Ra Settings
- Removal of unneeded css styles, correcting GitHub linguist
- Added setting `RA_DEFAULT_TO_DATETIME` which defaults to start of current year + 1


## [0.0.9] - 2019-12-25
### Added
- Added changelog, docs/faq
- Drop Use of Django Braces
- Support For Django 3
- Upgrade Django to >= 2.2.9


## [0.0.8] - 2019-12-18
### Added
- Activity Tests
- Data generator for tutorial

### Changed
- Enhance documentation and tutorial
- Fix UI around Chart list

### Removed
- Different Legacy Code


## [0.0.7] 2019-12-17
### Added
- Travis CI

### Removed
- `django-compressor` dependency


## [0.0.6] 2019-12-14
### Changed
- Use setup.cfg
- Use Select2 instead of own widget developed for Django 1.11

## [0.0.5] 2019-12-13
### Changed
- Update Tutorial

## [0.0.4] 2019-12-11
### Added
- First release on Github

### Changed
- Upgrade to Python 3 and Django 2.2