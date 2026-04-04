# **Product Requirements Document (PRD): Data-Forge**

---

## **1. Overview**

* **Name:** Data-Forge (working title)  
* **Primary Purpose:** To generate reference files (starting with Kerchunk) and update/provide catalogs for users, streamlining data access and management for climate datasets.  
* **Target Users:** Data publishers  
* **Provides:** An asynchronous service to generate reference files (Kerchunk to start) and (optionally) upload them and attach them as assets on existing STAC Items, enabling data publishers to create and catalog reference files at sites that lack job schedulers or dedicated compute resources

---

## **2. Objectives and Goals**

* **Main Objectives:**

  * Reduce manual effort and required technical knowledge for generating Kerchunk reference files and catalogs.  
  * Improve accessibility of climate datasets.  
  * Disseminate datasets efficiently to the scientific community.  
* **Key Success Metrics:**

  * Number of reference files generated and published to catalogs.  
  * Adoption rate among data publishers.  
  * Time saved in reference file generation and catalog publishing.  
  * Successful job completion rate.

---

## **3. User Stories/Use Cases**

1. **Submit Reference File Generation Jobs:** *"As a data publisher, I want to submit asynchronous jobs to generate Kerchunk reference files from my NetCDF datasets, so I can provide efficient access to large datasets without blocking my workflow."*

2. **Update STAC Catalog Assets:** *"As a data publisher, I want the service to upload generated Kerchunk reference files and update an existing STAC Item to include them as assets, so that users can discover and access my datasets through standard catalog interfaces."*

3. **Monitor Job Progress:** *"As a data publisher, I want to monitor the status and progress of my reference file generation jobs, so I can track completion and troubleshoot any issues."*

4. **Configure Generation Parameters:** *"As a data publisher, I want to specify chunk strategies and dimensions for Kerchunk generation, so I can optimize reference files for my specific data access patterns."*

5. **Batch Process Multiple Datasets:** *"As a data publisher, I want to submit multiple dataset conversion jobs at once, so I can efficiently process large collections of NetCDF files."*

6. **Retrieve Generated Reference Files:** *"As a data publisher, I want to download or directly access the generated Kerchunk reference files, so I can validate them before publishing or use them in my own workflows."*

7. **Manage Published Datasets:** *"As a data publisher, I want to view and manage my published STAC catalog entries, so I can update metadata or remove outdated datasets."*

### **Workflows**

* **Input:** Large/multiple NetCDF files.  
* **Process:** Generate Kerchunk reference files and (optionally) upload + update STAC assets.  
* **Output:** Kerchunk reference files and updated STAC catalog assets for easy discovery and access.

---

## **4. Functional Requirements**

* **Core Features:**

  1. Kerchunk conversion (from NetCDF, Zarr, etc.).  
     * Support chunk strategy: which dimensions  
     * Different grids  
  2. Provide Kerchunk reference files for download or direct access.  
  3. Upload Kerchunk reference files (optional) and update an existing STAC Item to include them as assets in the ESGF-NG STAC catalog.  
  4. API access (REST API and CLI tool).  
  5. Asynchronous job monitoring and status tracking.  
* **Integrations:**

  1. Globus Auth (API authentication and access control).  
  2. ESGF-NG STAC catalog (publishing and metadata management).  
     * Primary target for CMIP7 and CMIP6(plus) backfilling
* **User Flow:**

  1. Authenticate to Data-Forge API via Globus Auth.  
  2. Submit job with desired data via publicly accessible links (S3 store, HTTPS from ESGF catalog, etc).  
  3. Monitor job progress and status.  
  4. System converts files to Kerchunk reference files asynchronously.  
  5. Optional: System uploads Kerchunk reference files and updates an existing STAC Item to include them as assets in ESGF-NG STAC catalog.  
  6. Optional: Download reference files for validation or local use.

---

## **5. Non-Functional Requirements**

* **Performance Expectations:**

  * Fast reference file generation for large datasets.  
  * Quick catalog update times.  
  * Efficient job queue processing with minimal latency.  
* **Reliability:**

  * Retries with exponential backoff (and jitter) for transient failures during upload and STAC updates (e.g., timeouts, 429, 5xx).  
* **Security and Compliance:**

  * API access control managed via Globus Auth.  
  * STAC catalog is local and unauthenticated (read-only public access).  
* **Access Methods:**

  * REST API (programmatic access)  
  * Command-line interface (CLI)  
* **Deployment Platforms:**

  * Cloud environments (AWS, Azure, GCP)  
  * On-premises/bare-metal servers  
  * Docker containers  
  * Kubernetes clusters

---

## **6. Technical Specifications**

* **Technology Stack:**

  * Backend: FastAPI (REST API), Redis + dramatiq (job queueing and scheduling).  
    * Dask for job-level parallelization  
  * Authentication: Globus Auth SDK.  
  * Catalog: STAC API client for ESGF-NG STAC catalog.  
    * Service uses configured credentials/API tokens to update existing STAC Items (asset patching)  
  * Storage: User-provided storage locations (S3 and local filesystem).  
    * Data-Forge writes reference files to user-specified output paths (local or S3)  
    * In "ESGF publish" mode, Data-Forge uploads the reference file via a server-configured publishing endpoint and patches STAC to reference the uploaded URL  
  * Containerization: Docker.  
  * Deployment: Docker-compose (single node), Helm charts (Kubernetes).
* **Integrations:**

  * Globus Auth (API authentication).  
  * ESGF-NG STAC catalog (updating existing Items with generated reference file assets).  
  * Dramatiq + Redis (MVP: local asynchronous job scheduling).  
  * Compute schedulers (Stretch: Globus Compute, Slurm, PBS, etc).

---

## **7. Timeline and Roadmap**

* **Desired Launch Date:** ~May 2026 (6 months from now).  
* **Key Milestones:**  
  * **MVP (Month 6):**  
    * REST API with Globus Auth authentication  
    * CLI tool for job submission and monitoring  
    * Kerchunk reference file generation (NetCDF support)  
    * Optional: ESGF publish (upload) and STAC Item asset update  
    * Local dramatiq + Redis job scheduling  
  * **Stretch Goals:**  
    * Compute/scheduler integration (Globus Compute, Slurm, PBS)  
    * VirtualiZarr support  
    * Additional input formats (HDF5, GRIB)  
    * Advanced chunking strategies and optimization

---

## **8. Risks and Dependencies**

* **Potential Risks:**

  * Resource constraints (development, testing, infrastructure).  
  * Dependency delays (e.g., Globus/STAC updates, third-party services).  
* **Dependencies:**

  * Globus Auth for API authentication.  
  * User-provided storage infrastructure (S3 buckets and/or local filesystem access).  
  * ESGF-NG STAC catalog API access (requires service credentials).  
  * ESGF publishing endpoint API access (requires service credentials).  
  * ESGF NG: design docs   
    * https://github.com/ESGF/esgf-roadmap/  
  * STAC compliance and schema updates.  
  * Potential MetaGrid integration (if pursued).

---

## **9. Alternate/Complementary Implementation**

* Reference/template documentation for how to submit jobs to generate Kerchunk reference files at sites with existing compute schedulers (e.g., SLURM, PBS, Globus Compute).  
* Add-on Kafka queue consumer for event-driven generation in specific scenarios.  
* Integration hooks for sites with existing job scheduling infrastructure.

## **10. Example Usage**

### **CLI Examples**

#### **Authentication**
```bash
# Login via Globus Auth
$ data-forge login
Opening browser for Globus authentication...
Authentication successful!
```

#### **Submit Single Dataset Job**
```bash
# Submit job for a single NetCDF file
$ data-forge submit \
  --input "s3://esgf-data/CMIP6/CMIP/NCAR/CESM2/historical/r1i1p1f1/Amon/tas/gn/v20190308/*.nc" \
  --dataset-id "CMIP6.CMIP.NCAR.CESM2.historical.Amon.tas" \
  --concat-dims time \
  --output-path "s3://kerchunk-refs/CMIP6/NCAR/CESM2/"

Job submitted successfully!
Job ID: job-abc123-def456
Status: queued
```

#### **Submit with Advanced Options**
```bash
# Submit with custom chunk strategy and metadata
$ data-forge submit \
  --input "https://esgf-node.llnl.gov/thredds/fileServer/cmip6/CMIP6/.../*.nc" \
  --dataset-id "CMIP6.ScenarioMIP.IPSL.IPSL-CM6A-LR.ssp585" \
  --concat-dims time \
  --identical-dims "lat,lon,lat_bnds,lon_bnds" \
  --inline-threshold 300 \
  --metadata '{"project": "CMIP6", "institution": "IPSL"}'

Job submitted successfully!
Job ID: job-xyz789-uvw012
Status: queued

# Write to local filesystem
$ data-forge submit \
  --input "s3://my-data/dataset/*.nc" \
  --dataset-id "my.dataset.id" \
  --output-path "./kerchunk_refs/"

# ESGF publish (upload + update existing STAC Item asset)
$ data-forge submit \
  --input "s3://my-data/dataset/*.nc" \
  --dataset-id "my.dataset.id" \
  --esgf-publish \
  --stac-collection-id "cmip6" \
  --stac-item-id "my.dataset.id" \
  --stac-asset-key kerchunk_reference
```

#### **Monitor Job Status**
```bash
# Check status of specific job
$ data-forge status job-abc123-def456

Job ID: job-abc123-def456
Status: running
Progress: 45/100 files processed
Started: 2026-02-13 10:30:15 UTC
Estimated completion: 2026-02-13 11:15:00 UTC

# Watch job progress in real-time
$ data-forge status job-abc123-def456 --watch
```

#### **List Jobs**
```bash
# List all jobs
$ data-forge list

JOB ID              STATUS     DATASET ID                          SUBMITTED
job-abc123-def456   completed  CMIP6.CMIP.NCAR.CESM2...           2026-02-13 09:00:00
job-xyz789-uvw012   running    CMIP6.ScenarioMIP.IPSL...          2026-02-13 10:30:15
job-mno345-pqr678   failed     CMIP6.CMIP.MPI-M.MPI-ESM1-2...     2026-02-13 08:45:30

# Filter by status
$ data-forge list --status completed --limit 10
```

#### **Retrieve Reference Files**
```bash
# Download generated reference file
$ data-forge download job-abc123-def456 --output ./kerchunk_refs/

Downloading reference file...
Saved to: ./kerchunk_refs/CMIP6.CMIP.NCAR.CESM2.historical.Amon.tas.json

# Get reference file URL
$ data-forge get-url job-abc123-def456

s3://kerchunk-refs/CMIP6/NCAR/CESM2/CMIP6.CMIP.NCAR.CESM2.historical.Amon.tas.json
```

#### **View STAC Catalog Entry**
```bash
# View published STAC item
$ data-forge stac show job-abc123-def456

STAC Item ID: CMIP6.CMIP.NCAR.CESM2.historical.Amon.tas
Catalog: https://esgf-stac.llnl.gov/
Published: 2026-02-13 10:45:30 UTC
Assets:
  - kerchunk_reference: https://esgf-publish.example.org/kerchunk/.../tas.json
```

#### **Batch Job Submission**
```bash
# Submit multiple jobs from a configuration file
$ data-forge submit --batch jobs_config.yaml

Submitting 25 jobs from jobs_config.yaml...
✓ 25 jobs submitted successfully

Job IDs:
  - job-aaa111-bbb222
  - job-ccc333-ddd444
  ...
```

### **Internal Kerchunk Processing (Reference)**

For reference, the service internally uses Kerchunk as follows:

```python
from kerchunk.hdf import SingleHdf5ToZarr
from kerchunk.combine import MultiZarrToZarr
import fsspec

# Process individual NetCDF files
reference_files = []
for nc_file in netcdf_files:
    with fsspec.open(nc_file, mode="rb") as infile:
        h5chunks = SingleHdf5ToZarr(infile, nc_file, inline_threshold=300)
        reference_files.append(h5chunks.translate())

# Combine references, concatenating along the 'time' dimension
mzz = MultiZarrToZarr(
    reference_files,
    concat_dims=['time'],
    identical_dims=['lat', 'lon', 'lat_bnds', 'lon_bnds']
).translate()
```

## **11. Testing Plan**

### **Unit Testing**
* Kerchunk generation logic with various NetCDF file structures  
* STAC catalog API integration (create, update, delete items)  
* Job queue management (submission, status updates, completion)  
* Authentication and authorization flows with Globus Auth  

### **Integration Testing**
* End-to-end workflow: job submission → generation → STAC publishing  
* Multi-file dataset aggregation and concatenation  
* Error handling and retry mechanisms  
* Concurrent job processing  

### **Performance Testing**
* Benchmark datasets of varying sizes (1GB, 10GB, 100GB+)  
* Job queue throughput and latency measurements  
* Dask parallelization efficiency  
* Memory usage profiling for large datasets  

### **Acceptance Testing**
* Reference CMIP6 datasets for validation  
* ESGF community test datasets  
* Verify STAC catalog compliance and searchability  
* CLI tool usability testing with data publishers  

### **Test Datasets**
* CMIP6 sample datasets from ESGF  
* Various grid types (regular, irregular, curvilinear)  
* Different temporal resolutions and aggregation patterns  
* Edge cases: single-file, multi-file, large ensembles
