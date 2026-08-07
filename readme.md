### Local Electoral Body Reservations

Data on local electoral body (ULB and PRI) reservations.

See **[SOURCES.md](SOURCES.md)** for a state-by-state feasibility survey: where
each state publishes its reservation data, whether the files are text or scans,
and what it would take to extend coverage.

The table below is **generated** — `make coverage` rebuilds it from the parsed
files, from `data/inventory.csv` for states still raw, and from the sibling
repositories, then checks that every link resolves. It drifted twice while
hand-maintained, so it is no longer hand-maintained.

*Status* means: **parsed** — in this schema, one row per seat-year;
**prior work, other schema** — real coverage contributed earlier, in its own
layout; **raw, unparsed** — source documents on disk, no parser yet;
**not held** — nothing acquired; **no PRI** — nothing to collect.


<!-- coverage:start -->

| State | Tier | Years | Rows | Status | Where |
|---|---|---|---|---|---|
| Andaman & Nicobar Islands | - | - | - | not held | - |
| Andhra Pradesh | sarpanch, ward | 2020 | 26,287 | parsed | [data/ap/](data/ap/) |
| Arunachal Pradesh | - | - | - | not held | - |
| Assam | - | - | - | raw, unparsed | [data/assam/](data/assam/) - 1 digital-text |
| Bihar | mukhiya, sarpanch, panch, ward | 2006, 2011, 2016 | 692,314 | parsed | [local_elections_bihar](https://github.com/in-rolls/local_elections_bihar) |
| Chandigarh | - | - | - | raw, unparsed | [data/chandigarh/](data/chandigarh/) - 4 digital-text, 1 scan |
| Chhattisgarh | - | - | - | not held | - |
| Dadra & Nagar Haveli and Daman & Diu | - | - | - | not held | - |
| Goa | ward | 2012, 2017, 2022 | 2,960 | parsed | [data/goa/](data/goa/) |
| Gujarat | - | - | - | not held | - |
| Haryana | sarpanch, ward | 2016, 2022 | 135,426 | parsed | [local_elections_haryana](https://github.com/in-rolls/local_elections_haryana) |
| Himachal Pradesh | - | - | - | not held | - |
| Jammu & Kashmir | sarpanch, ward | 2010, 2016, 2018 | 11,508 | parsed | [data/jk/](data/jk/) |
| Jharkhand | mukhiya, panchayat_samiti, ward_member, zila_parishad | 2015 | 11,711 | parsed | [data/jharkhand/](data/jharkhand/) |
| Karnataka | - | GP reservation history (.dta) | - | prior work, other schema | [data/karnataka/](data/karnataka/) |
| Kerala | ward | 2005, 2010, 2015, 2020 | 148,885 | parsed | [local_elections_kerala](https://github.com/in-rolls/local_elections_kerala) |
| Ladakh | - | - | - | not held | - |
| Lakshadweep | - | - | - | not held | - |
| Madhya Pradesh | - | - | - | raw, unparsed | [data/madhya_pradesh/](data/madhya_pradesh/) - 2 scan |
| Maharashtra | - | Mumbai 2007, 2012, 2017 (urban only) | - | prior work, other schema | [data/maharashtra/](data/maharashtra/) |
| Manipur | - | - | - | not held | - |
| Meghalaya | - | - | - | no PRI | Sixth Schedule - autonomous district councils, no PRI |
| Mizoram | - | - | - | no PRI | Sixth Schedule - village councils, no PRI |
| Nagaland | - | - | - | no PRI | Article 371A - village councils, no PRI |
| NCT of Delhi | - | 2007, 2012, 2017 (urban) | - | prior work, other schema | [data/delhi/](data/delhi/) |
| Odisha | - | - | - | raw, unparsed | [data/odisha/](data/odisha/) - 6 digital-text |
| Puducherry | - | - | - | raw, unparsed | [data/puducherry/](data/puducherry/) - 1 digital-text, 1 scan |
| Punjab | - | - | - | not held | - |
| Rajasthan | - | 2004-2019 urban, 2005-2021 panchayat | - | prior work, other schema | [data/rajasthan/](data/rajasthan/) |
| Sikkim | - | - | - | not held | - |
| Tamil Nadu | - | - | - | raw, unparsed | [data/tamil_nadu/](data/tamil_nadu/) - 11 digital-text, 1 scan |
| Telangana | - | 2018-2023 | - | prior work, other schema | [data/telangana/](data/telangana/) |
| Tripura | - | - | - | not held | - |
| Uttar Pradesh | pradhan | 2005, 2010, 2015, 2021 | 1,552,251 | parsed | [local_elections_up](https://github.com/in-rolls/local_elections_up) |
| Uttarakhand | panchayat | 2008, 2014, 2019 | 129,044 | parsed | [local_elections_uttarakhand](https://github.com/in-rolls/local_elections_uttarakhand) |
| West Bengal | - | 2013 panchayat, 2008-2018 municipal | - | prior work, other schema | [data/wb/](data/wb/) |

<!-- coverage:end -->


### Other Sources

* https://github.com/tcpd/Urban_Local_Body
