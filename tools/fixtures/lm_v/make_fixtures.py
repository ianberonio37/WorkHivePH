"""make_fixtures.py - the three small images the LM-V walk hands to a page's photo inputs (tools/lm_walk_v_block.js).

The walk never calls a vision model: every vision function is answered by a stub whose payload matches what these
images show, so a receipt that says "the photo became an entry" is about a photo a person could plausibly take.

  nameplate.png      an equipment nameplate (logbook "Scan nameplate" -> equipment-label-ocr)
  defect_belt.png    a glazed, cracked V-belt on its pulleys (logbook "Photo defect capture" -> visual-defect-capture)
  resume_page_1.png  the first page of a printed resume (resume "Take photos" -> resume-extract)

  python tools/fixtures/lm_v/make_fixtures.py      -> rewrites the three PNGs next to this file (each < 25 KB)
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONTS = Path("C:/Windows/Fonts")


def font(name: str, size: int):
    try:
        return ImageFont.truetype(str(FONTS / name), size)
    except Exception:
        try:
            return ImageFont.load_default(size=size)
        except Exception:
            return ImageFont.load_default()


def nameplate() -> None:
    im = Image.new("L", (640, 380), 168)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((14, 14, 626, 366), radius=18, outline=60, width=6, fill=196)
    for x, y in ((34, 34), (594, 34), (34, 334), (594, 334)):
        d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=110, outline=60)
    b, r, m = font("arialbd.ttf", 34), font("arial.ttf", 24), font("consolab.ttf", 24)
    d.text((60, 44), "WEG", font=b, fill=20)
    d.text((170, 52), "THREE-PHASE INDUCTION MOTOR", font=r, fill=30)
    d.line((50, 98, 590, 98), fill=70, width=3)
    rows = [("MODEL", "W22 IE3 132M-4"), ("S/N", "1028475531"), ("kW", "7.5      V 400 D   50 Hz"),
            ("RPM", "1460     A 14.2   cos 0.84"), ("IP", "55   INS.CL F   AMB 40 C")]
    y = 112
    for k, v in rows:
        d.text((60, y), k, font=r, fill=40)
        d.text((190, y), v, font=m, fill=15)
        y += 44
    im.save(HERE / "nameplate.png", optimize=True)


def defect_belt() -> None:
    im = Image.new("L", (640, 400), 70)
    d = ImageDraw.Draw(im)
    # two pulleys and the belt between them, its top run glazed (bright) and cracked
    d.ellipse((60, 110, 240, 290), fill=120, outline=30, width=6)
    d.ellipse((420, 140, 560, 280), fill=120, outline=30, width=6)
    d.ellipse((130, 180, 170, 220), fill=40)
    d.ellipse((470, 190, 510, 230), fill=40)
    d.polygon([(150, 110), (490, 140), (490, 154), (150, 126)], fill=235)
    d.polygon([(150, 274), (490, 266), (490, 280), (150, 290)], fill=25)
    for x in range(200, 460, 38):
        d.line((x, 116 + (x - 150) * 30 // 340, x + 8, 128 + (x - 150) * 30 // 340), fill=10, width=3)
    d.rectangle((250, 330, 390, 372), fill=210, outline=20, width=2)
    d.text((262, 336), "DRIVE 3", font=font("arialbd.ttf", 26), fill=10)
    im.save(HERE / "defect_belt.png", optimize=True)


def resume_page() -> None:
    im = Image.new("L", (600, 780), 250)
    d = ImageDraw.Draw(im)
    h, s, r = font("arialbd.ttf", 30), font("arialbd.ttf", 20), font("arial.ttf", 18)
    d.text((40, 40), "RESUME", font=h, fill=10)
    d.text((40, 84), "Maintenance Technician  -  Valenzuela, Metro Manila", font=r, fill=30)
    d.line((40, 120, 560, 120), fill=120, width=2)
    lines = [("EXPERIENCE", s), ("Maintenance Technician, Northline Packaging Corp.", r), ("Jun 2019 - Aug 2024", r),
             ("- Cut conveyor downtime 30% with a weekly belt-tension round", r), ("", r),
             ("EDUCATION", s), ("BS Mechanical Engineering", r), ("Technological University of the Philippines", r), ("", r),
             ("SKILLS", s), ("Vibration analysis  -  LOTO  -  PM planning", r), ("", r),
             ("CERTIFICATES", s), ("TESDA NC II Electrical Installation and Maintenance (2018)", r), ("", r),
             ("SUMMARY", s), ("Five years on conveyors, pumps and fleet vehicles.", r)]
    y = 140
    for t, f in lines:
        d.text((40, y), t, font=f, fill=15)
        y += 34
    im.save(HERE / "resume_page_1.png", optimize=True)


if __name__ == "__main__":
    nameplate()
    defect_belt()
    resume_page()
    for p in sorted(HERE.glob("*.png")):
        print(f"{p.name}: {p.stat().st_size} bytes")
