# cloudrun-recipe-handler
Pangeo Forge recipe handler for GCP Cloud Run.

To deploy, from within the `/src` directory:

```console
$ gcloud run deploy $SERVICE_NAME --source .
```

To get service url from service name:

```console
$ gcloud run services describe $SERVICE_NAME
```

To invoke:

```console 
$ curl \
  -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  $SERVICE_URL \
  --json $PAYLOAD_JSON
```
or

```console
$ curl \
  -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  $SERVICE_URL \
  -d $PAYLOAD_JSON
```

## Testing

### pytest

Create and activate a local conda environment from the file `ci/env.yaml`:

```console
$ conda env create --file ci/env.yaml
$ conda activate cloudrun
```

Then run the tests:

```console
$ pytest src/tests
```

> **Note**: Because one of the features of this service is to modify its own environment, the tests also modify the test environment. This means the tests are somewhat long-running, but in exchange for this performance cost, we get the reassurance of testing the actual behavior (as opposed to faster, but potentially inaccurate, mocked tests).

### docker

The official Cloud Run docs have some good suggestions for [testing locally with docker](https://cloud.google.com/run/docs/testing/local#docker).
