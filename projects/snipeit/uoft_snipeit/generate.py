from importlib.resources import files
from textwrap import wrap
from . import settings
from .mkinventorylabel import get_info_from_server
from typing import Literal
from PIL import Image, ImageDraw, ImageFont
from qrcode.main import QRCode
from qrcode.image.pil import PilImage
from os.path import expanduser


def generate_label(asset: int):
    s = settings()
    qrcode_url = f"{s.snipeit_hostname}/api/v1/asset/{asset}"
    fields = get_info_from_server(item_type="asset", item_id=asset)
    field = {key: fields[key] for key in {"name", "asset_tag", "serial", "model_number"}}
    im = make_label_from_fields(90, 29, 2, "mm", field, qrcode_url)
    im = im.transpose(Image.FLIP_TOP_BOTTOM)
    im.save(expanduser(f"~/Asset-Label.jpg"))


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
    img: Image.Image = qr.make_image(image_factory=PilImage)  # type: ignore
    img = img.resize((size, size))
    return img


def generate_label_image(fields: dict[str, str], width: int, max_height: int) -> Image.Image:
    font_size = 28  # how many pixels tall the font is
    field_spacing = 10  # how many pixels between each field

    # this is the thing we're going to fill with text and return from this function
    image = Image.new("L", (width, max_height), color=255)
    draw = ImageDraw.Draw(image)

    regular = ImageFont.truetype(files("uoft_snipeit").joinpath("DejavuSans-mono-regular.ttf").open("rb"), font_size)
    bold = ImageFont.truetype(files("uoft_snipeit").joinpath("DejavuSans-mono-bold.ttf").open("rb"), font_size)

    # In order to calculate how many characters we can fit on a line, we need to know how wide the font is.
    # We can leverage the fact that the font is monospaced, and that the bold and regular variants are the same width
    character_width = regular.getlength("a")

    vertical_offset = 0
    longest_key = max(fields.keys(), key=len)

    for key, value in fields.items():
        # draw the key
        draw.text((0, vertical_offset), key + ": ", font=bold, fill=0)

        # wrap the value text to fit the width, if needed
        key_width = len(longest_key + ": ") * character_width
        max_value_width = width - key_width
        max_value_chars_per_line = int(max_value_width // character_width)
        value = "\n".join(wrap(value, max_value_chars_per_line, break_long_words=True))

        draw.text((key_width, vertical_offset), value, font=regular, fill=0)
        number_of_lines = value.count("\n") + 1
        vertical_offset += number_of_lines * font_size + field_spacing
    return image


def make_label_from_fields(
    width: float,
    height: float,
    margin: float,
    unit: Literal["in", "mm", "cm", "px"],
    fields: dict[str, str],
    qrcode_url: str | None = None,
    qrcode_size: float | None = None,
) -> Image.Image:
    if qrcode_size is None:
        qrcode_size = height - (margin * 2)
    width, height, margin, qrcode_size = to_pixels(width, height, margin, qrcode_size, unit)
    image = Image.new("L", (width, height), color=255)
    text_offset = margin
    if qrcode_url:
        qr = generate_qr_image(qrcode_url, qrcode_size)
        image.paste(qr, (margin, margin))
        text_offset += qrcode_size + margin
    text_width = width - margin - text_offset
    text_data = generate_label_image(fields, text_width, max_height=height - (margin * 2))
    image.paste(text_data, (text_offset, margin))
    return image


def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    pass
