<img alt="NSIDC logo" src="https://nsidc.org/themes/custom/nsidc/logo.svg" width="150" />


# Noaadata-web-server-metrics

Noaadata-web-server-metrics enables anyone to use the scripts that show the 
metrics NSIDC NOAA dataset downloads. The data is hosted in this repo: [noaadata-web-server](https://github.com/nsidc/noaadata-web-server)

## Level of Support

* This repository is not actively supported by NSIDC but we welcome issue 
  submissions and pull requests in order to foster community contribution.

See the [LICENSE](LICENSE) for details on permissions and warranties. Please 
contact nsidc@nsidc.org for more information.

## Requirements

Docker + docker-compose

OR

Python + Conda

## Installation

Install a pre-built image from DockerHub:

`docker pull nsidc/noaadata-web-server-metrics`

## Usage

There are two cli functions to run.
1. Ingest:
  The ingest function will run daily to read in the download logs and then output daily json files to /share/logs with necessary information for the report. The two arguments this function takes are:
  * start date (`-s` or `--start_date`)
  * end date (`-e` or `--end_date`)
  `PYTHONPATH=. python noaa_metrics/cli.py ingest -s 2023-01-01 -e 2023-04-07`
2. Report
  The report function generates the CSV report that will be mailed to recipients. This function takes:
  * start date (`-s` or `--start_date`)
  * end date (`-e` or `--end_date`) 
  * mailto (`-m` or `--mailto`) This entry is the email list and can take multiple emails 
  * dataset (`-d` or `--dataset`) The default for dataset is all datasets.
  `PYTHONPATH=. python noaa_metrics/cli.py report -s 2023-01-01 -e 2023-04-07 -m email@email.com`

## With Docker
TODO

## Without Docker
TODO

## Troubleshooting

TODO

## License

See [LICENSE](LICENSE).

## Code of Conduct

See [Code of Conduct](CODE_OF_CONDUCT.md).

## Credit

This software was developed by the National Snow and Ice Data Center with 
funding from multiple sources.
