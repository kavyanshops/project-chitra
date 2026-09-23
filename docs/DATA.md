# CHITRA — Data Guide

Raw data lives in `data/` and is git-ignored. **Primary test site: Apollo 11**, an equatorial mare site covered by OHRC, TMC-2, IIRS, LRO NAC, Kaguya TC and a NAC DTM. The NAC DTM covers **0.31–1.24° N, 23.37–23.51° E**.

## 1. Reference data (public, fetched by `scripts/fetch_reference.sh`)

| Product | GSD | Source |
|---|---|---|
| NAC_DTM_APOLLO11 (GeoTIFF DTM) | 2 m | [LROC RDR](https://data.lroc.im-ldi.com/lroc/view_rdr/NAC_DTM_APOLLO11) |
| Orthophoto M150361817 | 0.5 m / 2 m | same page |
| Orthophoto M150368601 | 0.5 m / 2 m | same page |
| LRO WAC global mosaic (crop) | ~100 m | [LROC downloads](https://lroc.im-ldi.com/images/downloads) |
| SELENE/Kaguya TC ortho (crop) | ~10 m | [JAXA DARTS](https://darts.isas.jaxa.jp/planet/pdap/selene/) |
| SLDEM2015 / LOLA (regional) | ~59 m / 118 m | [PDS Geosciences LOLA](https://pds-geosciences.wustl.edu/missions/lro/lola.htm) |

## 2. Chandrayaan-2 data (PRADAN login required — download manually)

1. Log in at <https://pradan.issdc.gov.in> and open **Chandrayaan-2 Map Browse** (<https://chmapbrowse.issdc.gov.in>).
2. Search by location **lat 0.3–1.3° N, lon 23.3–23.6° E**.
3. Download one of each (calibrated products, `.img` + `.xml` label):
   - **TMC-2** — nadir-view (`n`) calibrated strip (`ch2_tmc_ncn_…`)
   - **OHRC** — calibrated (`ch2_ohr_ncp_…`)
   - **IIRS** (optional) — calibrated radiance cube (`ch2_iir_nci_…`)
4. Place them in `data/raw/ch2/`.

The PDS4 XML labels carry the solar azimuth/elevation and the image geometry that CHITRA reads.

## 3. Sensor reference card

| Sensor | GSD | Swath | Bands | Notes |
|---|---|---|---|---|
| OHRC | 0.25 m (100 km alt.) | 3 km | pan (visible) | off-nadir tilt capability |
| TMC-2 | 5 m | 20 km | pan 0.5–0.8 µm | fore / nadir / aft stereo triplet |
| IIRS | ~80 m | 20 km | ~256, 0.8–5 µm | hyperspectral cube, thermal tail beyond ~3 µm |
| LRO NAC | 0.5 m | 5 km | pan | reference |
| Kaguya TC | ~10 m | 35 km | pan | reference |
| LRO WAC | ~100 m (mosaic) | global | 7 | reference |

## 4. Licensing
LROC, PDS and JAXA products are public-domain or open-access. ISSDC data is used under ISRO's data-use policy; cite ISSDC/ISRO in any public result.
