The shapefiles in this directory come from the humdata project: https://data.humdata.org/dataset

The original WorldBorder shape data is from the GeoDjango Tutorial:
- https://docs.djangoproject.com/en/3.2/ref/contrib/gis/tutorial/

The Kenya data is from the American Red Cross. This data set was chosen because it is
up to date and has matching borders at the ward, subcounty and county levels.

The Uganda data is from the UN OCHA ROSEA. There were some issues with shapes that had
different borders but identical names and pcodes at adm level 3. This was corrected by
creating an ST_Union of the shapes for those areas and replacing the original records.

A name mapping table called BorderLevelName was also created which maps the
administrative level in each country with its corresponding local and english names.

All data is converted to SRID 4326 (geography / lat+long) format in the database.

--- Specific data set download locations ---

Kenya:
- Level 1 - County: https://data.humdata.org/dataset/47-counties-of-kenya
- Level 2 - Subcounty: https://data.humdata.org/dataset/kenya-sub-counties
- Level 3 - Ward: https://data.humdata.org/dataset/administrative-wards-in-kenya-1450

Uganda:
- https://data.humdata.org/dataset/uganda-administrative-boundaries-admin-1-admin-3

Zambia:
- https://data.humdata.org/dataset/cod-em-zmb

To prepare shape files for importing into postgresql database the following commands are useful:
- shp2pgsql -G -I ke_subcounty kenya_subcounties > kenya_subcounties.sql
- psql -d ishamba -f kenya_subcounties.sql

The file boundary_db_design.txt has some sql details on how the final table was
constructed from these sources.
