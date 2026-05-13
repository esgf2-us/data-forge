# Data-Forge Implementation Plan

## Overview
This document outlines a staged approach to building Data-Forge, a service for generating Kerchunk reference files and managing catalogs for climate datasets. **Key Architecture**: the initial core flow is local input -> generate Kerchunk -> write the reference file alongside the source data on local disk. Additional output destinations (for example S3 and Globus) are future stages. The service does NOT provide internal storage; users manage their own file storage infrastructure.

---

## Stage 0: Project Setup & Foundation (Week 1)

### Goals
- Establish project structure
- Set up development environment
- Create basic tooling and CI/CD

### Tasks
1. **Project Structure**
   - Initialize Python project with Poetry/pip-tools
   - Set up directory structure:
     ```
     data-forge/
     ├── src/
     │   ├── dataforge/
     │   │   ├── api/          # FastAPI routes
     │   │   ├── core/         # Core business logic
     │   │   ├── models/       # Data models
     │   │   ├── workers/      # Job workers
     │   │   ├── cli/          # CLI tool
     │   │   └── utils/        # Utilities
     ├── tests/
     ├── docs/
     ├── docker/
     └── deployments/
     ```

2. **Development Environment**
   - Create `pyproject.toml` with dependencies:
     - FastAPI, uvicorn
     - kerchunk, fsspec, h5netcdf, xarray
     - redis, dramatiq
     - dask, distributed
     - pydantic for validation
      - s3fs, aiohttp for future output backends and integrations
     - Click/Typer for CLI
   - Set up Docker development environment
   - Create `.env.example` for configuration

3. **Testing & CI**
   - Set up pytest framework
   - Configure GitHub Actions / GitLab CI
   - Set up pre-commit hooks (black, ruff, mypy)

### Deliverables
- ✅ Project skeleton
- ✅ Development environment
- ✅ Basic CI/CD pipeline

---

## Stage 1: Core Kerchunk Conversion (Week 2)

### Goals
- Implement basic Kerchunk conversion functionality
- Support single file and multi-file conversion
- Support writing to local filesystem and S3
- Benchmark multi-input conversion paths before expanding scope

### Tasks
1. **Conversion Module** (`src/dataforge/core/converter.py`)
    - Implement `KerchunkConverter` class
    - Support single NetCDF file conversion
    - Support multi-file conversion with concatenation along specified dimensions
    - Handle different chunk strategies
    - Write output to one server-configured destination: local or S3
    - Basic error handling and logging

2. **Storage Writer** (`src/dataforge/core/storage.py`)
    - Implement fsspec-based output writer (DI-friendly interface + concrete implementations)
    - Support writing to S3 (s3://)
    - Support writing to local filesystem
    - Handle authentication for output destinations
    - Add a docker-compose overlay for local S3-compatible testing and output validation

3. **Configuration** (`src/dataforge/models/config.py`)
     - Define conversion configuration model:
       - inline_threshold (default: 300)
       - concat_dims (e.g., ['time'])
       - identical_dims (e.g., ['lat', 'lon', 'lat_bnds', 'lon_bnds'])
       - output_mode (one of: local, s3)
       - output_path (server-configured for local and s3 output)

4. **Testing & Benchmarking**
    - Unit tests for converter
    - Test with sample NetCDF files
    - Test writing to mock S3 (moto) and local filesystem
    - Add a benchmark plan for single-input vs multi-input conversion
    - Measure concat-dimension behavior and output stability across multiple inputs

### Deliverables
- ✅ Working Kerchunk converter
- ✅ Output to user-specified locations (local and S3)
- ✅ Unit tests with >80% coverage
- ✅ Multi-input benchmark coverage and documentation

---

## Stage 2: Job Queue System + Basic API + Local CLI Smoke Test (Week 3-4)

### Goals
- Implement asynchronous job processing
- Set up Redis + dramatiq for job management
- Create FastAPI application with core endpoints
- Job monitoring capabilities
- Add a minimal CLI over the local API so developers can test the stack end to end
- Keep Stage 2 scoped to local-input MVP only

### Tasks
1. **Job Queue Setup**
   - Configure Redis connection (job metadata storage only)
   - Set up dramatiq actors
   - Implement job states: QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED

2. **Job Models** (`src/dataforge/models/job.py`)
     - Define job data structures:
        ```python
        class JobSubmission:
            input_files: List[str]  # local files only for Stage 2 MVP
            output_path: Optional[str]
            output_name: Optional[str]
            concat_dims: List[str] = ['time']
            identical_dims: Optional[List[str]]
            inline_threshold: int = 300
            metadata: Optional[Dict[str, Any]]

        class Job:
            id: str  # job-{uuid}
            status: JobStatus
            submission: JobSubmission
            created_at: datetime
            updated_at: datetime
            started_at: Optional[datetime]
            completed_at: Optional[datetime]
            progress_total: Optional[int]
            progress_done: Optional[int]
            error_message: Optional[str]
            result_url: Optional[str]  # Output path
        ```

3. **Worker Implementation** (`src/dataforge/workers/converter_worker.py`)
    - Create dramatiq actor for conversion
    - Integrate with Stage 1 converter
    - Handle job lifecycle and state updates
    - Write reference files to the configured output destination (local)
    - Store job metadata only in Redis (NOT the reference files)
    - Update job progress (files processed / total)

4. **Job Storage**
    - Redis for job metadata and status only
    - No internal file storage - outputs go to the configured destination
    - Job results contain output path

5. **API Structure** (`src/dataforge/api/`)
   - Set up FastAPI application
   - Configure CORS, middleware
   - Implement health check endpoint
   - Configure OpenAPI/Swagger docs

6. **Core Endpoints**
    - `POST /api/v1/jobs` - Submit local-input conversion job
     - `GET /api/v1/jobs/{job_id}` - Get job status and progress
     - `GET /api/v1/jobs` - List jobs (with pagination, filtering by status)
    - `GET /api/v1/jobs/{job_id}/result` - Get result URL/path
    - `DELETE /api/v1/jobs/{job_id}` - Cancel job (if queued/running)
    - No remote input or STAC/ESGF endpoints in Stage 2

7. **Request/Response Models** (`src/dataforge/models/api.py`)
   - Define Pydantic models for requests/responses
   - Input validation (URL formats, path validation)
   - OpenAPI documentation
   - Example requests matching PRD CLI examples

8. **Testing**
     - Integration tests for API endpoints
     - Test job submission and status retrieval
     - Test progress tracking
     - Test local-input validation and cancellation flows

9. **Local CLI Smoke Test** (`src/dataforge/cli/`)
    - Implement a thin CLI over the REST API for local development
    - Support `submit`, `status`, `list`, and `get-url`
    - Make the API base URL configurable for local testing
    - Defer auth, rich output, config files, and batch submission to later stages

### Deliverables
- ✅ Asynchronous job processing
- ✅ Job state management (metadata only in Redis)
 - ✅ Working REST API for local-input MVP jobs
- ✅ Minimal CLI for local API testing
- ✅ OpenAPI/Swagger documentation
- ✅ Integration tests

---

## Stage 3: Local Workflow Hardening (Week 5)

### Goals
- Support the core local workflow end to end
- Read local input files and generate Kerchunk references
- Write the Kerchunk file locally alongside the source data
- Keep output naming/layout predictable for later output destinations

### Tasks
1. **Local Input Handling**
   - Expand and validate local file inputs
   - Support `file://` and plain filesystem paths
   - Preserve local-only validation in the API and CLI

2. **Local Output Layout**
    - Keep generated Kerchunk files next to the source dataset by default
    - Define predictable output naming for single-file and multi-file runs
    - When `output_name` is omitted, derive a stable local stem from the input file name(s)
    - Make overwrites and file existence behavior explicit (`overwrite_existing`, default false)

3. **Converter Hardening**
   - Keep converter focused on local input paths
   - Improve error messages for missing/invalid local files
   - Ensure the output path is created only where requested

4. **Testing**
   - Test local path validation and output naming
   - Test write-then-read behavior on local files
   - Test missing file and permission failure paths
   - Add fixtures for representative local datasets

### Deliverables
- ✅ Local input support end to end
- ✅ Local output written alongside source data
- ✅ Clear output naming/layout for later output backends
- ✅ Tests for local workflow validation and failure modes

### Future Output Methods
- S3 output
- Globus output
- ESGF/STAC publish flow

---

## Stage 4: STAC Catalog Integration (Week 6-7)

### Goals
- Support a single publishing workflow: generate the Kerchunk reference, write it next to the source files or upload it via S3, then patch an existing STAC Item to add a `kerchunk` aggregate
- Treat STAC patching as the final publication step after the Kerchunk href is known
- **Security Model**: Single catalog configured server-side (prevents abuse)
- Service authenticates to catalog; catalog is public read-only

### Tasks
1. **STAC Module** (`src/dataforge/core/stac.py`)
   - Implement STAC Item aggregate patching for an existing Item
   - Model the update after ESGF publisher aggregate-add behavior: fetch the existing Item, build JSON Patch operations, and apply only the aggregate asset change
   - Add a `kerchunk` aggregate asset whose href points to the generated Kerchunk JSON
   - Preserve existing Item content and unrelated assets; avoid replacing the full Item document
   - Support future aggregate types with the same shape (`zarr`, `virtualizarr`, `icechunk`), but Stage 4 MVP only emits `kerchunk`
   - Prefer dataset-oriented targeting: accept a dataset identifier, fetch the Item, and derive collection/item metadata from the fetched Item when possible

2. **STAC API Client** (`src/dataforge/core/stac_client.py`)
    - Use the `esgcet` package for ESGF-NG STAC search and transaction operations instead of building a custom low-level client from scratch
    - Wrap `esgcet` behind a small local adapter so Data-Forge depends on a narrow internal interface
    - Use `esgcet.search_check.ESGSearchCheck` or equivalent package search functionality to fetch the target Item before patching
    - Use the `esgcet` transaction client support to submit JSON Patch operations for aggregate asset updates
    - Fetch the target Item before patching so the service can validate existence and derive collection metadata
    - Handle service authentication (API token/credentials)
    - **Note**: Service authenticates to publish; catalog is public read-only for users
    - Error handling and retry logic (exponential backoff + jitter)
    - Retry on transient failures (timeouts/connection errors, 429, 5xx)
    - Fail fast on hard failures (400, 401/403, 404)

3. **ESGF Publisher** (`src/dataforge/core/esgf_publisher.py`)
    - Finalize the publishable Kerchunk href after generation
    - Support the Stage 4 output cases:
      - local write next to the source files
      - S3 write to the configured bucket/prefix
    - Return the externally-resolvable href that will be inserted into the STAC aggregate asset
    - Reuse `esgcet` conventions and request shapes where practical so output publication and STAC update logic remain aligned with ESGF tooling
    - Error handling and retry logic (exponential backoff + jitter)

4. **Publishing + STAC Configuration** (Server-Side Only)
   - **MVP Security**: Server-configured STAC base URL + service credential/token
   - Server-configured ESGF publish endpoint + service credential/token
   - Optional allow-list for collections that may be updated
   - **Rationale**: Prevents bad actors from publishing to arbitrary catalogs/endpoints

5. **Worker Updates**
    - For Stage 4 publishing jobs:
      - Generate the Kerchunk JSON
      - Write it locally next to the source files or to S3 using the configured output mode
      - Resolve the final href for that written Kerchunk JSON
      - Fetch the target STAC Item and apply a JSON Patch that adds the `kerchunk` aggregate asset pointing to that href
      - Include the publishing site/datanode context if required by the catalog's aggregate representation
    - STAC patching is the final step in the publishing workflow; if it fails after retries, the job fails
    - Record publication results (dataset ID, asset href, aggregate type, timestamps, failure reason)

6. **API Endpoints**
    - Enhance `POST /api/v1/jobs` with output mode selection and publishing options
    - Require a STAC target identifier when STAC publishing is requested
    - Prefer `dataset_id` as the primary identifier for ESGF/STAC publish flows
    - Allow `stac_collection_id` + `stac_item_id` only if the target catalog requires explicit addressing and dataset lookup is insufficient
    - `GET /api/v1/jobs/{job_id}/stac` - Retrieve STAC target + asset href (if published)

7. **Testing**
    - Unit tests for STAC aggregate patch generation
    - Unit tests for the local `esgcet` adapter layer with mocked `esgcet` responses
    - Unit tests that verify only the aggregate asset change is emitted, leaving unrelated Item content untouched
    - Unit tests for publishable href resolution for local and S3 outputs
    - Integration tests for `esgcet`-backed STAC search + transaction flows (including 429/5xx retry behavior)
    - Integration tests for end-to-end: generate -> write local/S3 -> fetch Item -> patch `kerchunk` aggregate into STAC Item

### Deliverables
- ✅ STAC aggregate asset updates for existing Items
- ✅ Retries/backoff for upload + STAC update
- ✅ Server-configured STAC catalog integration (secure)
- ✅ Server-configured ESGF publish integration (secure)
- ✅ Service-level authentication to catalog (credentials never exposed)
- ✅ STAC integration tests
- 🔒 Security: Centralized catalog control prevents malicious publications

---

## Stage 5: Dask Parallelization (Week 8)

### Goals
- Add Dask for job-level parallelization
- Improve performance for large multi-file datasets
- Support distributed processing within a job

### Tasks
1. **Dask Integration** (`src/dataforge/core/dask_converter.py`)
   - Set up Dask client (local cluster initially)
   - Parallelize multi-file Kerchunk generation
   - Use Dask to process files in parallel (not just sequential)
   - Implement chunked processing for memory efficiency
   - Proper Dask cluster lifecycle management

2. **Memory Management**
   - Configure Dask worker memory limits
   - Implement spilling to disk for large jobs
   - Monitor memory usage per job
   - Prevent OOM errors

3. **Configuration** (`src/dataforge/models/dask_config.py`)
   - Dask cluster configuration
   - Worker count (default: based on available CPUs)
   - Memory per worker
   - Scheduler options
   - Thread vs process workers

4. **Worker Updates**
   - Integrate Dask into dramatiq workers
   - Create Dask cluster per job or shared pool
   - Handle Dask cluster cleanup
   - Progress reporting from Dask tasks

5. **Performance Optimization**
   - Optimize file reading with Dask
   - Batch file processing
   - Reduce network I/O overhead
   - Efficient memory usage patterns

6. **Performance Testing**
   - Benchmark with/without Dask
   - Test with datasets of various sizes (10, 100, 1000+ files)
   - Measure speedup vs sequential processing
   - Optimize worker count and chunk strategies
   - Memory profiling

### Deliverables
- ✅ Dask-based job-level parallelization
- ✅ Significant performance improvements for multi-file datasets
- ✅ Scalability tests and benchmarks
- ✅ Memory-efficient processing

---

## Stage 6: Advanced Features (Week 9-10)

### Goals
- Enhanced chunk strategies and optimization
- Better metadata handling for CMIP6/CMIP7
- Improved error handling and validation
- Basic monitoring and metrics

### Tasks
1. **Advanced Chunk Strategies** (`src/dataforge/core/chunking.py`)
   - Configurable dimension selection strategies
   - Auto-detect optimal chunk sizes based on data shape
   - Grid-aware chunking recommendations
   - Support for irregular grids (curvilinear, unstructured)
   - Chunking presets for common CMIP6/7 variables

2. **Metadata Enhancement** (`src/dataforge/core/metadata.py`)
   - Extract comprehensive CMIP6/CMIP7 metadata
   - CF conventions compliance checking
   - DRS (Data Reference Syntax) parsing
   - Automatic dataset_id validation
   - Provenance tracking (source files, processing date, Data-Forge version)
   - Enhanced STAC metadata with CMIP attributes

3. **Validation** (`src/dataforge/core/validation.py`)
   - Pre-flight validation of input URLs
   - Output path write permission checks
   - NetCDF file structure validation
   - Dimension compatibility checks for multi-file datasets
   - Early failure detection

4. **Error Handling**
   - Detailed error messages with suggestions
   - Graceful degradation (partial success scenarios)
   - Retry logic for transient failures
   - Error categorization (user error vs system error)

5. **Monitoring & Observability** (`src/dataforge/monitoring/`)
   - Basic Prometheus metrics:
     - Jobs submitted, completed, failed
     - Average job duration
     - Files processed per second
     - API request latency
   - Structured logging (JSON logs)
   - Job statistics dashboard data
   - Health check enhancements

6. **Performance Optimizations**
   - Connection pooling for S3
   - Caching for repeated metadata extraction
   - Optimize Kerchunk inline threshold strategies
   - Reduce memory footprint for large files

7. **Testing**
   - Test with various CMIP6 datasets and grids
   - Validation logic tests
   - Error handling tests
   - Performance regression tests

### Deliverables
- ✅ Advanced conversion options and chunking strategies
- ✅ Enhanced CMIP6/CMIP7 metadata support
- ✅ Robust validation and error handling
- ✅ Basic monitoring and metrics
- ✅ Performance optimizations

---

## Stage 7: Docker, Kubernetes & CLI Tool (Week 11-12)

### Goals
- Containerize all services
- Production-ready Kubernetes deployment with Helm
- Build CLI tool matching PRD examples
- Complete deployment infrastructure

### Tasks
1. **Docker Images**
   - Create Dockerfile for API service
   - Create Dockerfile for worker service(s)
   - Optimize image sizes (multi-stage builds)
   - Pin dependencies for reproducibility
   - Security scanning integration

2. **Docker Compose** (`docker-compose.yml`)
   - API service (FastAPI)
   - Worker service(s) (dramatiq)
   - Redis service (job metadata)
   - Volume management (configuration only, no data storage)
   - Network configuration
   - Health checks for all services

3. **Kubernetes Deployment**
   - Create Helm chart for Data-Forge
   - Deployments for API, workers, Redis
   - ConfigMaps and Secrets management
   - Horizontal Pod Autoscaling for workers
   - Ingress configuration
   - Persistent volume claims (for Redis if needed)
   - Resource limits and requests
   - Liveness and readiness probes

4. **Helm Chart** (`deployments/helm/`)
   - Values.yaml for configuration
   - Templates for all Kubernetes resources
   - Support for multiple environments (dev, staging, prod)
   - Parameterized scaling configuration
   - Documentation for Helm deployment

5. **CLI Tool** (`src/dataforge/cli/`)
   - Use Click framework
   - Implement commands per PRD examples:
     - `dataforge login` - Authenticate (Globus Auth in Stage 8)
     - `dataforge submit` - Submit job with all options
     - `dataforge status <job-id>` - Check job status
     - `dataforge list` - List jobs with filtering
     - `dataforge get-url <job-id>` - Get result URL
     - `dataforge stac show <job-id>` - View STAC item
   - Support `--watch` for real-time status updates
   - Colorized output with status indicators
   - Progress bars for running jobs

6. **CLI Client Library** (`src/dataforge/client/`)
   - Create Python API client wrapping REST API
   - Used by CLI and available for programmatic access
   - Handle authentication, retries, pagination
   - Async and sync variants

7. **CLI Features**
   - Rich progress display (files processed / total)
   - Table formatting for job lists
   - JSON output option for scripting
   - Configuration file support (~/.dataforge/config)
   - Batch job submission from YAML/JSON

8. **Configuration Management**
   - Environment variable configuration
   - `.env` file for local development
   - Secrets management (Redis password, S3 credentials, STAC API token)
   - Support for multiple environments (dev, staging, prod)
   - Kubernetes-native secret management

9. **Documentation**
   - Docker Compose deployment guide
   - Kubernetes deployment guide
   - Helm chart documentation
   - CLI usage guide with examples matching PRD
   - Configuration reference
   - Environment variable documentation
   - Troubleshooting guide

### Deliverables
- ✅ Docker images for all services
- ✅ Docker Compose setup for single-node deployment
- ✅ Production-ready Kubernetes deployment
- ✅ Helm chart for easy deployment
- ✅ Full-featured CLI tool matching PRD examples
- ✅ Python client library
- ✅ Comprehensive deployment documentation

---

## Stage 8: Globus Auth Integration (Week 13-14)

### Goals
- Add Globus Auth for user authentication
- Protect API endpoints with OAuth2
- Support token-based CLI authentication

### Tasks
1. **Globus Auth Setup**
   - Register Data-Forge as Globus application
   - Configure OAuth2 scopes
   - Set up callback URLs

2. **API Authentication** (`src/dataforge/api/auth.py`)
   - Implement Globus Auth middleware for FastAPI
   - Token validation using Globus SDK
   - User identity extraction
   - Protected endpoint decorators
   - API key support for programmatic access

3. **User Management** (`src/dataforge/models/user.py`)
   - Store user identity from Globus (sub/username)
   - Associate jobs with users
   - User-scoped job listings
   - Resource quotas per user (optional)

4. **CLI Authentication** (`src/dataforge/cli/auth.py`)
   - `dataforge login` implementation
   - OAuth2 device flow or browser-based flow
   - Token storage (~/.dataforge/tokens.json)
   - Token refresh logic
   - `dataforge logout` command

5. **API Updates**
   - All job endpoints require authentication
   - Jobs filtered by authenticated user
   - Admin endpoints for monitoring (optional)

6. **Testing**
   - Mock Globus Auth for tests
   - Test token validation
   - Test user isolation (users can only see their jobs)
   - Test CLI authentication flow

7. **Documentation**
   - Authentication guide
   - Globus Auth setup instructions
   - Token management
   - Troubleshooting authentication issues

### Deliverables
- ✅ Globus Auth integration for API and CLI
- ✅ User-scoped job management
- ✅ Secure token handling
- ✅ Authentication documentation

---

## Stage 9: Production Hardening, Security, Resiliency & Final Testing (Week 15-16)

### Goals
- Comprehensive end-to-end testing
- Performance optimization and load testing
- Security hardening
- Queue and worker resiliency across service outages and restarts
- Complete documentation
- Production readiness verification

### Tasks
1. **End-to-End Testing**
   - Complete workflows with real CMIP6 datasets
   - Multi-user concurrent job testing
   - Failure recovery scenarios
   - Data integrity validation
   - STAC publication verification
   - Globus Auth integration testing

2. **Performance Testing**
   - Benchmark with datasets of varying sizes:
     - Small: single file, <1GB
     - Medium: 10-100 files, 1-10GB total
     - Large: 100-1000+ files, 10-100GB+ total
   - Load testing (50-100 concurrent jobs)
   - Memory profiling and optimization
   - Network I/O optimization
   - Dask cluster tuning
   - API latency benchmarks (target: p95 <500ms)

3. **Security Audit**
    - Authentication/authorization review
    - Input validation and sanitization
    - SQL/command injection prevention
    - Credential handling audit (no leakage in logs/errors)
    - Output path traversal attack prevention
    - Rate limiting implementation
    - Dependency vulnerability scanning
    - Container security scanning

   **Current posture note (May 2026):**
   - Current implementation is acceptable for trusted local development, but is not production-ready from a security standpoint.
   - API endpoints are currently unauthenticated/unauthorized.
   - Local input paths are accepted from callers without workspace confinement, so file access is broader than intended for a multi-user deployment.
   - Local output placement can be derived from caller-supplied paths when no server-side local output root is configured.
   - Development deployment currently exposes Redis and the API on the network without production-grade auth/TLS controls.
   - OpenAPI/docs and permissive default CORS settings should be treated as development defaults and tightened before any shared deployment.

4. **Queue Resiliency & Recovery**
    - Verify queued jobs survive API restarts, worker restarts, and Redis reconnect events
    - Define the expected behavior for jobs interrupted while `RUNNING`
    - Implement recovery/reconciliation on startup so orphaned `RUNNING` jobs are re-queued or marked failed according to policy
    - Ensure job state transitions remain safe under duplicate delivery or worker retry conditions
    - Test cancellation behavior during outages and after recovery
    - Document broker durability assumptions and required Redis persistence settings for production
    - Add operational guidance for draining workers, restarting services, and recovering from broker outages

5. **Kubernetes Production Testing**
    - Deploy to production-like environment
    - Test horizontal scaling
    - Test pod failure recovery
    - Test rolling updates
    - Ingress and load balancer testing
    - Resource limit validation
    - Monitoring and alerting verification

6. **Documentation Completion**
    - User guide for data publishers
    - API documentation refinement (OpenAPI/Swagger)
    - CLI reference with examples
    - Deployment guide (Docker Compose + Kubernetes)
    - Troubleshooting guide
    - Architecture documentation
    - Configuration reference
    - Security best practices
    - Resiliency and recovery runbooks
    - Performance tuning guidelines

7. **Production Readiness**
    - Monitoring and alerting setup (Prometheus)
    - Log aggregation configuration
    - Backup and recovery procedures
    - Incident response plan
    - Runbook for common operations
    - Health check validation

8. **User Acceptance Testing**
    - Beta testing with data publishers
    - Feedback collection and priority fixes
    - Usability improvements
    - Edge case handling
    - Documentation review

9. **CMIP6/CMIP7 Validation**
    - Test with real CMIP6 datasets from ESGF
    - Various variables (tas, pr, tos, etc.)
    - Different grid types and resolutions
   - Historical, scenario, and control experiments
   - CMIP7 datasets (as available)
   - Validate STAC metadata accuracy

### Deliverables
- ✅ Production-ready system
- ✅ Comprehensive test coverage (>80%)
- ✅ Complete documentation
- ✅ Security audit passed
- ✅ Queue resiliency and outage recovery validated
- ✅ Performance benchmarks met
- ✅ User acceptance criteria met
- ✅ Kubernetes deployment validated
- ✅ Monitoring and alerting operational

---

## MVP COMPLETE (Week 16 / 4 Months)

### MVP Features Complete
✅ Kerchunk conversion service with Dask parallelization  
✅ REST API for job management  
✅ User-specified output paths (local filesystem)  
✅ Server-configured STAC catalog integration (secure)  
✅ Asynchronous job processing with progress tracking  
✅ Local input sources only for the initial core flow  
✅ Advanced metadata extraction and validation  
✅ Monitoring and observability (Prometheus, structured logging)  
✅ Docker + Kubernetes deployment (production-ready)  
✅ Helm chart for easy deployment  
✅ CLI tool with all core commands  
✅ Globus Auth integration  
✅ Production-ready with comprehensive testing  

### MVP Success Criteria
- [ ] Convert NetCDF files to Kerchunk references with Dask parallelization
- [ ] API handles 50+ concurrent jobs without degradation
- [ ] Jobs write outputs to user-specified S3 paths successfully
- [ ] STAC catalog updates succeed for CMIP6 datasets (server-configured)
- [ ] Kubernetes deployment works on production infrastructure
- [ ] Horizontal scaling verified (10 → 50 workers)
- [ ] CLI completes all workflows from PRD examples
- [ ] Globus Auth authentication working end-to-end
- [ ] Advanced validation prevents common user errors
- [ ] Monitoring dashboards operational (Prometheus + Grafana)
- [ ] Documentation complete and reviewed
- [ ] >80% test coverage
- [ ] Security audit passed
- [ ] Performance benchmarks met (job throughput, API latency)

---

## Post-MVP Features (Deferred)

These features are valuable but not required for initial launch. They can be prioritized based on user feedback and operational needs after the 4-month MVP is complete.

### Compute Scheduler Integration
**Timeline:** 3-4 weeks post-MVP  
**Priority:** High for HPC sites

**Goals:**
- Support external compute schedulers for HPC environments
- Hybrid job routing (local vs remote compute)

**Key Features:**
- Scheduler abstraction layer (`BaseScheduler` interface)
- Globus Compute integration for remote execution
- SLURM scheduler support (sbatch, squeue)
- PBS scheduler support (qsub, qstat)
- Job routing based on dataset size, user, priority
- Unified status monitoring across schedulers

**Use Case:** Sites with existing HPC infrastructure want to leverage their compute resources instead of running local workers.

---

### Web UI
**Timeline:** 4-6 weeks post-MVP  
**Priority:** Medium (CLI + API sufficient for initial users)

**Goals:** User-friendly web interface for job management and monitoring

**Key Features:**
- Dashboard with job overview and statistics
- Job submission form with validation
- Real-time job monitoring with progress
- Catalog browser for published datasets
- User profile and settings management
- Globus Auth integration for login

**Tech Stack:** React/Vue + FastAPI backend

**Use Case:** Broaden adoption to less technical users; provide visual monitoring for operators.

---

### VirtualiZarr Support
**Timeline:** 2-3 weeks post-MVP  
**Priority:** Medium (emerging technology)

**Goals:** Add VirtualiZarr as alternative/complement to Kerchunk

**Key Features:**
- VirtualiZarr backend option for reference generation
- Support Zarr v3 references
- Performance comparison with Kerchunk
- Backend selection via API/CLI (`--backend virtualzarr`)

**Rationale:** VirtualiZarr is maturing rapidly and may offer advantages for certain use cases.

---

### Kafka Consumer for Event-Driven Workflows
**Timeline:** 2-3 weeks post-MVP  
**Priority:** Low (integration feature)

**Goals:** Event-driven job submission for integration with existing publication workflows

**Key Features:**
- Kafka consumer service (separate from main API)
- Listen for dataset publication events
- Auto-submit Kerchunk generation jobs
- Dead letter queue for failed messages
- Integration with ESGF publication workflows

**Use Case:** Automatic Kerchunk generation when new datasets are published to ESGF.

---

### MetaGrid Integration
**Timeline:** TBD (depends on MetaGrid API availability)  
**Priority:** Low

**Goals:** Integrate with MetaGrid for dataset discovery

**Tasks:**
- Research MetaGrid API
- Publish dataset metadata to MetaGrid
- Support MetaGrid search integration
- Alternative/complement to STAC catalog

---

## Testing Strategy

### Unit Tests
- All core modules (converter, STAC, data sources, storage)
- Scheduler implementations
- CLI commands
- Target: >80% code coverage

### Integration Tests
- API endpoints with authentication
- Worker job processing end-to-end
- STAC catalog asset update flow
- Local workflow and output layout
- Future output adapters (S3/Globus)
- Globus Auth integration
- Scheduler integration (with mocks)

### End-to-End Tests
- Complete workflows: submit → process → write locally alongside source data
- CLI workflows matching PRD examples
- Multi-file conversion with various concat strategies
- Error scenarios and recovery

### Performance Tests
- Benchmark datasets:
  - Small: single file, <1GB
  - Medium: 10-100 files, 1-10GB total
  - Large: 100-1000+ files, 10-100GB+ total
- Measure job throughput (jobs/hour)
- Scalability: concurrent jobs (10, 50, 100)
- Dask parallelization efficiency
- API latency under load
- Memory usage profiling

### Security Tests
- Authentication/authorization (Globus Auth)
- Input validation and sanitization
- SQL/command injection prevention
- Credential handling (no leakage in logs/errors)
- Output path traversal attacks
- Rate limiting

### CMIP6/CMIP7 Specific Tests
- Test with real CMIP6 datasets from ESGF
- Various variables (tas, pr, tos, etc.)
- Different grid types and resolutions
- Historical, scenario, and control experiments
- CMIP7 datasets (as available)
- Validate STAC metadata accuracy

---

## Documentation Plan

### User Documentation
- **Getting Started Guide**
  - Installation (Docker Compose)
  - First job submission
  - Monitoring jobs
  - Retrieving results
  
- **CLI Reference**
  - All commands with examples from PRD
  - Option descriptions
  - Common workflows
  
- **API Reference**
  - Auto-generated from OpenAPI spec
  - Authentication guide
  - Request/response examples
  - Error codes
  
- **Tutorials**
  - Converting CMIP6 datasets
  - Batch job submission
  - Publishing to STAC catalog
  - Optimizing chunk strategies
  
- **FAQ**
  - Common issues and solutions
  - Performance tips
  - Storage configuration

### Developer Documentation
- **Architecture Overview**
  - System design
  - Component interactions
  - Data flow diagrams
  - No internal storage architecture
  
- **Development Setup**
  - Local development environment
  - Running tests
  - Contributing guidelines
  
- **Code Standards**
  - Python style guide (Black, ruff)
  - Type hints
  - Docstring format
  
- **API Design**
  - RESTful principles
  - Versioning strategy
  - Deprecation policy
  
- **Extension Points**
  - Adding new schedulers
  - Custom metadata extractors
  - Storage backend plugins

### Operational Documentation
- **Deployment Guide**
  - Docker Compose setup
  - Kubernetes deployment with Helm
  - Environment configuration
  - Scaling strategies
  
- **Configuration Reference**
  - All environment variables
  - Redis configuration
  - Dask cluster settings
  - STAC catalog connection
  - Globus Auth setup
  
- **Monitoring**
  - Prometheus metrics
  - Log aggregation
  - Alerting setup
  - Performance tuning
  
- **Troubleshooting**
  - Common errors and fixes
  - Job failure debugging
  - Network/storage issues
  - Performance problems
  
- **Security**
  - Authentication configuration
  - Credential management
  - Network security
  - Compliance considerations

### ESGF-Specific Documentation
- **ESGF Integration Guide**
  - Accessing ESGF datasets
  - STAC catalog asset updates for CMIP6/7
  - CMIP DRS conventions
  - ESGF-NG roadmap alignment

---

## Risk Mitigation

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Large file processing failures | High | Streaming, chunked processing, Dask parallelization |
| Memory exhaustion | High | Dask memory management, worker limits, spilling |
| Network I/O bottlenecks | Medium | Connection pooling, async I/O, retries |
| User storage permissions | High | Pre-flight validation, clear error messages |
| STAC catalog downtime | Medium | Queue updates locally, retry with backoff |
| Kerchunk library limitations | Medium | Stay current with upstream, contribute fixes |
| S3 API rate limits | Medium | Exponential backoff, connection pooling |

### Schedule Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| ESGF-NG API changes | Medium | Regular sync with ESGF team, API versioning |
| Dependency delays | Medium | Pin versions, vendor critical dependencies |
| Feature creep | High | Strict MVP scope, defer stretch goals to post-launch |
| Resource constraints | High | Prioritize features, adjust timeline, seek help |
| Testing delays | Medium | Parallel testing with development, automate |

### Integration Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| STAC schema evolution | Medium | Version pinning, compatibility layer |
| Globus Auth API changes | Low | Monitor release notes, SDK updates |
| Scheduler API differences | Medium | Abstraction layer, test on target systems early |
| CMIP7 metadata changes | Medium | Flexible metadata extraction, configurable templates |
| User storage incompatibilities | High | Support major cloud providers, clear documentation |

---

## Success Metrics

### MVP Success Criteria (Week 16 / 4 Months)
These criteria are already captured in the "MVP COMPLETE" section above. Refer to that section for the full list of success criteria.

### Post-MVP Operational Metrics
- **Usage Metrics**
  - Jobs processed per day (target: 100+)
  - Datasets cataloged per week
  - Unique users/sites deployed (target: 5+ sites)
  - Data volume processed (TB/month)

- **Performance Metrics**
  - Average job completion time by dataset size
  - API response time p95 (target: <500ms)
  - Worker throughput (files/hour)
  - Dask speedup factor vs sequential

- **Reliability Metrics**
  - Job success rate (target: >95%)
  - API uptime (target: 99.5%)
  - STAC publication success rate (target: >98%)
  - Mean time to recovery from failures

- **User Satisfaction**
  - User feedback score
  - Documentation clarity rating
  - Feature requests prioritization
  - Community engagement (GitHub stars, issues, contributions)

---

## Timeline Summary - 4 Month MVP Plan

| Stage | Duration | Weeks | Description |
|-------|----------|-------|-------------|
| 0 | 1 week | 1 | Project Setup & Foundation |
| 1 | 1 week | 2 | Core Kerchunk Conversion |
| 2 | 2 weeks | 3-4 | Job Queue System + Basic API + Local CLI Smoke Test |
| 3 | 1 week | 5 | Remote Data Source Support (S3, local) |
| 4 | 2 weeks | 6-7 | STAC Catalog Integration (server-configured) |
| 5 | 1 week | 8 | Dask Parallelization |
| 6 | 2 weeks | 9-10 | Advanced Features (validation, monitoring, metadata) |
| 7 | 2 weeks | 11-12 | Docker, Kubernetes & CLI Tool |
| 8 | 2 weeks | 13-14 | Globus Auth Integration |
| 9 | 2 weeks | 15-16 | Production Hardening & Final Testing |
| **MVP COMPLETE** | **16 weeks** | **4 months** | **Production-Ready Release** |

### Key Development Strategies

**1. Parallel Development Opportunities (2-3 developers)**
- Weeks 5-8: Developer A on local workflow + Dask, Developer B on STAC integration
- Weeks 9-12: Developer A on advanced features, Developer B on Kubernetes/Docker/full CLI UX
- Weeks 13-14: All developers on Globus Auth integration
- Weeks 15-16: All developers on production hardening and testing

**2. MVP Scope - Production-Ready System**
- Core conversion with Dask parallelization
- User-managed storage (local filesystem only for MVP)
- Server-configured STAC catalog (future publish path)
- Production-ready Kubernetes deployment with Helm
- Comprehensive monitoring and observability
- Full authentication (Globus Auth)
- Advanced validation and error handling
- Complete documentation

**3. Deferred to Post-MVP (based on user feedback)**
- Compute scheduler integration (Globus Compute, SLURM, PBS) - 3-4 weeks
- Web UI for broader adoption - 4-6 weeks
- VirtualiZarr support - 2-3 weeks
- Kafka consumer for event-driven workflows - 2-3 weeks
- MetaGrid integration - TBD

**4. Testing Throughout Development**
- Unit tests written alongside code (target: >80% coverage)
- Integration tests run nightly
- Performance benchmarks run weekly
- CMIP6 test datasets prepared in Stage 0
- Security audit integrated into Stage 9
- User acceptance testing in Stage 9

**5. Security-First Approach**
- Server-configured STAC catalog (prevents malicious publications)
- Input validation at all layers
- Credential management (never exposed to users)
- Container security scanning
- Rate limiting and abuse prevention

---

## Next Steps

1. **Stakeholder Review** (Week 0)
   - Review and approve implementation plan
   - Confirm timeline and resource allocation
   - Identify CMIP6 test datasets
   - Establish communication channels with ESGF-NG team

2. **Project Kickoff** (Week 1, Stage 0)
   - Set up repository and project structure
   - Configure development environment
   - Establish CI/CD pipeline
   - Create project documentation site

3. **ESGF Coordination** (Ongoing)
   - Regular sync meetings with ESGF-NG STAC team
   - Align on STAC schema for CMIP6/7
   - Coordinate STAC catalog API access
   - Share roadmap updates

4. **Test Data Preparation** (Week 1-2)
   - Identify representative CMIP6 datasets for testing
   - Set up test S3 buckets or storage
   - Prepare test STAC catalog instance
   - Document test scenarios

5. **Team Assignment** (Week 1)
   - Assign developers to initial stages
   - Identify specialists for Globus, STAC, HPC integration
   - Set up sprint planning and standup meetings
   - Establish code review process

---

## Appendix: Key Architectural Decisions

### 1. No Internal Storage
- **Decision:** Data-Forge does NOT store reference files internally
- **Rationale:** Reduces operational complexity, storage costs, and scaling challenges
- **Implication:** Users must provide accessible output paths (S3, web servers, etc.)

### 2. Service-Level STAC Authentication
- **Decision:** Service authenticates to STAC catalog, catalog is public read-only
- **Rationale:** Simplifies user experience, enables public dataset discovery
- **Implication:** Secure credential management for service, no per-user STAC credentials

### 3. Dask for Job-Level Parallelization
- **Decision:** Use Dask within each job to parallelize multi-file processing
- **Rationale:** Significant speedup for large datasets, Python-native, flexible
- **Implication:** Additional memory and cluster management complexity

### 4. Dramatiq + Redis for Job Queue
- **Decision:** Dramatiq with Redis backend for MVP job scheduling
- **Rationale:** Simple, reliable, good enough for single-node deployments
- **Future:** May extend with Celery or cloud-native queues for large-scale deployments

### 5. Modular Scheduler Architecture
- **Decision:** Abstract scheduler interface supporting local, Globus Compute, SLURM, PBS
- **Rationale:** Flexibility for different deployment environments (cloud, HPC, hybrid)
- **Implication:** Additional development and testing for each scheduler type

### 6. CLI-First User Experience
- **Decision:** CLI tool as primary user interface for MVP
- **Rationale:** Data publishers are technical users comfortable with command-line tools
- **Future:** Web UI as stretch goal for broader adoption
