# Edge (nginx)

The production edge config lives with the SPA build so it ships in the same image:

- `frontend/nginx.conf`: server block (SPA fallback, `/api` proxy to `backend:8000`, `/healthz-edge`)
- `frontend/nginx-security-headers.conf`: headers included in every location

The `edge` service in `compose.prod.yaml` builds `frontend/Dockerfile` target `runtime`
(`nginxinc/nginx-unprivileged`, non-root, port 8080). TLS termination is expected in front
of this container (load balancer or ingress); see `docs/deployment.md`.
