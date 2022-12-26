# Latest stable tag of official pangeo forge base image for dataflow
FROM pangeo/forge:5e51a29

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

# Install production dependencies.
RUN mamba run -n notebook pip install --no-cache-dir -r requirements.txt

# Run the web service on container startup. Here we use the gunicorn
# webserver, with one worker process and 8 threads.
# For environments with multiple CPU cores, increase the number of workers
# to be equal to the cores available.
# Timeout is set to 0 to disable the timeouts of the workers to allow Cloud Run to handle instance scaling.
CMD exec gunicorn \
    -k uvicorn.workers.UvicornWorker \
    --bind :$PORT --workers 1 --threads 8 --timeout 0 \
    main:app
