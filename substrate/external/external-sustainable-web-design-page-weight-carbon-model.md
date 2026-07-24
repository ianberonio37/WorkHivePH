---
name: external-sustainable-web-design-page-weight-carbon-model
type: reference
source: https://sustainablewebdesign.org/estimating-digital-emissions/
source_sha: 3787973703c08eb0
fetched_at: 2026-07-24T04:29:51Z
last_verified: 2026-07-24
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: sustainable-web-design-page-weight-carbon-model
---

## reference · sustainable-web-design-page-weight-carbon-model
* The Sustainable Web Design Model (SWDM) estimates digital emissions using data transfer and carbon intensity as key inputs.
* The model breaks down into three system segments: data centers (22% of total energy), networks (24%), and user devices (54%).
* Each segment is further divided into operational and embodied emissions.
* Operational emissions for each segment are calculated using energy intensity values:
  + Data centers: 0.055 kWh/GB
  + Networks: 0.059 kWh/GB
  + User devices: 0.080 kWh/GB
* Embodied emissions for each segment are calculated using energy intensity values:
  + Data centers: 0.012 kWh/GB
  + Networks: 0.013 kWh/GB
  + User devices: 0.081 kWh/GB
* The global average carbon intensity of electricity is 494 gCO2e/kWh.
* The model uses the following formula to estimate average emissions per page view: 
  `Average Emissions per Page View (gCO2e) = ([(OPDC × (1 - Green Hosting Factor) + EMDC) + (OPN + EMN) + (OPUD + EMUD)] × New Visitor Ratio) + ([(OPDC × (1 - Green Hosting Factor) + EMDC) + (OPN + EMN) + (OPUD + EMUD)] × Return Visitor Ratio × (1 - Data Cache Ratio))`
* Total energy consumption values used in the model:
  + Data centers: 290 TWh
  + Networks: 310 TWh
  + User devices: 421 TWh
* Total data transfer across the internet: 5.29 ZB
* The model assumes that the values provided by Malmodin are equivalent to electricity consumption with a global electricity emissions factor.
* The percentage of total embodied energy for each segment:
  + Data centers: 11%
  + Networks: 12%
  + User devices: 77%
Sources: https://sustainablewebdesign.org/estimating-digital-emissions/
