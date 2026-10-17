from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

SIZE = 96
PADDING = 8


class Command(BaseCommand):
    help = (
        "Turn a logo into a push badge: a 96x96 white symbol on a transparent background, "
        "which is what Android shows in the status bar."
    )

    def add_arguments(self, parser):
        parser.add_argument("source", help="Your logo (PNG with transparency works best).")
        parser.add_argument("--output", help="Where to write the badge (default: <source>-badge-96.png).")
        parser.add_argument(
            "--threshold",
            type=int,
            default=40,
            help="For logos without transparency: how different from the background a pixel must be "
            "to count as part of the symbol (0-255, default 40).",
        )

    def handle(self, *args, source, output=None, threshold=40, **options):
        try:
            from PIL import Image, ImageChops
        except ImportError:
            raise CommandError("This command needs Pillow: pip install 'kvn-notify[icons]'") from None

        src = Path(source)
        if not src.exists():
            raise CommandError(f"{src} does not exist.")
        out = Path(output) if output else src.with_name(f"{src.stem}-badge-96.png")

        with Image.open(src) as opened:
            img = opened.convert("RGBA")

        alpha = img.getchannel("A")
        if alpha.getextrema()[0] >= 250:
            # No transparency: treat the colour in the corners as the background.
            rgb = img.convert("RGB")
            corner = rgb.getpixel((0, 0))
            background = Image.new("RGB", rgb.size, corner)
            diff = ImageChops.difference(rgb, background).convert("L")
            # Anything clearly below the threshold is background (including soft glows and
            # gradients); a short ramp just under it keeps the symbol's edges smooth.
            floor = threshold // 2
            alpha = diff.point(
                lambda v: 255 if v >= threshold else 0 if v <= floor else (v - floor) * 255 // (threshold - floor)
            )
            self.stdout.write("No transparency found; separated the symbol from the background colour.")

        bbox = alpha.point(lambda a: 255 if a >= 32 else 0).getbbox()
        if not bbox:
            raise CommandError("Could not find a symbol in the image.")
        alpha = alpha.crop(bbox)

        inner = SIZE - 2 * PADDING
        scale = min(inner / alpha.width, inner / alpha.height)
        new_size = (max(1, round(alpha.width * scale)), max(1, round(alpha.height * scale)))
        alpha = alpha.resize(new_size, Image.LANCZOS)

        badge = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
        white = Image.new("RGBA", new_size, (255, 255, 255, 255))
        white.putalpha(alpha)
        badge.paste(white, ((SIZE - new_size[0]) // 2, (SIZE - new_size[1]) // 2), white)
        badge.save(out, "PNG")

        self.stdout.write(self.style.SUCCESS(f"Wrote {out}"))
        self.stdout.write("Put it in your static files and set KVN_NOTIFY['BADGE'] to its static path.")
