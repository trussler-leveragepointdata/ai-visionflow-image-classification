# Locust stress-test report

## Environment

- Test date: 2026-11-21
- Host: Apple MacBook Pro (Mac16,7), Apple M4 Pro
- Physical CPU: 14 cores (10 performance, 4 efficiency)
- Physical memory: 24 GB
- Operating system: macOS 26.7.3 (build 25G342)
- Docker Desktop engine: 28.3.2
- Docker Compose: 2.38.2-desktop.1
- Docker allocation: 14 CPUs, 7.65 GiB memory
- Locust: 2.47.0 on Python 3.12.7

## Method

The API, PostgreSQL, Redis, UI, and model service ran in Docker Desktop. Locust
ran on the host and targeted `http://localhost:8000`. Each simulated user logged
in once, then executed the `GET /` index task and `POST /model/predict` task with
equal weight. The prediction task reused `stress_test/dog.jpeg`.

Each recorded run lasted two minutes. The 10-, 50-, and 100-user scenarios used
spawn rates of 2, 5, and 10 users per second respectively. The model was warmed
before measurements, and a 10-second graceful stop timeout was used for the
two-worker runs and the repeated one-worker 50-user run. All results below come
from the endpoint rows in the generated Locust CSV files rather than from the
aggregated row.

## Prediction results

| Model instances | Users | Requests | Failures | Requests/s | Average (ms) | Median (ms) | p95 (ms) | p99 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 10 | 199 | 0 | 1.67 | 120.3 | 110 | 210 | 250 |
| 1 | 50 | 866 | 1 | 7.25 | 366.7 | 290 | 970 | 1,600 |
| 1 | 100 | 1,044 | 28 | 8.64 | 3,178.1 | 3,000 | 6,500 | 8,200 |
| 2 | 10 | 197 | 0 | 1.66 | 113.0 | 110 | 120 | 210 |
| 2 | 50 | 932 | 0 | 7.80 | 132.3 | 110 | 220 | 380 |
| 2 | 100 | 1,813 | 0 | 15.06 | 299.0 | 210 | 800 | 1,200 |

At 10 users the workload did not saturate one model worker, so a second worker
made almost no throughput difference. At 50 users, two workers increased predict
throughput by 7.6% and reduced average prediction latency by 63.9%. At 100 users,
two workers increased predict throughput by 74.3% and reduced average prediction
latency by 90.6%.

## Index results

| Model instances | Users | Requests | Failures | Requests/s | Average (ms) | Median (ms) | p95 (ms) | p99 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 10 | 187 | 0 | 1.57 | 6.0 | 4 | 7 | 110 |
| 1 | 50 | 924 | 0 | 7.74 | 70.8 | 4 | 470 | 1,100 |
| 1 | 100 | 964 | 29 | 7.98 | 2,267.8 | 2,000 | 5,500 | 7,000 |
| 2 | 10 | 187 | 0 | 1.57 | 4.4 | 4 | 7 | 8 |
| 2 | 50 | 954 | 0 | 7.99 | 10.1 | 3 | 59 | 150 |
| 2 | 100 | 1,851 | 2 | 15.37 | 103.7 | 4 | 550 | 950 |

Although the index handler itself is inexpensive, it shares the API worker pool
with prediction requests. This is why index latency and failures increased when
prediction traffic saturated the one-worker pipeline.

## Resource observations

- With one model instance and 10 users, the model used about 110% Docker CPU and
  961 MiB memory.
- With one model instance and 50 users, the model used about 223% CPU and 1.0 GiB
  memory. API CPU remained near 2%.
- With one model instance and 100 users, the model used about 204% CPU and 1.26
  GiB memory. Gunicorn logged a worker timeout, which explains the dropped
  prediction and index connections in that run.
- With two model instances and 50 users, both workers consumed the Redis queue
  (approximately 98% and 117% CPU) and used about 2.5 GiB combined memory.
- With two model instances and 100 users, both workers used approximately
  220-227% CPU and about 2.8 GiB combined memory. No additional Gunicorn worker
  timeout was logged.

The API service uses a blocking polling loop while awaiting Redis results. Under
the one-instance 100-user load, queued predictions kept an API worker blocked
long enough for Gunicorn's worker timeout to terminate it. Scaling the model
workers shortened the queue and substantially improved both prediction and index
responsiveness. Two isolated index disconnects remained in the two-worker
100-user run, but there was no corresponding Gunicorn timeout.

## Reproducing the test

Create the Locust environment:

```bash
python3.12 -m venv .venv-locust
.venv-locust/bin/python -m pip install -r stress_test/requirements.txt
```

Start one model instance and run a scenario:

```bash
docker compose --env-file .env up -d --scale model=1
.venv-locust/bin/locust -f stress_test/locustfile.py \
  --headless -u 50 -r 5 -t 2m --stop-timeout 10 \
  --csv stress_test/results/model1-users50 --only-summary
```

Scale to two model instances and repeat with identical parameters:

```bash
docker compose --env-file .env up -d --scale model=2
.venv-locust/bin/locust -f stress_test/locustfile.py \
  --headless -u 50 -r 5 -t 2m --stop-timeout 10 \
  --csv stress_test/results/model2-users50 --only-summary
```

The raw statistics and failure records are stored in `stress_test/results/`.
