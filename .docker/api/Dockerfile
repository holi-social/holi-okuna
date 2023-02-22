FROM python:3.11.0

RUN apt-get -y update && apt-get -y upgrade && apt-get install -y \
    ffmpeg \
    binutils \
    libproj-dev \
    libgdal-dev \
    libgeos-dev 

# Copy any files over
COPY wait-for-it.sh /wait-for-it.sh
COPY entrypoint.sh /entrypoint.sh
COPY bootstrap_development_data.sh /bootstrap_development_data.sh

# Change permissions
RUN chmod +x /entrypoint.sh
RUN chmod +x /bootstrap_development_data.sh
RUN chmod +x /wait-for-it.sh

ENTRYPOINT ["/entrypoint.sh"]

COPY requirements.txt /requirements.txt

RUN pip install --upgrade pip
RUN pip install -r /requirements.txt

VOLUME ["/opt/okuna-api"]

EXPOSE 80

#CMD ["python", "manage.py", "runserver", "0.0.0.0:80"]
CMD ["uvicorn", "openbook.asgi:application", "--host", "0.0.0.0", "--port", "80"]
