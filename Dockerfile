# pull official base image
FROM python:3.6.3-alpine

# set work directory
RUN apk --update add build-base mysql-dev bash
RUN apk --update add libxml2-dev libxslt-dev libffi-dev gcc musl-dev libgcc openssl-dev curl
RUN apk add jpeg-dev zlib-dev freetype-dev lcms2-dev openjpeg-dev tiff-dev tk-dev tcl-dev
RUN apk --update add gcc python3-dev musl-dev postgresql-dev

WORKDIR /code

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN pip install --upgrade pip
COPY /dist/* /dist/
RUN pip install /dist/django-erp_framework-erp-1.1.1.tar.gz
RUN pip install django-compressor==2.4
RUN erp_framework-admin start project_name
WORKDIR /code/project_name
RUN python manage.py migrate
RUN python manage.py createsuperuser
RUN ls -al
EXPOSE 8000
CMD python manage.py runserver 0.0.0.0:8000
