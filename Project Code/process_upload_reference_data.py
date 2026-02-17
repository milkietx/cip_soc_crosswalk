## the aim of this code is to download all programs from THECB
##source location = https://www.txhigheredaccountability.org/AcctPublic/InteractiveReport/AddReport

import sys
sys.path.append(r'C:\Users\cmg0530\Projects\cip_soc_crosswalk\Project Code\codelib')
from helpers import *
import pandas as pd
import os

def main():
    #files downloaded into folder from nhgis
    folder = r"C:\Users\cmg0530\Projects\cip_soc_crosswalk\Data Downloads\Spatial Data\NHGIS"
    outfolder = r"C:\Users\cmg0530\Projects\cip_soc_crosswalk\Data Downloads\Spatial Data\NHGIS\Unzipped Folders"
    reprojectfolder = r"C:\Users\cmg0530\Projects\cip_soc_crosswalk\Data Downloads\Spatial Data\NHGIS\Reprojected"
    #unzip files
    unzip_gis_files(folder,outfolder)

    #reproject files
    rpfold = bulk_reproject_gis_files(outfolder,reprojectfolder,new_crs=4326)

    #upload into sqlite
    files_to_upload = generate_bulk_upload_list_from_folder(rpfold)
    
    #save one copy in the geometry_reference database
    #save another copy in the sqlite database
    db_path = r'C:\Users\cmg0530\Projects\cip_soc_crosswalk\Databases\cip_soc_duck.db'
    
    ###tis is where you nede to pick it back up
    for x in files_to_upload:
        title = x.split("\\")[-1][0:-4]
        gdf = gpd.read_file(x)
        load_from_gdf(conn=con,
                  gdf=gdf,
                  table_name=f'geom_{title}',
                  geom_col_name='geom')
        
if __name__ == "__main__":
    main()
