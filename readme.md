### Local Electoral Body Reservations

Data on local electoral body (ULB and PRI) reservations.

See **[SOURCES.md](SOURCES.md)** for a state-by-state feasibility survey: where
each state publishes its reservation data, whether the files are text or scans,
and which states are already sitting in `data/` waiting to be parsed. The table
below tracks coverage; SOURCES.md tracks what it would take to extend it.

`data/` holds raw source documents for several states whose rows here are still
blank — run `python scripts/inventory.py` to classify them.


| State                                    | Year(s) | Contributor(s) | 
| ---------------------------------------- | ------- | ------- | 
|  Andaman & Nicobar Islands               |        | | 
| [Andhra Pradesh](data/ap/)               | 2020 raw gazettes, unparsed | |
| Arunachal Pradesh                        |   | |
| [Assam](data/assam/)                     | 2020 municipal only | |
| [Bihar](data/bihar/)                          | 2006, 2011, 2016    | Aaditya Dar for 2006 and 2011 |
| Chattisgarh                              |  | |
| Chandigarh                               |  | |
| Dadra & Nagar Haveli                     |  | |
| Daman & Diu                              |  | |
| [Goa](data/goa/)                         | 2012, 2017, 2022 raw, unparsed | |
| Gujarat                                  |   |. |
| [Haryana](https://github.com/in-rolls/local_elections_haryana) | 2016, 2022 | |
| [Himachal Pradesh](data/himachal/)       | one district, 2020 | |
| [Jammu & Kashmir](data/jk/)              | 2010, 2016, 2018 raw, unparsed | |
| [Jharkhand](data/jharkhand/)             | 2010, 2015 mukhiya, 2022 raw | |
| Lakshadweep                              |   |  |
| [Karnataka](data/karnataka/)             | GP reservation history (.dta) | Thad Dunning|
| [Kerala](data/kerala/)                        |   | Thad Dunning|
| [Madhya Pradesh](data/madhya_pradesh/)   | raw, scanned | |
| [Maharashtra](data/maharashtra/)         | Mumbai 2007, 2012, 2017 (urban only; ~28k rural GPs missing) | Varun Karekurve-Ramachandra |
| Manipur                                  |  | |
| Meghalaya                                |  | |
| Mizoram                                  |  | |
| Nagaland                                 |  | | 
| [NCT OF Delhi](data/delhi/)                   | 2007, 2012, 2017| Varun Karekurve-Ramachandra |
| [Odisha](data/odisha/)                   | 2017 district totals only | |
| Punjab                                   |     |  |
| [Puducherry](data/puducherry/)           | 2021 raw | |
| [Rajasthan](data/rajasthan/)                  |  2004--2019 for urban and 2005--2020 for panchayat + 2020--2021 from the website  |  |
| Sikkim                                   |     |  |
| [Tamil Nadu](data/tamil_nadu/)           | municipal only | |
| Telangana                                |  2018--2023   |  |
| Tripura                                  |     |  |
| [Uttar Pradesh](data/up/)                     |  2015, 2021  |  |
| [Uttarakhand](data/uttarakhand/)              |  2008, 2013, 2018-19 for urban and 2008, 2014, 2019 for panchayat   | |
| [West Bengal](wb/)                       |  2013 for panchayat, 2008-2018 for municipal  | |


### Other Sources

* https://github.com/tcpd/Urban_Local_Body
