<img alt="NSIDC logo" src="https://nsidc.org/themes/custom/nsidc/logo.svg" width="150" />


# Noaadata-web-server-metrics

Noaadata-web-server-metrics enables anyone to use the scripts that show the 
metrics for the NSIDC NOAA dataset downloads. The data is hosted in this repo: [noaadata-web-server](https://github.com/nsidc/noaadata-web-server)

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
  The ingest function will run daily to read in the download logs and then output daily json files to /share/logs with necessary information for the report. Use `--help` to learn more.

2. Report
  The report function generates the CSV report that will be mailed to recipients. Use `--help` to learn more. To send to multiple emails put `-m` before each email.

### With Docker
`source VERSION.env`.  
`./scripts/cli.sh ingest -s 2023-01-01 -e 2023-04-01`.  
`./scripts/cli.sh report -s 2023-01-01 -e 2023-04-01 -m email@colorado.edu -m email@email.com`. 

###  Without Docker
`PYTHONPATH=. python noaa_metrics/cli.py ingest -s 2023-01-01 -e 2023-04-07`.  
`PYTHONPATH=. python noaa_metrics/cli.py report -s 2023-01-01 -e 2023-04-07 -m email@email.com`. 

### NSIDC Ops Example
1. Deploy app with Garrison. 
2. Set the version properly. `source /opt/deploy/noaadata-web-server-metrics/VERSION.env`
3. Run ingest daily. `/opt/deploy/noaadata-web-server-metrics/scripts/cli.sh ingest -s 2023-01-01 -e 2023-01-01`
4. Run report on specified schedules or adhoc. `/opt/deploy/noaadata-web-server-metrics/scripts/cli.sh report -s 2023-01-01 -e 2023-04-01 -m roma8902@colorado.edu`

## Troubleshooting

Make sure that `share/logs/noaa-web/ingest` and `share/logs/noaa-web/report` are created in each environment.

`parse_nginx_logs.sh` was created in response to an issue listed in [PSS-677](https://nsidc.atlassian.net/browse/PSS-677)

The script is in `scripts` directory and can be run on the `access.log` if for some reason the `download.log` does not get created for a day or various days. An example of how this was run to recover the missing December days for PSS-667 is below:

```
grep "01/Dec/2024" /share/logs/noaa-web-all/production/access.log > ~/noaadata-web-server-metrics/scripts/01dec2024_access.log

./parse_nginx_lines.sh 01dec2024_access.log > 01dec2024_download.log
```

In that scenario if you then want to run the ingest locally you will need to change the input path in `noaa_metrics/ingest_logs.py`

## License

See [LICENSE](LICENSE).

## Code of Conduct

See [Code of Conduct](CODE_OF_CONDUCT.md).

## Credit

This software was developed by the National Snow and Ice Data Center with 
funding from multiple sources.
