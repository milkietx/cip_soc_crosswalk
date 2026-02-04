## the aim of this code is to download all programs from THECB
##source location = https://www.txhigheredaccountability.org/AcctPublic/InteractiveReport/AddReport

import sys
sys.path.append(r'C:\Users\cmg0530\Projects\cip_soc_crosswalk\Project Code\codelib')
from helpers import *
import pandas as pd
import os

def main():
    #files downloaded into folder from nhgis
    folder = r"C:\Users\cmg0530\Projects\cip_soc_crosswalk\Data Downloads\Spatial Data\NHGIS\nhgis0136_shape"
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
    db_path1 = r'C:\\Users\\cmg0530\\Projects\\cip_soc_crosswalk\\Databases\\geometry_reference.sqlite'
    db_path2 = r'C:\\Users\\cmg0530\\Projects\\cip_soc_crosswalk\\Databases\\cipsoc.sqlite'

    bulk_upload_to_sqlite(bulk_upload_file_list=files_to_upload, db_path=db_path1,schema='ref')
    bulk_upload_to_sqlite(bulk_upload_file_list=files_to_upload, db_path=db_path2,schema='ref')

if __name__ == "__main__":
    main()
