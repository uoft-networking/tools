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

from typing import Literal
from PIL import Image, ImageDraw, ImageFont
from qrcode import QRCode
from qrcode.image.pil import PilImage


def to_pixels(
    width: float,
    height: float,
    margin: float,
    qrcode_size: float,
    unit: Literal["in", "mm", "cm", "px"],
    dpi: int = 300,
):
    if unit == "in":
        width *= dpi
        height *= dpi
        margin *= dpi
        qrcode_size *= dpi
    elif unit == "mm":
        width *= dpi / 25.4
        height *= dpi / 25.4
        margin *= dpi / 25.4
        qrcode_size *= dpi / 25.4
    elif unit == "cm":
        width *= dpi / 2.54
        height *= dpi / 2.54
        margin *= dpi / 2.54
        qrcode_size *= dpi / 2.54
    elif unit == "px":
        pass
    else:
        raise ValueError(f"Unknown unit {unit}")
    return int(width), int(height), int(margin), int(qrcode_size)

def generate_qr_image(data: str, size: int) -> Image.Image:
    qr = QRCode(
        version=1,
        box_size=1,
        border=0,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img: Image.Image = qr.make_image(image_factory=PilImage) # type: ignore
    img = img.resize((size, size))
    return img


def generate_label_image(fields: dict[str, str], width: int, max_height: int) -> Image.Image:
    font_size = 28
    paragraph_spacing = 10
    image = Image.new("L", (width, max_height), color=255)
    draw = ImageDraw.Draw(image)
    regular = ImageFont.truetype(files("uoft_snipeit").joinpath("DejavuSans-mono-regular.ttf").open("rb"), font_size)
    bold = ImageFont.truetype(files("uoft_snipeit").joinpath("DejavuSans-mono-bold.ttf").open("rb"), font_size)
    vertical_offset = 0
    longest_key = max(fields.keys(), key=len)
    for name, value in fields.items():
        key_width = bold.getlength(longest_key+": ")
        draw.text((0, vertical_offset), name+": ", font=bold, fill=0)
        draw.text((key_width, vertical_offset), value, font=regular, fill=0)
        number_of_lines = value.count("\n") + 1
        vertical_offset += number_of_lines * font_size + paragraph_spacing
    return image


def make_label(
    width: float,
    height: float,
    margin: float,
    unit: Literal["in", "mm", "cm", "px"],
    fields: dict[str, str],
    qrcode: str | None = None,
    qrcode_size: float|None = None,
) -> Image.Image:
    if qrcode_size is None:
        qrcode_size = height - (margin * 2)
    width, height, margin, qrcode_size = to_pixels(width, height, margin, qrcode_size, unit)
    image = Image.new("L", (width, height), color=255)
    text_offset = margin
    if qrcode:
        qr = generate_qr_image(qrcode, qrcode_size)
        image.paste(qr, (margin, margin))
        text_offset += qrcode_size + margin
    text_width = width - margin - text_offset
    text_data = generate_label_image(fields, text_width, max_height=height - (margin * 2))
    image.paste(text_data, (text_offset, margin))
    return image


def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    data = {
        "model number": "1234567890",
        "serial number": "123456789",
        "asset": "123456789",
        "name": "hello world",
        "description": "hello world\nand again and again",
    }
    im = make_label(90, 29, 2, "mm", data, qrcode="https://www.google.com")
    im.save('test.jpg')
