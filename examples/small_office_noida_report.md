# ECSBC 2024 envelope check

- Model: small_office_noida.idf
- Climate zone: Composite · Level: ECSBC · Building type: default · Latitude: 28.57°N
- **Overall: FAIL** (6 pass, 2 fail, 0 not evaluated)

| Check | Item | Value | Limit | Status | Reference | Note |
|---|---|---|---|---|---|---|
| Wall U-factor | Ext wall - brick + 75mm XPS | 0.371 | 0.400 | **PASS** | ECSBC 2024 Table 5.6 | 210.0 m2 |
| Roof U-factor | Flat roof - RCC + 50mm PUF | 0.401 | 0.260 | **FAIL** | ECSBC 2024 Table 5.3 | 200.0 m2; add R ≥ 1.35 m2K/W of insulation to comply |
| Window-to-wall ratio | whole building | 18.9% | 40.0% | **PASS** | ECSBC 2024 §5.3.3 | 39.6 of 210.0 m2 |
| Skylight-to-roof ratio | whole building | 0.0% | 5.0% | **PASS** | ECSBC 2024 §5.3.4 | 0.0 of 200.0 m2 |
| Window U-factor | DGU low-e window | 2.000 | 2.200 | **PASS** | ECSBC 2024 Table 5.9 | 39.6 m2; values from SimpleGlazingSystem in IDF |
| Window SHGC | DGU low-e window (non-north: East, South, West) | 0.280 | 0.250 | **FAIL** | ECSBC 2024 Table 5.9 | 25.2 m2 |
| Window SHGC | DGU low-e window (north: North) | 0.280 | 0.500 | **PASS** | ECSBC 2024 Table 5.9 | 14.4 m2 |
| Window VLT (minimum) | DGU low-e window | 0.450 | 0.270 | **PASS** | ECSBC 2024 §5.3.3 |  |

## Window-to-wall ratio by facade

| Facade | Window m2 | Gross wall m2 | WWR |
|---|---|---|---|
| East | 5.4 | 35.0 | 15.4% |
| North | 14.4 | 70.0 | 20.6% |
| South | 14.4 | 70.0 | 20.6% |
| West | 5.4 | 35.0 | 15.4% |

_Prescriptive pre-check only. U-factors use ISO 6946 air films (Rsi 0.13 walls, 0.10 roofs; Rse 0.04) and ignore thermal bridging. Confirm against the notified ECSBC and any state amendment._
