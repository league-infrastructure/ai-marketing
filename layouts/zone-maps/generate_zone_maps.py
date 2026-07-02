#!/usr/bin/env python3
"""
Generate square SVG zone-map references for League Peachjar-flyer and Facebook templates.

Each map is a 1024x1024 square (the generation master's aspect). Content areas are drawn as
flat #00FF00 (green-screen green) rectangles -- the exact chroma key the real template art
uses -- so a map can be handed to an image generator as a layout reference. A dashed grey
box marks the safe region (the crop that must be preserved); dashed blue boxes mark the
intended output crops. Labels are annotations for humans/models and are NOT meant to appear
in generated art.

Coordinates are normalized [0,1] on the square and are the source of truth; the sidecar
JSON examples in the layout .md files mirror these numbers. Every zone must fit inside every
listed crop -- asserted at generation time.
"""
import os, sys

CANVAS=1024
CHROMA="#00FF00"; CHROMA_STROKE="#0aa60a"
SAFE_STROKE="#8a8a8a"; CROP_STROKE="#1e6fff"; LABEL="#0a2a0a"

def R(x,y,w,h): return dict(x=x,y=y,w=w,h=h)      # keep normalized floats
def px(z): return {k:round(v*CANVAS) for k,v in z.items()}

# NOTE: content areas are deliberately SMALL. The artwork is the hero; these flyers exist
# to drive people to the QR/URL, so copy is only a title + short teaser. The empty (non-green)
# space inside each crop is reserved for art. Target: art >= ~55% of the crop area.

MAPS={
"peachjar-multi-event-A":{
  "title":"Peachjar multi-event - A (art hero top, compact event list below)",
  "crops":[("peachjar 8.5:11", R(0.121,0.01,0.757,0.98))],
  "zones":[
    # top ~0.01-0.34 of the crop is left blank for the hero art
    ("masthead / title","small strip", R(0.17,0.35,0.66,0.06)),
    ("EVENT LIST (title+teaser rows)","compact", R(0.17,0.43,0.66,0.27)),
    ("org + location","small", R(0.17,0.74,0.45,0.075)),
    ("QR","small square", R(0.68,0.735,0.15,0.15)),
    ("nonprofit line","thin strip", R(0.17,0.845,0.45,0.035)),
  ]},
"peachjar-multi-event-B":{
  "title":"Peachjar multi-event - B (big art band, content in lower third)",
  "crops":[("peachjar 8.5:11", R(0.121,0.01,0.757,0.98))],
  "zones":[
    ("logo","tiny", R(0.15,0.05,0.12,0.045)),
    ("title","small strip", R(0.31,0.05,0.38,0.07)),
    ("QR","small square", R(0.72,0.05,0.13,0.13)),
    # 0.13-0.55 left blank = large full-width art band
    ("EVENT LIST (title+teaser rows)","compact", R(0.15,0.55,0.70,0.24)),
    ("org + location","small", R(0.15,0.82,0.70,0.06)),
    ("nonprofit line","thin strip", R(0.15,0.90,0.70,0.035)),
  ]},
"single-event-facebook":{
  "title":"Single event - Facebook (art hero; compact title+date+teaser, no QR - clicks through)",
  "crops":[("feed 1:1", R(0.0,0.0,1.0,1.0)), ("link 1.91:1", R(0.0,0.238,1.0,0.524))],
  "zones":[
    # No QR/link: the Facebook image itself is the click target. Keep art up top, copy low.
    ("TITLE","medium", R(0.08,0.49,0.58,0.10)),
    ("date + time","small", R(0.08,0.61,0.40,0.06)),
    ("teaser","small", R(0.08,0.68,0.62,0.07)),
  ]},
}

def contains(c,z,eps=1e-9):
    return (z['x']>=c['x']-eps and z['y']>=c['y']-eps and
            z['x']+z['w']<=c['x']+c['w']+eps and z['y']+z['h']<=c['y']+c['h']+eps)
def overlap(a,b):
    return not (a['x']+a['w']<=b['x'] or b['x']+b['w']<=a['x'] or a['y']+a['h']<=b['y'] or b['y']+b['h']<=a['y'])

# ---- validate before drawing ----
errs=[]
for name,spec in MAPS.items():
    zs=[z for _,_,z in spec["zones"]]
    for role,size,z in spec["zones"]:
        for cname,c in spec["crops"]:
            if not contains(c,z): errs.append(f"{name}: '{role}' outside crop '{cname}'")
        if size in ("square","small square") and abs(z['w']-z['h'])>1e-9:
            errs.append(f"{name}: '{role}' not square {z['w']}x{z['h']}")
    for i in range(len(zs)):
        for j in range(i+1,len(zs)):
            if overlap(zs[i],zs[j]): errs.append(f"{name}: zone overlap {i},{j}")
if errs:
    print("VALIDATION FAILED:"); [print(" -",e) for e in errs]; sys.exit(1)

# ---- art-coverage report: content should be a minority of the primary crop ----
for name,spec in MAPS.items():
    c=spec["crops"][0][1]; carea=c['w']*c['h']
    zarea=sum(z['w']*z['h'] for _,_,z in spec["zones"])
    frac=zarea/carea
    flag="" if frac<=0.45 else "  <-- content too large"
    print(f"  {name}: content {frac*100:4.1f}% of crop, art ~{(1-frac)*100:4.1f}%{flag}")
print("validation OK: all zones inside all crops, squares square, no overlaps")

def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def intersect_crops(crops):
    x0=max(c['x'] for _,c in crops); y0=max(c['y'] for _,c in crops)
    x1=min(c['x']+c['w'] for _,c in crops); y1=min(c['y']+c['h'] for _,c in crops)
    return R(x0,y0,x1-x0,y1-y0)

def svg(spec):
    p=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS}" height="{CANVAS}" viewBox="0 0 {CANVAS} {CANVAS}">']
    p.append(f'<rect x="0" y="0" width="{CANVAS}" height="{CANVAS}" fill="#ffffff"/>')
    p.append(f'<text x="{CANVAS//2}" y="26" text-anchor="middle" font-family="sans-serif" font-size="18" fill="#333">{esc(spec["title"])}</text>')
    s=px(intersect_crops(spec["crops"]))
    p.append(f'<rect x="{s["x"]}" y="{s["y"]}" width="{s["w"]}" height="{s["h"]}" fill="none" stroke="{SAFE_STROKE}" stroke-width="2" stroke-dasharray="10 8"/>')
    p.append(f'<text x="{s["x"]+6}" y="{max(s["y"]-6,40)}" font-family="sans-serif" font-size="13" fill="{SAFE_STROKE}">safe region (kept by every crop)</text>')
    for cname,c in spec["crops"]:
        cc=px(c)
        p.append(f'<rect x="{cc["x"]}" y="{cc["y"]}" width="{cc["w"]}" height="{cc["h"]}" fill="none" stroke="{CROP_STROKE}" stroke-width="2" stroke-dasharray="4 6"/>')
        p.append(f'<text x="{cc["x"]+cc["w"]-6}" y="{cc["y"]+18}" text-anchor="end" font-family="sans-serif" font-size="13" fill="{CROP_STROKE}">crop: {esc(cname)}</text>')
    for role,size,z in spec["zones"]:
        zz=px(z)
        p.append(f'<rect x="{zz["x"]}" y="{zz["y"]}" width="{zz["w"]}" height="{zz["h"]}" fill="{CHROMA}" stroke="{CHROMA_STROKE}" stroke-width="2"/>')
        cx=zz["x"]+zz["w"]//2; cy=zz["y"]+zz["h"]//2
        p.append(f'<text x="{cx}" y="{cy-4}" text-anchor="middle" font-family="sans-serif" font-size="17" font-weight="bold" fill="{LABEL}">{esc(role)}</text>')
        p.append(f'<text x="{cx}" y="{cy+16}" text-anchor="middle" font-family="sans-serif" font-size="12" fill="{LABEL}">[{esc(size)}]</text>')
    p.append('</svg>')
    return "\n".join(p)

here=os.path.dirname(os.path.abspath(__file__))
for name,spec in MAPS.items():
    open(os.path.join(here,name+".svg"),"w").write(svg(spec))
    print("wrote",name+".svg")
