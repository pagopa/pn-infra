# CDC Cache Updater

## Description

This script updates CDC tables in Parquet format from JSON source. It allows processing by year, specific months, or specific days.

## Installation

### Prerequisites

- Python 3.6 or higher  
- AWS CLI configured with appropriate permissions  

### Dependencies

Install dependencies:

pip install -r requirements.txt  

Note: The `requirements.txt` file only contains `boto3`.  

## Important Notes

- This script works **ONLY** on pn-core AWS accounts  
- It is **NOT** designed for AWS Confinfo accounts  
- Current day data is always skipped and will be processed by `UpdateCdcJsonViewsLambda` after midnight  

## Usage

### Before running

Authenticate with AWS SSO:

aws sso login --profile sso_pn-core-<env>  

### Required parameters

- `--envName`: Environment (dev, tes, uat, hotfix, prod)  
- `--table`: Base table name (example: pn_userattributes)  
- `--year`: Year to process (YYYY)  

### Optional parameters

- `--database`: Glue database name (default: `cdc_analytics_database`)  
- `--workgroup`: Athena workgroup (default: `cdc_analytics_workgroup`)  
- `--region`: AWS region (default: `eu-south-1`)  
- `--workers`: Maximum parallel workers (default: `12`)  
- `--months`: Specific months to process (comma-separated, e.g. `"01,02,03"`)  
- `--days`: Specific days to process (comma-separated, e.g. `"01,15,30"`)  

### Examples

#### Process entire year:

python update_cdc_cache_optimized_final.py --envName dev --table pn_userattributes --year 2024  

#### Process multiple specific months:

./update_cdc_cache_optimized_final.py --envName dev --table pn_userattributes --year 2024 --months "01,02,03"  

#### Process a single month:

./update_cdc_cache_optimized_final.py --envName dev --table pn_userattributes --year 2024 --months "05"  

#### Process specific days in a month:

./update_cdc_cache_optimized_final.py --envName dev --table pn_userattributes --year 2024 --months "05" --days "01,15,30"  

#### Process a single day:

./update_cdc_cache_optimized_final.py --envName dev --table pn_userattributes --year 2024 --months "05" --days "15"  

## Behavior with current date

- If processing the current year: the current day will be skipped  
- If processing the current month: the current day will be skipped  
- If trying to process only the current day: it will be skipped entirely  

The current day's data will always be processed by `UpdateCdcJsonViewsLambda` after midnight to ensure data completeness.
