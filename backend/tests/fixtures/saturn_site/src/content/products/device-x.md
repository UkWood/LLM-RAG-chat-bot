---
# keep this source comment
title: Device X
name: Full device X
group: controllers
systems:
  - heating-system
status: obsolete
notice: For qualified personnel
mass_kg: 1.25
temperature_c:
  min: -40
  max: 70
dimensions_mm: [120, 80, 40]
lifetime_years: 12
specs:
  - group: Interfaces
    name: RS-485
    value: "2"
    condition: isolated
features:
  - first
  - second
related: [device-y]
variant_of: device-y
software: [software-x]
articles: [article-x]
solutions: [solution-x]
new_filter_parameter:
  unit: kPa
  values: [1, 2, 3]
  qualifiers:
    condition: nominal
---
# Device X

Body text.
