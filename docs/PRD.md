# **Product Requirements Document (PRD): Data-Forge**

---

## **1\. Overview**

* **Name:** Data-Forge (working title)  
* **Primary Purpose:** To generate file representations (starting with Kerchunk) and update/provide catalogs for users, streamlining data access and management for climate datasets.  
* **Target Users:** Climate scientists  
* **Provides:** An asynchronous service for sites that lack job schedulers or resources, e.g. could run alongside esgf-docker stack

---

## **2\. Objectives and Goals**

* **Main Objectives:**

  * Reduce manual effort and required technical knowledge for generating file representations and catalogs.  
  * Improve accessibility of climate datasets.  
  * Disseminate datasets efficiently to the scientific community.  
* **Key Success Metrics:**

  * Number of catalogs generated.  
  * User adoption rate among climate scientists.  
  * Time saved in data preparation and access.

---

## **3\. User Stories/Use Cases**

1. **Generate Kerchunk Representations:** *"As a data provider/publisher, I want to generate kerchunk representations of datasets to provide efficient access to large datasets."*

2. **Centralized Dataset Discovery:** *"As a climate scientist, I want a central point to find datasets that have been converted to Kerchunk, so I can easily locate and use relevant data."*

3. **Efficient Data Access:** *"As a climate scientist, I want to efficiently access Kerchunk datasets with common data science tools (e.g., xarray, Dask), so I can integrate them into my workflows without performance bottlenecks."*

### **Workflows**

* **Input:** Large/multiple NetCDF files.  
* **Process:** Generate Kerchunk representations and catalog the outputs.  
* **Output:** Kerchunk files and updated catalogs for easy discovery and access.

---

## **4\. Functional Requirements**

* **Core Features:**

  1. Kerchunk conversion (from NetCDF, Zarr, etc.).  
     * Support chunk strategy: which dimensions  
     * Different grids  
  2. Provide Kerchunk files for download or direct access.  
  3. Register Kerchunk files as STAC item assets or Globus collection.  
  4. API access (web interface and CLI tool).  
  5. Asynchronous job monitoring.  
* **Integrations:**

  1. Globus (catalogs, authentication).  
     * For non ESGF-NG projects  
  2. STAC (catalogs)  
     * Primary target (priority) for CMIP7 and CMIP6(plus) backfilling  
* **User Flow:**

  1. Provide desired data via publicly accessible links i.e. (S3 store, https from ESGF catalog, etc).  
  2. Convert files to Kerchunk representations.  
  3. Upload kerchunk as ancillary data for a dataset.  
     * Push to ESGF-NG STAC catalog

---

## **5\. Non-Functional Requirements**

* **Performance Expectations:**

  * Fast conversion speed for large datasets.  
  * Low latency for catalog searches.  
  * Minimal access time for Kerchunk files.  
* **Security and Compliance:**

  * Access control managed via Globus Auth.  
* **Supported Platforms:**

  * Command-line interface (CLI).  
  * Cloud deployment.  
  * On-premises deployment.

---

## **6\. Technical Specifications**

* **Technology Stack:**

  * Backend: FastAPI (API), Redis \+ dramatiq (job queueing).  
    * Dask job level parallelization  
  * Containerization: Docker.  
  * Deployment: Bare-metal, Container, Docker-compose (for docker), Helm (for Kubernetes).  
* **Integrations:**

  * Globus (authentication and catalogs).  
  * STAC (catalogs).  
  * Compute schedulers (Globus Compute, Slurm, PBS, etc)

---

## **7\. Timeline and Roadmap**

* **Desired Launch Date:** \~May 2026 (6 months from now).  
* **Key Milestones:**  
  * **MVP:** Conversion service w/API, push STAC catalog (Month 6).  
  * **Stretch**: Web UI, Compute/scheduler integration, VirtualiZarr support

---

## **8\. Risks and Dependencies**

* **Potential Risks:**

  * Resource constraints (development, testing, infrastructure).  
  * Dependency delays (e.g., Globus/STAC updates, third-party services).  
* **Dependencies:**

  * Globus Auth and data transfer.  
    * Transfer would be needed for ANL  
  * ESGF NG: design docs   
    * https://github.com/ESGF/esgf-roadmap/  
  * STAC compliance and schema updates.  
  * Potential MetaGrid integration (if pursued).

---

## **9\. Alternate/complimentary implementation**

* Reference/template for how-to submit jobs to generate Kerchunk files at sites with compute systems, e.g. SLURM, PBS, Globus compute.  
* Add-on Kafka queue consumer that generates in some circumstances.

## **10\. Example code:**

    for nc\_file in netcdf\_files:  
            with fsspec.open(nc\_file, mode="rb") as infile:  
                h5chunks \= SingleHdf5ToZarr(infile, nc\_file, inline\_threshold=300)  
                \# You can save each reference file to disk or store them in memory  
                \# For demonstration, we'll just keep the translated dict in a list  
                reference\_files.append(h5chunks.translate())  
      
    \# Combine the references, concatenating along the 'time' dimension  
    \# 'identical\_dims' lists variables that should not be concatenated  
    mzz \= MultiZarrToZarr(reference\_files, concat\_dims=\['time'\], identical\_dims=\['lat', 'lon', 'lat\_bnds', 'lon\_bnds'\]).translate()

**11\. Testing Plan**

* Benchmarking datasets and tests  
* Maybe use the REF