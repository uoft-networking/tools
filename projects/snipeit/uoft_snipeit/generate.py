import os
from importlib.resources import files, as_file


def mklabel_generate_label(asset: int):
    file_path = files("uoft_snipeit").joinpath("AP-Template.odt")
    with as_file(file_path) as file:
        os.system(f"mklabel -t assets -n {asset}, -i {file}")
