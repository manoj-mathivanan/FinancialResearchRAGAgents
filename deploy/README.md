# Deploy FinDoc on the VPS

Caddy serves `findoc.manojmathivanan.com` and forwards traffic to FastAPI on `127.0.0.1:8767`. The FastAPI container serves the built React UI and connects to the existing FinDoc database using a read-only role.

Build from a clean checkout of the release commit. Tag each image with its commit so you can switch back without rebuilding.

```sh
release=$(git rev-parse --short=12 HEAD)
docker build -t "local/findoc:$release" .
```

The host stores the database connection and model settings in `/var/lib/findoc/database.env` and `/var/lib/findoc/staging.env`. It mounts the BGE cache from `/var/lib/findoc/bge-cache`. Keep those files outside Git. Start the app with one worker and the resource settings used in the initial deployment.

```sh
docker run -d --name findoc-staging --restart unless-stopped --network host \
  --memory 280m --memory-swap 480m --cpus 0.50 --pids-limit 96 \
  --cap-drop ALL --security-opt no-new-privileges \
  --log-opt max-size=5m --log-opt max-file=2 \
  --env-file /var/lib/findoc/database.env --env-file /var/lib/findoc/staging.env \
  -e FASTEMBED_CACHE_PATH=/var/cache/findoc -e HF_HUB_OFFLINE=1 \
  -v /var/lib/findoc/bge-cache:/var/cache/findoc "local/findoc:$release" \
  python -m uvicorn findoc.api:app --host 127.0.0.1 --port 8767 --workers 1 --limit-concurrency 4
```

For an update, stop the current container and rename it to `findoc-previous` before starting the new container. Verify the public home page, `/api/config`, and one Research Team question with a filing and transcript citation. Verify Trader still responds. If the check fails, stop and rename the new container, rename `findoc-previous` back to `findoc-staging`, and start it. The app release uses the existing database and does not require reindexing unless the embedding model or passage format changes.
