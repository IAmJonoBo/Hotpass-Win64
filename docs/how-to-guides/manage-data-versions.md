---
title: Managing data versions
summary: How to version datasets with DVC and track refined outputs
last_updated: 2025-11-02
---

# Managing data versions

This guide shows how to use DVC (Data Version Control) to version refined datasets and track data lineage in the Hotpass pipeline.

## Overview

Hotpass integrates DVC to provide:

- **Versioned storage** for refined datasets and backfill snapshots
- **Semantic versioning** (major.minor.patch) for datasets
- **Git-based tracking** of data changes without storing large files in Git
- **Recovery workflows** to restore specific dataset versions

## Prerequisites

Install the DVC extra if you haven't already:

```bash
uv sync --extra versioning
```

Or add it to your `HOTPASS_UV_EXTRAS`:

```bash
export HOTPASS_UV_EXTRAS="dev versioning"
bash ops/uv_sync_extras.sh
```

## Initializing DVC

Initialize DVC in your repository:

```bash
hotpass version --init
```

This creates a `.dvc` directory with configuration files. The command will prompt you to configure a remote storage location.

### Configuring remote storage

DVC supports multiple storage backends (S3, Azure Blob, Google Cloud Storage, local filesystem). Configure a remote:

```bash
# S3 example
dvc remote add -d storage s3://my-bucket/hotpass-data

# Local filesystem example (for development)
dvc remote add -d storage /mnt/data/hotpass-dvc

# Azure Blob Storage example
dvc remote add -d storage azure://my-container/hotpass-data
```

Commit the DVC configuration:

```bash
git add .dvc/config
git commit -m "Configure DVC remote storage"
```

## Tracking datasets

### Add datasets to DVC tracking

Track the `data/` inputs and `dist/` outputs:

```bash
# Track input data
hotpass version --add data/

# Track refined outputs
hotpass version --add dist/refined_data.xlsx
```

This creates `.dvc` files that track metadata about your datasets. Commit these files:

```bash
git add data.dvc dist/refined_data.xlsx.dvc
git commit -m "Track datasets with DVC"
```

### Check DVC status

View the status of tracked files:

```bash
hotpass version --status
```

## Managing semantic versions

### Set a specific version

Set the version for a dataset:

```bash
hotpass version --set 1.0.0 --dataset refined_data --description "Initial release"
```

### Bump versions

Increment version components automatically:

```bash
# Patch version (1.0.0 → 1.0.1) for bug fixes
hotpass version --bump patch --dataset refined_data

# Minor version (1.0.1 → 1.1.0) for new features
hotpass version --bump minor --dataset refined_data

# Major version (1.1.0 → 2.0.0) for breaking changes
hotpass version --bump major --dataset refined_data
```

### Get current version

View the current version for a dataset:

```bash
hotpass version --get refined_data
```

### Tag versions

Create Git tags for dataset versions:

```bash
hotpass version --bump patch --tag --dataset refined_data
```

This creates a Git tag like `refined_data-v1.0.1` for easy reference.

## Pushing and pulling data

### Push data to remote

After refining data, push it to the configured DVC remote:

```bash
dvc push
```

### Pull data from remote

On a new machine or after checking out a different branch:

```bash
dvc pull
```

This downloads the data files tracked by the `.dvc` files in your repository.

## Recovery and backfill workflows

### Restore a specific version

To restore data to a specific version:

1. Check out the git commit with the desired data version:

   ```bash
   git checkout refined_data-v1.0.0
   ```

2. Pull the data from the remote:

   ```bash
   dvc pull
   ```

3. The `dist/refined_data.xlsx` file now reflects version 1.0.0

### Compare versions

View version history:

```bash
git log --oneline --decorate | grep refined_data-v
```

Compare two versions:

```bash
# Check out the first version
git checkout refined_data-v1.0.0
dvc pull

# Save or note differences, then check out the second version
git checkout refined_data-v1.1.0
dvc pull

# Compare the files as needed
```

## Integration with pipeline runs

The pipeline automatically records version metadata when enabled:

```python
from hotpass.versioning import DVCManager, record_version_metadata, DatasetVersion

# In your pipeline or export step
manager = DVCManager(repo_root)
current_version = manager.get_version("refined_data")
new_version = current_version.bump("patch")

# Set the new version
manager.set_version(new_version, "refined_data")

# Record version metadata alongside outputs
record_version_metadata(
    output_path=Path("dist/refined_data.xlsx"),
    version=new_version,
    metadata={"records": 1000, "pipeline_run_id": "abc123"},
)
```

## CI/CD integration

In CI workflows, validate DVC setup without pushing data:

```yaml
- name: Check DVC status
  run: |
    uv run hotpass version --status

- name: Validate DVC tracking
  run: |
    dvc status --cloud
```

For production pipelines, push DVC metadata after successful runs:

```yaml
- name: Push DVC data
  if: github.ref == 'refs/heads/main'
  run: dvc push
```

## Best practices

1. **Version on significant changes**: Bump patch for data quality fixes, minor for new fields or records, major for schema changes.

2. **Tag important milestones**: Use `--tag` when releasing datasets to stakeholders.

3. **Document versions**: Always include `--description` when setting or bumping versions.

4. **Regular pushes**: Push to DVC remotes regularly to avoid data loss.

5. **Separate remotes**: Consider separate DVC remotes for development and production environments.

6. **Security**: Configure DVC remotes with appropriate access controls and encryption.

## Troubleshooting

### DVC not installed

If you see "DVC not installed", ensure the versioning extra is installed:

```bash
uv sync --extra versioning
```

### Remote not configured

If `dvc push` fails with "no remote configured", add a remote:

```bash
dvc remote add -d storage <remote-url>
```

### Permission errors

Ensure you have read/write access to the DVC remote storage location.

## See also

- [DVC documentation](https://dvc.org/doc)
- [Configure pipeline](configure-pipeline.md)
- [Orchestrate and observe](orchestrate-and-observe.md)
- [Roadmap tracking](../roadmap.md#phase-3--pipelines-ingest-backfill-refine-publish)
