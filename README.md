<p align="center">
  <img src="PYROGithub.png" width="850">
</p>

<h1 align="center">Pyro Domain Checker</h1>

<p align="center">
  TLD rotation • parked-page filtering • content scoring
</p>


![Python](https://img.shields.io/badge/python-3.11-blue)

## Features

- Checks a host across multiple TLDs from `Targets.txt`
- Finds domains that are actually online instead of just guessing
- Filters out parked domains, registrar pages, and “domain for sale” pages
- Detects dead domains, DNS failures, timeouts, and connection errors
- Catches basic placeholder pages like `Index of /`, `My Blog`, `Coming Soon`, and maintenance pages
- Scores pages based on the title, page content, links, and useful keywords
- Separates results into real matches, possible matches, and rejected domains
- Runs checks concurrently so scans finish fast
- Saves results to `results.json`, `working.txt`, `possible.txt`, and `rejected.txt`

 git clone https://github.com/wh1tebr34d/pyro-domain-checker
 cd pyro-domain-checker
 pip install -r requirements.txt
 python pyro.py aniwatch
  
## Screenshots

### Pyro Scan

![Pyro scan](Screenshot%202026-05-18%20203611.png)

### Pyro Results

![Pyro results](Screenshot%202026-05-18%20203633.png)

### Pyro Output Files

![Pyro output files](Screenshot%202026-05-18%20203640.png)
