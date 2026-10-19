# Academic Figure Skill Asset Confirmation (verified against assets/figures/)
# (a) COPY-FIRST: accepted R34 native SVG and its standalone assets, unchanged.
# (b) aggregate membership flow -> SankeyDiagram parameter inherit (Arial,
#     light links and proportional widths). The asset's simulated per-identity
#     trajectories are incompatible with this observed aggregate source table.
# (c) capacity schematic -> other/ has no production schematic; native SVG.
# (d) sharp-bound means -> no exact-bound asset; native scaled axis, NOT a CI.
# All panels remain native SVG; Inkscape exports the vector PDF and PNG preview.
# Academic Figure Skill Typography Baseline — COPY VERBATIM, place at TOP of script
import matplotlib as mpl
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans"],
    "font.size": 8,
    "axes.titlesize": 8,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 8,
    "figure.titlesize": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.6,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "legend.frameon": False,
})
# Academic Figure Skill Nature/Cell/Science Color Palette -- COPY VERBATIM
CATEGORICAL = ["#2166AC", "#B2182B", "#1B7837", "#F1A340", "#762A83", "#666666"]
CATEGORICAL_EXTENDED = [
    "#2166AC", "#B2182B", "#1B7837", "#F1A340", "#762A83", "#666666",
    "#4393C3", "#D6604D", "#5AAE61", "#B35806", "#9970AB", "#999999",
]
DIVERGING   = ["#2166AC", "#F7F7F7", "#B2182B"]
SEQUENTIAL  = ["#F7FBFF", "#6BAED6", "#08306B"]
ACCENT_RED  = "#B2182B"
GREY        = "#999999"
BLACK       = "#222222"
# Academic Figure Skill Export Baseline — COPY VERBATIM
mpl.rcParams.update({
    "pdf.fonttype": 42,         # TrueType font embedding
    "svg.fonttype": "none",     # editable text in SVG
    "savefig.bbox": "tight",    # trim whitespace
    "savefig.dpi": 300,
})

def save_cns_figure(fig, filename):
    """Standard Academic Figure Skill export: vector PDF + 300dpi PNG preview."""
    fig.savefig(f"{filename}.pdf", bbox_inches="tight", dpi=300)
    fig.savefig(f"{filename}.png", bbox_inches="tight", dpi=300)

from pathlib import Path
from copy import deepcopy
from lxml import etree as E
import argparse, csv, subprocess, hashlib, json, math, os, shutil

P = 72 / 25.4
NS = 'http://www.w3.org/2000/svg'
INK='#20262C'; BLUE='#355C7D'; TEAL='#007F75'; GOLD='#9B6E22'
PURPLE='#80658A'; GRAY='#616B73'; EDGE='#D7DDE1'; PALE='#F3F5F6'
HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]/'outputs/TRACE_DT_BIOLOGY_DIRECT_FIG1_VECTOR_R34_2026-10-10'
p=argparse.ArgumentParser()
p.add_argument('--data',type=Path,default=HERE/'source_data')
p.add_argument('--panel-a',type=Path,default=HERE/'accepted_R34_panel_a' if (HERE/'accepted_R34_panel_a').exists() else BASE/'figures')
p.add_argument('--output',type=Path,default=HERE/'rendered_figures')
p.add_argument('--inkscape',default='C:/Program Files/Inkscape/bin/inkscape.com')
args=p.parse_args(); OUT=args.output; OUT.mkdir(parents=True,exist_ok=True)
def load_row(name):
    with (args.data/name).open(encoding='utf-8',newline='') as f:
        rows=list(csv.DictReader(f,delimiter='\t'))
    assert len(rows)==1,(name,len(rows))
    return rows[0]

brow=load_row('Figure_1_A_deterministic_global_mean_matched_example.tsv')
drow=load_row('Figure_1_C_global_tie_bounds.tsv')
B=50; shared=int(brow['intersection_deterministic']); replaced=B-shared
assert brow['context_name']=='colorectal adenocarcinoma'
assert (brow['operator_code_a'],brow['operator_code_b'])==('00100','01001')
assert (shared,replaced)==(28,22) and float(brow['substitution_deterministic'])==replaced/B
assert all(float(brow[k])==shared for k in ['intersection_minimum','intersection_maximum','intersection_expected_uniform_tie'])
values=[float(drow[k]) for k in ['mean_lower_bound_global_F','deterministic_global_F','mean_upper_bound_global_F']]
pair_n=int(drow['within_context_pairs'])
assert pair_n==11408 and 0<=values[0]<=values[1]<=values[2]<=1

labels=[]; connectors=[]; counter=0
def el(parent,tag,**attrs):
    return E.SubElement(parent,'{'+NS+'}'+tag,{k.replace('_','-'):str(v) for k,v in attrs.items()})
def txt(g,x,y,s,size=7,weight='normal',color=INK,anchor='start'):
    global counter
    counter+=1; ident=f'r35_label_{counter:03d}'
    t=el(g,'text',x=x*P,y=y*P,id=ident,font_family='Arial',font_size=size,
         font_weight=weight,fill=color,text_anchor=anchor)
    t.text=s;labels.append({'id':ident,'text':s,'font_pt':size});return t
def line(g,x1,y1,x2,y2,color=EDGE,lw=.6,dash=None):
    a=dict(x1=x1*P,y1=y1*P,x2=x2*P,y2=y2*P,stroke=color,stroke_width=lw)
    if dash:a['stroke_dasharray']=dash
    return el(g,'line',**a)
def rect(g,x,y,w,h,fill='white',stroke=EDGE,lw=.6,r=0,**attrs):
    return el(g,'rect',x=x*P,y=y*P,width=w*P,height=h*P,rx=r*P,
              fill=fill,stroke=stroke,stroke_width=lw,**attrs)
def glyph(g,x,y,s,shape='circle',color=BLUE,r=1.2):
    if shape=='circle':el(g,'circle',cx=x*P,cy=y*P,r=r*P,fill=color,stroke=color,stroke_width=.7)
    elif shape=='square':rect(g,x-r,y-r,2*r,2*r,fill=color,stroke='none')
    else:
        el(g,'polygon',points=' '.join(f'{a*P},{b*P}' for a,b in [(x,y-r),(x+r,y),(x,y+r),(x-r,y)]),
           fill='white',stroke=color,stroke_width=.9)
    if s:txt(g,x,y+.72,s,6.5,color='white' if shape!='diamond' else INK,anchor='middle')
def arrow(g,x1,y1,x2,y2,name):
    dx=x2-x1;dy=y2-y1;length=math.hypot(dx,dy);ux=dx/length;uy=dy/length
    head=1.45;half=.68;bx=x2-head*ux;by=y2-head*uy
    el(g,'path',id=name,d=f'M{x1*P},{y1*P} L{bx*P},{by*P}',fill='none',stroke=BLUE,stroke_width=.85,stroke_linecap='round')
    el(g,'polygon',points=' '.join(f'{a*P},{b*P}' for a,b in [(x2,y2),(bx-half*uy,by+half*ux),(bx+half*uy,by-half*ux)]),fill=BLUE)
    connectors.append({'id':name,'total_mm':length,'visible_shaft_mm':length-head})
def ribbon(g,x1,y1,x2,y2,h,color,ident):
    # Aggregate-set flow only: every ribbon's vertical width = exact count * unit.
    mid=(x1+x2)/2
    path=f'M{x1*P},{y1*P} C{mid*P},{y1*P} {mid*P},{y2*P} {x2*P},{y2*P} L{x2*P},{(y2+h)*P} C{mid*P},{(y2+h)*P} {mid*P},{(y1+h)*P} {x1*P},{(y1+h)*P} Z'
    return el(g,'path',id=ident,d=path,fill=color,fill_opacity=.18,stroke=color,stroke_width=.45,stroke_opacity=.7)

HEIGHT=178
root=E.Element('{'+NS+'}svg',nsmap={None:NS},width='170mm',height=f'{HEIGHT}mm',viewBox=f'0 0 {170*P} {HEIGHT*P}')
el(root,'title').text='TRACE-DT Figure 1'
el(root,'desc').text='Fixed evidence, observed aggregate membership substitution, a synthetic capacity-two tie example, and means of pair-specific sharp substitution bounds. No confidence interval, individual rank inference, or joint global allocation.'
rect(root,0,0,170,HEIGHT,fill='white',stroke='none')
accepted=E.parse(str(args.panel_a/'Figure_1a.svg')).getroot()
ag=accepted.xpath('.//*[@id="Fig1a_vector_workflow"]')[0]
root.append(deepcopy(ag))
assert E.tostring(ag,method='c14n',exclusive=True)==E.tostring(root[-1],method='c14n',exclusive=True)
for t in ag.xpath('.//*[local-name()="text"]'):
    labels.append({'id':t.get('id'),'text':t.text,'font_pt':float(t.get('font-size'))})
for ext in ['svg','pdf','png']:
    shutil.copy2(args.panel_a/f'Figure_1a.{ext}',OUT/f'Figure_1a.{ext}')

# (b) A count-scaled alluvial comparison of complete observed membership sets.
# The outside nodes represent ONLY the opposite-list-only identities in the
# displayed union; they are not the total number of unselected targets.
b=el(root,'g',id='Fig1b_membership_flow')
txt(b,2.38,88,'b',10,'bold')
txt(b,6.8,88,'22 of 50 identities are replaced',8.5,'bold')
txt(b,6.8,94.5,'Colorectal · same evidence · B = 50',6.7,color=GRAY)
txt(b,17,99.5,brow['operator_code_a'],7.2,'bold',anchor='middle')
txt(b,74,99.5,brow['operator_code_b'],7.2,'bold',anchor='middle')
unit=.39;hs=shared*unit;hu=replaced*unit;top=103;only=top+hs+1;outside=128
ribbon(b,18,top,73,top,hs,BLUE,'shared_28_flow')
ribbon(b,18,only,73,outside,hu,GRAY,'leave_22_flow')
ribbon(b,18,outside,73,only,hu,PURPLE,'enter_22_flow')
for x in [16,73]:
    rect(b,x,top,2,hs,fill=BLUE,stroke='none')
rect(b,16,only,2,hu,fill=GRAY,stroke='none')
rect(b,73,only,2,hu,fill=PURPLE,stroke='none')
rect(b,16,outside,2,hu,fill=PURPLE,stroke='none')
rect(b,73,outside,2,hu,fill=GRAY,stroke='none')
txt(b,45.5,109.5,'28 retained',7.3,'bold',BLUE,anchor='middle')
txt(b,29.5,121.2,'22 leave',6.8,'bold',GRAY,anchor='middle')
txt(b,61.5,121.2,'22 enter',6.8,'bold',PURPLE,anchor='middle')
txt(b,17,140.5,'Not in 00100',6.5,color=GRAY,anchor='middle')
txt(b,74,140.5,'Not in 01001',6.5,color=GRAY,anchor='middle')

# (c) Fully enumerate the three legal lists; the possible state is their union.
c=el(root,'g',id='Fig1c_capacity_ties')
txt(c,87,88,'c',10,'bold')
txt(c,91.4,88,'One tie seat, three valid lists',8.5,'bold')
txt(c,91.4,94.5,'H = {a}; T = {b,c,d}; B = 2',6.7,color=GRAY)
txt(c,91.4,100.5,'Score boundary',6.5,'bold')
txt(c,132.5,100.5,'Admissible lists',6.5,'bold')
glyph(c,95,105.5,'a','circle',TEAL,1.45)
txt(c,99,106.2,'Above cutoff',6.5)
rect(c,91.4,110.5,27.5,9,fill='#F8F5EE',stroke=GOLD,lw=.6,r=.6)
for x,s in zip([96,105,114],'bcd'):glyph(c,x,115,s,'diamond',GOLD,1.45)
txt(c,105.2,124,'Choose r = 1 from T',6.5,color=GOLD,anchor='middle')
arrow(c,120.4,112.5,128.4,112.5,'one_tie_seat_to_admissible_lists')
admissible=[['a','b'],['a','c'],['a','d']]
for y,pair in zip([105.5,112.5,119.5],admissible):
    glyph(c,138,y,pair[0],'circle',TEAL,1.35)
    glyph(c,148,y,pair[1],'diamond',GOLD,1.45)
    line(c,140,y,145.6,y,EDGE,.6)
# Identifier order selects only the first concrete list; it does not confer
# extra scientific support on b relative to c/d.
rect(c,134.8,102.8,16.5,5.4,fill='none',stroke=BLUE,lw=.7,r=.5)
txt(c,154,106.2,'ID',6.5,'bold',BLUE)
line(c,91.4,127.2,163,127.2,EDGE,.6)
txt(c,91.4,131.5,'Necessary',6.5,'bold',TEAL)
txt(c,115,131.5,'Possible',6.5,'bold',GOLD)
txt(c,144,131.5,'ID realized',6.5,'bold',BLUE)
glyph(c,100,136,'a','circle',TEAL,1.4)
for x,s in zip([116,122,128,134],'abcd'):glyph(c,x,136,s,'diamond',GOLD,1.35)
for x,s in zip([148,155],'ab'):glyph(c,x,136,s,'square',BLUE,1.25)
txt(c,163,141,'Possible is a union, not a four-seat list',6.5,color=GRAY,anchor='end')

# (d) Linear percent axis: exact unrounded means determine marker positions.
d=el(root,'g',id='Fig1d_sharp_bound_axis')
txt(d,2.38,146.5,'d',10,'bold')
txt(d,6.8,146.5,'Sharp pairwise bounds across contexts',8.5,'bold')
txt(d,6.8,150.7,f'{pair_n:,} comparisons · mean endpoints, not a confidence interval',6.5,color=GRAY)
x0=26;x1=163;lo=.20;hi=.60
xs=[x0+(v-lo)/(hi-lo)*(x1-x0) for v in values]
line(d,xs[0],164.5,xs[2],164.5,EDGE,1.6)
for x,v,label,shape,color in zip(xs,values,['Lower-bound mean','ID mean','Upper-bound mean'],['circle','square','diamond'],[TEAL,BLUE,GOLD]):
    txt(d,x,155.5,label,6.5,color=color,anchor='middle')
    txt(d,x,160.2,f'{v*100:.1f}%',9,'bold',color,anchor='middle')
    line(d,x,166,x,169.5,EDGE,.5,dash='2 2')
    glyph(d,x,164.5,'',shape,color,1.1)
line(d,x0,169.5,x1,169.5,GRAY,.6)
for percent in [20,30,40,50,60]:
    x=x0+(percent/100-lo)/(hi-lo)*(x1-x0)
    line(d,x,169.5,x,170.6,GRAY,.6)
    txt(d,x,173.3,str(percent),6.5,color=GRAY,anchor='middle')
txt(d,(x0+x1)/2,177,'Top-50 membership replaced (%)',6.7,anchor='middle')

def write_svg(node,path):
    E.ElementTree(node).write(str(path),encoding='utf-8',xml_declaration=True)
write_svg(root,OUT/'Figure_1.svg')
# Independent supporting-panel editable masters, each at its native print size.
panel_boxes={'b':(0,82,85,60),'c':(85,82,85,60),'d':(0,142,170,36)}
for letter,node in [('b',b),('c',c),('d',d)]:
    x,y,w,h=panel_boxes[letter]
    panel=E.Element('{'+NS+'}svg',nsmap={None:NS},width=f'{w}mm',height=f'{h}mm',viewBox=f'0 0 {w*P} {h*P}')
    el(panel,'title').text=f'TRACE-DT Figure 1{letter}'
    rect(panel,0,0,w,h,fill='white',stroke='none')
    wrap=el(panel,'g',transform=f'translate({-x*P},{-y*P})');wrap.append(deepcopy(node))
    write_svg(panel,OUT/f'Figure_1{letter}.svg')

profile=OUT/'inkscape_profile';profile.mkdir(exist_ok=True)
env={**os.environ,'INKSCAPE_PROFILE_DIR':str(profile)}
logs=[]
for stem in ['Figure_1','Figure_1b','Figure_1c','Figure_1d']:
    for ext in ['pdf','png']:
        cmd=[args.inkscape,str(OUT/f'{stem}.svg'),'--export-area-page',f'--export-filename={OUT/stem}.{ext}']
        if ext=='png':cmd+=['--export-dpi=300']
        result=subprocess.run(cmd,check=True,capture_output=True,text=True,encoding='utf-8',env=env)
        logs.append({'command':cmd,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
query=subprocess.run([args.inkscape,str(OUT/'Figure_1.svg'),'--query-all'],check=True,capture_output=True,text=True,encoding='utf-8',env=env)
(OUT/'SVG_OBJECT_BOUNDS.csv').write_text(query.stdout,encoding='utf-8')
logs.append({'command':'query-all','exit_code':query.returncode,'stderr':query.stderr})
(OUT/'INKSCAPE_EXPORT_LOG.json').write_text(json.dumps(logs,indent=2),encoding='utf-8')
qa={'tool':subprocess.check_output([args.inkscape,'--version'],text=True).strip(),
    'full_size_mm':[170,HEIGHT],'panel_a_group_exclusive_c14n_unchanged':True,
    'panel_a_assets_sha256_unchanged':{ext:hashlib.sha256((OUT/f'Figure_1a.{ext}').read_bytes()).hexdigest()==hashlib.sha256((args.panel_a/f'Figure_1a.{ext}').read_bytes()).hexdigest() for ext in ['svg','pdf','png']},
    'minimum_font_pt':min(t['font_pt'] for t in labels),'labels':labels,'connectors':connectors,
    'observed_example':{'capacity':B,'shared':shared,'leave':replaced,'enter':replaced,'union':shared+2*replaced,'ribbon_unit_mm_per_identity':unit,'ribbon_heights_mm':[hs,hu,hu],
      'rendering':'aggregate membership counts; no individual identities or ranks inferred',
      'outside_nodes':'opposite-list-only members within the displayed union, not all unselected targets'},
    'synthetic_example':{'H':['a'],'T':['b','c','d'],'B':2,'r':1,'all_admissible_lists':admissible,'necessary':['a'],'possible':['a','b','c','d'],'ID_realized':['a','b']},
    'global_means':{'pairwise_comparisons':pair_n,'values_unrounded':values,'positions_mm':xs,'axis_percent':[20,60],'axis_mm':[x0,x1],'not_confidence_interval':True,'not_joint_global_allocation':True},
    'science_changed':False,'data_downsampled':False,'new_statistical_inference':False}
assert all(qa['panel_a_assets_sha256_unchanged'].values())
(OUT/'FIG1_VECTOR_QA.json').write_text(json.dumps(qa,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({k:qa[k] for k in ['tool','full_size_mm','minimum_font_pt','observed_example','synthetic_example','global_means']},indent=2))
