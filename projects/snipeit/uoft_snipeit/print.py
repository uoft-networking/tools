from uoft_core import shell


def system_print_label():
    print("Printing asset label")
    shell(
        rf"lp -d QL-800 -o landscape -o media=29x90mm -o scaling=100 -o MediaType=Labels\ *Tape -o AutoCut=False -o AutoEject=False -P 1 ~/Asset-Label.jpg"
    )
