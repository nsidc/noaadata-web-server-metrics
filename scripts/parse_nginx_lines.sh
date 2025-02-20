#!/bin/bash
#
# ./parse_nginx_lines.sh
#
# /share/logs/noaa-web/dev/roma8902/
# Usage:
#   ./parse_nginx_lines.sh <input_file> [> output_file]
# eg
#   ./parse_nginx_lines.sh access_line_sample.txt > download.log
#
# Note: input_file is in "access.log" format
# Note: output_file is in "download.log" format
#
#
#
# Format of access.log (input):
#    log_format main  '$remote_addr - $remote_user [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for"';
#
#
# Format of download.log (output):
#    log_format custom_download  '[$time_local] $request_time $remote_addr '
#                                '$body_bytes_sent $request_filename $status';
#
#
#  Sample access line:
#  (here access_line_sample.txt with this line repeated)
#     71.6.1.82 - - [04/Jan/2025:00:00:03 +0000] "GET /NOAA/G02158/unmasked/2025/01_Jan/SNODAS_unmasked_20250103.tar HTTP/1.1" 200 34191360 "-" "Wget/1.19.4 (linux-gnu)" "71.6.1.82"
#
#  Sample download line:
#  (here download_line_expected.txt) with this line repeated
#  [04/Jan/2025:00:00:03 +0000] 1.306 71.6.1.82 34191360 /usr/share/nginx/html/NOAA/G02158/unmasked/2025/01_Jan/SNODAS_unmasked_20250103.tar 200
# sample_download_line="[04/Jan/2025:00:00:03 +0000] 1.306 71.6.1.82 34191360 /usr/share/nginx/html/NOAA/G02158/unmasked/2025/01_Jan/SNODAS_unmasked_20250103.tar 200"

ifn="$1"
if [ -z "$ifn" ]; then
  echo "No file given"
  exit
fi

if [ ! -f "$ifn" ]; then
  echo "No such file: ${ifn}"
  exit
fi

debug=false
dummy_request_time=1.234
filename_prefix="/usr/share/nginx/html"
regex='^([^ ]+) ([^ ]+) ([^ ]+) (\[.*\]) (\"[^\"]+\") ([^ ]+) ([^ ]+)'
regex2='^([^ ]+) ([^ ]+) '
regex3='([^\ ]+\.[a-zA-Z0-9]+)$'

while IFS= read -r line; do
  # Process the line here
  printline=True
  #echo "Line: $line"

  # PAINFUL REGEX HERE!!!
  #     71.6.1.82 - - [04/Jan/2025:00:00:03 +0000] "GET /NOAA/G02158/unmasked/2025/01_Jan/SNODAS_unmasked_20250103.tar HTTP/1.1" 200 34191360 "-" "Wget/1.19.4 (linux-gnu)" "71.6.1.82"
  if [[ "$line" =~ $regex ]]; then
    ipaddress="${BASH_REMATCH[1]}"
    firstdash="${BASH_REMATCH[2]}"
    seconddash="${BASH_REMATCH[3]}"
    timestamp="${BASH_REMATCH[4]}"

    # Note: this will be used to compute "the_filename" below...
    firstquoted="${BASH_REMATCH[5]}"

    status_str="${BASH_REMATCH[6]}"
    bodybytes_str="${BASH_REMATCH[7]}"

    if [ "${debug}" == "True" ]; then
      echo "ipaddresss: ${ipaddress}"
      echo "firstdash: ${firstdash}"
      echo "seconddash: ${seconddash}"
      echo "timestamp: ${timestamp}"
      echo "firstquoted: ${firstquoted}"
      echo "status_str: ${status_str}"
      echo "bodybytes_str: ${bodybytes_str}"
    fi
  else
    # echo "OH GOD...DIDNT MATCH REGEX!!!"
    # echo "regex: ${regex}"
    printline=False
  fi

  if [[ "$firstquoted" =~ $regex2 ]]; then
    # Note: secondword includes the leading slash '/....'
    firstword="${BASH_REMATCH[1]}"
    if [[ "$firstword" == '"GET' ]]; then
      secondword="${BASH_REMATCH[2]}"
      if [[ "$secondword" =~ $regex3 ]]; then
        the_filename="${filename_prefix}${secondword}"
      else
        printline=False
      fi 
    else 
      printline=False
    fi 
  else
    printline=False
  fi

  if [ "${printline}" == "True" ]; then
    download_line="${timestamp} ${dummy_request_time} ${ipaddress} ${bodybytes_str} ${the_filename} ${status_str}"
    echo "${download_line}"
  fi
  #echo "${sample_download_line}"
done < "${ifn}"
