from enum import Enum

class Role(str, Enum):
    voip = "voip"
    desktop = "desktop"
    printer = "printer"
