This document describes the process for importing _new_ customers into iShamba.

_Considerable care_ should be taken when following this process to ensure that the
quality of the data input into the system is consistently high.

## Batching

Due to the performance issues inherent to the framework upon which the iShamba `Customer`
importer is built, uploads should be batched into groups **no more than 10,000 customers**
prior to uploading.

## CSV Files

Note that `Customer` importing does ***NOT*** include `MarketSubscription`,
`TipSeriesSubscriptions` or premium `Subscription`. To create those, a separate
CSV import is necessary.

The `Customer` file (including the phone number(s), location, etc. of the customers)
**must be uploaded first**.

### `Customer` CSV file

This is the main and **first** file to be uploaded. It includes the majority of customer
properties such as phone number(s), name, location, etc.

#### CSV File Format

The table below shows the format of customer upload CSV files.

| name      | sex | phones                      | country | village  | ward | subcounty | county | agricultural_region | preferred_language | farm_size | notes               | is_registered | has_requested_stop | commodities | categories | location            |
| --------- | --- |-----------------------------|---------|----------| ---- | --------- | ------ |---------------------|--------------------|-----------|---------------------| ------------- | ------------------ | ----------- | ---------- | ------------------- |
| Joe Blogs | f   | +254700000000,+254700000001 | Kenya   |          |      |           |        | Rift Valley         | eng                | 1.00      | Joined via whatsapp | 1             | 0                  | 15,62       | 1,2        | 37.546696,-1.727074 |

**Key points**:
 - The ordering of columns may be changed, but special attention should be paid to the column names.
 - The `sex` field should be **`m`**, **`f`**, or blank.
 - Phone numbers (`phones`) should be formatted in [E164](https://en.wikipedia.org/wiki/E.164) format (see example below).
 - Numerical fields such as `region` contain the ID of the associated record (e.g. the Region with ID `1` is the [Central region](https://ishamba.mediae.org/admin/agri/region/1/)) or their corresponding name. These IDs are visible in the associated admin pages.
 - Comma-separated numeric fields such as `phones`, `categories` and `commodities` contain one or more related IDs (see above).
 - The `farm_size` field can take one of the following values (where `x` is farm size in acres)
   - **`0.00`**: `x < 0.25`
   - **`0.25`**: `0.25 <= x < 0.5`
   - **`0.50`**: `0.5 <= x < 0.75`
   - **`0.75`**: `0.75 <= x < 1`
   - **`1.00`**: `1 <= x < 1.5`
   - **`1.50`**: `1.5 <= x < 2`
   - **`2.00`**: `2 <= x < 3`
   - **`3.00`**: `3 <= x < 5`
   - **`5.00`**: `5 <= x < 10`
   - **`10.00`**: `x >= 10`

 - Boolean columns such as `is_registered` and `has_requested_stop` take the values **`0`** or `False` and **`1`** or `True`.
 - The `location` field takes values in the following format `longitude,latitude` (e.g. `37.546696,-1.727074`).

#### Skipped Customer Imports

After uploading the customer file, special attention should be paid to the skipped customers. They should be copied in a separate sheet so that they can be assigned the category intended separately.

### `MarketSubscription` CSV file

This file contains the markets and backup markets (if required) for the customers imported by uploading the `Customer`s CSV FILE. The format of this file is as follows:

#### Format

| phone           | market_id     | backup_market_id |
| --------------- | ------------- | ---------------- |
| +2547000000001  | 5             | 2                |
| +2547000000001  | 1             |                  |

**Key points**:
 - One `MarketSubscription` will be created per row in the file. That means generally **two rows per customer are required**. The above example would assign the `Customer` with phone number `+2547000000001` the following markets:
  - Embu (ID: 5) with main-market backup Nakuru (ID: 2)
  - Mombasa (ID: 1) with no backup as Mombasa is a main-market.
 - The `phone` values should match the `phone` column values in the `Customers` CSV file.
 - Both the `market_id` and `backup_market_id` fields reference `Market`s.
 - A `backup_market_id` should be assigned if the `market_id` references a non-main-market. Otherwise, it should be blank.
---
## Process

 1. Assemble the customer import file.
 2. Upload the customer file to staging ensuring there are no import errors and verifying that the customers have been created as expected.
 3. Before confirming import, record any skipped imports in a separate spreadsheet.
 4. Assemble the market subscription file based on the updated customers (ensuring all customer import errors corrections are reflected).
 5. Upload the market subscription file and make sure it is created as you expect (paying special attention to their assigned market subscriptions).
 6. Check for any errors arising from existing customers who already have market subscriptions. Copy these customers in a separate spreadsheet and remove them from the file you are going to upload.
 7. Verify that the customers have been created as you expect.
 8. If you find any problems with the data in production _immediately_ notify [Elizabeth](elizabeth@mediae.org) Lilian or Elias.
