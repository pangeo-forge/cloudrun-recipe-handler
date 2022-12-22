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