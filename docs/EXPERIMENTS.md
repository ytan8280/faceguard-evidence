# Experiments

This file records experiments run specifically for FaceGuard Evidence.
Results must be measured, reproducible and linked to the relevant code, data,
model and configuration versions.

Historical values copied from the original FaceGuard notebook do not count as
FaceGuard Evidence experiments. They are documented separately in
[`MODEL_CARD.md`](MODEL_CARD.md).

## Experiment Record Requirements

Every experiment entry must include:

- experiment identifier and date;
- question or hypothesis;
- code revision;
- model and artifact versions;
- dataset or query-set identity;
- configuration and random seed;
- hardware and software environment;
- procedure;
- raw-output location;
- measured results;
- interpretation;
- limitations; and
- next decision.

Do not record estimated, expected or invented values as results.

## Experiment Index

| ID | Date | Experiment | Status | Result |
|---|---|---|---|---|
| `FG-EXP-001` | 2026-10-06 | Imported website baseline verification | Completed | Backend and frontend started and responded successfully; detector not configured |
| `FG-EXP-002` | 2026-10-06 | Verified `vit3` checkpoint loading | Completed | Hashed checkpoint loaded successfully on CPU and health reported ready |
| `FG-EXP-003` | 2026-10-06 | Atlas and authentication-path verification | Completed | Atlas ping succeeded; database-backed nonexistent sign-in returned expected `401` |

## FG-EXP-001: Imported Website Baseline Verification

### Question

Can the history-preserved original FaceGuard website install, build, import and
start in the FaceGuard Evidence worktree before any RAG changes are made?

### Revision

- FaceGuard Evidence merge commit: `57935c5`
- Imported original FaceGuard revision:
  `c46cc8f8170b809f7bf53bd159e81e11d7cdc9cc`

### Environment

| Component | Measured value |
|---|---|
| Operating system | Windows |
| Python | `3.11.9` |
| FastAPI | `0.115.2` |
| PyTorch | `2.14.1+cpu` |
| Torchvision | `0.29.1+cpu` |
| CUDA available | `False` |
| Node.js | `v24.19.0` |
| npm | `11.17.0` |

The Python environment was created in the ignored repository-local `.venv`
directory. Frontend packages were installed from the committed
`package-lock.json`.

### Procedure

1. Created a Python 3.11 virtual environment.
2. Installed `requirements.txt`.
3. Ran `pip check`.
4. Imported the FastAPI application and listed its `/api/` routes.
5. Installed frontend packages with `npm ci`.
6. Built the frontend with `npm run build`.
7. Started the backend on `127.0.0.1:8001`.
8. Started the Vite frontend on `127.0.0.1:5173`.
9. Requested the backend health endpoint and frontend root page.
10. Stopped both temporary processes.

No model checkpoint or database connection was configured.

### Measured Results

| Check | Result |
|---|---|
| Python dependency integrity | `pip check`: no broken requirements |
| Backend application import | Succeeded |
| Imported API routes | `/api/health`, `/api/auth/signin`, `/api/auth/signup`, `/api/auth/google`, `/api/profile`, `/api/analyze` |
| Frontend production build | Succeeded; 50 modules transformed |
| Frontend build time | `813 ms` |
| Built JavaScript size | `202.60 kB` (`64.65 kB` gzip) |
| Built CSS size | `39.50 kB` (`8.41 kB` gzip) |
| Frontend live request | HTTP `200`; FaceGuard page title present |
| Backend health request | HTTP `200` |
| Backend health body | `{"status":"ok","model_ready":false,"model_name":"vit"}` |

### Interpretation

The imported baseline website can install, build and start successfully on the
measured Windows environment. The backend correctly remains available when the
checkpoint is absent and reports that the detector is not ready.

This verifies the application shell only. It does not verify detector
predictions, Grad-CAM, authentication, database persistence, Google sign-in or
profile-history behavior.

### Limitations

- No checkpoint was configured.
- No image was submitted to `/api/analyze`.
- MongoDB and Google OAuth were not configured.
- The Python dependency manifest contains broad lower bounds, so future
  installations may resolve different package versions.
- Node.js 24 is newer than the original documented Node.js 18 baseline.
- npm reported that the esbuild install script was not approved, although the
  Vite production build still completed successfully.
- Raw command output was not retained as a separate artifact; measured values
  are recorded in this entry.

### Next Decision

Verify the pinned `vit3.pth` artifact through the imported detector path before
adding RAG behavior.

## FG-EXP-002: Verified `vit3` Checkpoint Loading

### Question

Can the imported detector implementation load the exact checkpoint selected
for FaceGuard Evidence and report it as ready through the live API?

### Revision and Artifact

- FaceGuard Evidence revision: `57935c5`
- Model filename: `vit3.pth`
- Model size: `343,248,309` bytes
- Model SHA-256:
  `6FAE9B18A7A7BAFED65FE5A944FC1B66A8CE070896A8531C6C5857477806C25B`

The checkpoint remained outside the repository and was configured through the
ignored local `.env` file.

### Environment

The software environment was the same as `FG-EXP-001`:

- Python `3.11.9`;
- PyTorch `2.14.1+cpu`;
- Torchvision `0.29.1+cpu`; and
- CUDA unavailable.

### Procedure

1. Recalculated the local checkpoint size and SHA-256.
2. Confirmed both values matched the model-card record.
3. Configured `FACEGUARD_MODEL_NAME=vit3`.
4. Configured the external checkpoint path through `.env`.
5. Left `FACEGUARD_FAKE_THRESHOLD` unset.
6. Loaded the checkpoint through the imported `InferenceService`.
7. Started the FastAPI backend.
8. Requested `GET /api/health`.
9. Stopped the backend.

### Measured Results

| Check | Result |
|---|---|
| Checkpoint size match | Yes |
| Checkpoint SHA-256 match | Yes |
| Model load | Succeeded |
| Model ready after direct load | `True` |
| Reported model name | `vit3` |
| Device | `cpu` |
| Input image size | `224` |
| Active threshold | `0.25` |
| Live health status | HTTP `200` |
| Live health body | `{"status":"ok","model_ready":true,"model_name":"vit3"}` |

### Interpretation

The exact checkpoint selected for FaceGuard Evidence is structurally
compatible with the imported ViT-B/16 inference implementation and can be
loaded successfully on CPU.

The active threshold of `0.25` comes from the imported source default because
the threshold environment variable was deliberately left unset. This result
does not justify adopting `0.25` as the final FaceGuard Evidence threshold.

### Limitations

- No image inference was performed.
- Prediction probability and label behavior were not checked.
- Grad-CAM output was not checked.
- Loading compatibility does not prove that this checkpoint is byte-for-byte
  identical to the historical notebook's `vit3.pth`.
- Detector latency and memory use were not measured.
- Threshold selection remains unresolved.

### Next Decision

Run one controlled still-image inference through `/api/analyze`, confirm the
response contract and inspect Grad-CAM behavior before introducing the
detector adapter abstraction.

## FG-EXP-003: Atlas and Authentication-Path Verification

### Question

Do the local backend and frontend configurations point to the intended
services, and can the imported authentication path reach the new MongoDB Atlas
database without creating test data?

### Revision

- FaceGuard Evidence revision: `57935c5`
- Local configuration files: ignored `.env` files, not committed

### Procedure

1. Checked required backend and frontend variable presence without printing
   values.
2. Confirmed backend and frontend Google client IDs matched.
3. Confirmed the frontend API URL used port `8001`.
4. Sent an Atlas administrative `ping`.
5. Built the frontend with its local environment.
6. Started the backend with Atlas and `vit3` configured.
7. Requested `GET /api/health`.
8. Submitted a sign-in request for a randomly generated nonexistent
   `example.invalid` email.
9. Confirmed the request returned an authentication result rather than a
   database-connection error.
10. Stopped the backend.

The sign-in check performed a read operation only and did not create a user.

### Measured Results

| Check | Result |
|---|---|
| Atlas ping | Succeeded |
| Database name configured | Yes |
| Frontend API URL configured | Yes |
| Frontend API port | `8001` |
| Backend Google client ID configured | Yes |
| Frontend Google client ID configured | Yes |
| Google client IDs matched | Yes |
| Frontend production build | Succeeded |
| Frontend build time | `715 ms` |
| Backend health status | HTTP `200` |
| Backend health model state | `model_ready: true`, `model_name: vit3` |
| Nonexistent account sign-in | HTTP `401 Unauthorized` |
| Database connection failure | Not observed |

### Interpretation

The new MongoDB Atlas deployment is reachable from the local environment. The
authentication service can query the configured users collection, and the
frontend is configured to call the backend on its actual local port.

The `401` response is the expected result for a nonexistent account. A `503`
would instead have indicated disabled authentication or a database connection
failure.

### Limitations

- No account was created.
- Password hashing and successful email/password sign-in were not tested.
- Google OAuth was not exercised with a real identity token.
- Profile retrieval and analysis-history persistence were not tested.
- Atlas production network rules, backups and monitoring were not evaluated.
- Credential values were intentionally excluded from the experiment record.

### Next Decision

Use a temporary disposable account only when testing the complete sign-up,
sign-in, profile and history workflow, and remove it after validation.

## Planned Experiment Areas

These are plans, not results:

1. detector-adapter equivalence against the pinned original implementation;
2. detector latency on the selected local or hosted environment;
3. PostgreSQL full-text retrieval baseline;
4. pgvector semantic-retrieval baseline;
5. hybrid-fusion comparison;
6. reranking comparison;
7. retrieval evaluation using a versioned question set;
8. generation evaluation using supported-claim and citation checks; and
9. Azure token, latency and cost measurement.

Planned work remains in this section until it has been executed and measured.
