import tempfile
from importlib.resources import files, as_file

from .mkinventorylabel import make_label


def generate_label(asset: int):
    file_path = files("uoft_snipeit").joinpath("AP-Template.odt")
    with (
        as_file(file_path) as file,
        tempfile.NamedTemporaryFile(suffix=".odt") as output_file,
    ):
        make_label("asset", asset, file, output_file)
