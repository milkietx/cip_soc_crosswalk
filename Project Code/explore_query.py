## the aim of this code is to download all programs from THECB
##source location = https://www.txhigheredaccountability.org/AcctPublic/InteractiveReport/AddReport

import sys
sys.path.append(r'C:\Users\cmg0530\Projects\cip_soc_crosswalk\Project Code\codelib')
from helpers import *
import pandas as pd
import os

def main():
    #connect to database
    db_path = r'C:\\Users\\cmg0530\\Projects\\cip_soc_crosswalk\\Databases\\cipsoc.sqlite'
    con = create_conn(db_path)
    
    import geopandas as gpd
    x = r"C:\Users\cmg0530\Projects\cip_soc_crosswalk\Data Downloads\Spatial Data\NHGIS\Reprojected\US_cd116th_2020.shp"
    tf = gpd.read_file(x)
    crs = tf.geometry.crs.to_epsg()
    try:
        tf["geometry"] = [MultiPolygon([feature]) if isinstance(feature, Polygon) else feature for feature in tf["geometry"]]
    except:
        print("Not a polygon or multipolygon shape")
    tf['geom_wkt'] = tf.apply(lambda x: x['geometry'].wkt,axis=1)
    tf = tf.drop(columns=['geometry'])

    #table name
    title = x.split("\\")[-1][0:-4]

    #upload to sqlite 
    con = create_conn(db_path)
    upload_to_sqlite(con.cursor(),
                        con,
                        tf,
                        title,
                        schema,
                        drop=True,
                        chunk_print_size=5000)

    #make spatial in sqlite
    make_table_spatial(con.cursor(), 
                    con,
                    wkt_col='geom_wkt',
                    geometry_column='geometry',
                    srid=crs,
                    table_name=title, 
                    schema=schema)
    
    crsr = con.cursor()
    
    
    crsr.execute("""SELECT 
        blk.GISJOIN AS blk_join,
        cd.GISJOIN AS cd_join
    FROM 
        ref_TX_block_2020 AS blk
    JOIN
        (SELECT * from ref_US_cd116th_2020 where statefp = '48' and cd116fp = '22') AS cd
    WHERE 
        ST_Within(blk.geometry, cd.geometry) = 1""")
pd.read_sql(r"SELECT * from ref_US_cd116th_2020 where statefp = '48' and cd116fp = '22'",con=con)