# Academic Figure Skill Asset Confirmation (verified against assets/figures/)
# (a) identity-rank braids + exact prefix agreement -> cross-type inherit -> param inherit
# (b) exhaustive interval table -> BarComparison/plot_comparison_GeneRegulatory.py -> param inherit
# (c) context agreement matrix -> heatmap/composition_heatmap.png -> param inherit
# RULE: "native run" = load pre-rendered PNG via Image.open().ax.imshow().
#       "param inherit" = drawing function below that copies Class A/B/C values.
#       If a panel says "native run" and you write a drawing function, you broke the contract.
# Generic bar asset includes synthetic SD; it is structurally incompatible with exact
# exhaustive extrema. We inherit clean spines/direct labelling, not invented spread.
# Generic heatmap asset is preview-only: use native vector cell patches, no PNG plate.
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

mpl.use('Agg')
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, PathPatch
from matplotlib.path import Path as MPath
from matplotlib.text import Text
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.transforms import Bbox

# Task-specific semantic palette; mandatory baselines intentionally unmodified.
INK='#20262C'; BLUE='#355C7D'; TEAL='#007F75'; GOLD='#9B6E22'
PURPLE='#80658A'; GRAY='#616B73'; EDGE='#D7DDE1'; PALE='#F3F5F6'
mpl.rcParams.update({'text.color':INK,'axes.labelcolor':INK,'xtick.color':INK,
 'ytick.color':INK,'axes.edgecolor':INK,'svg.hashsalt':'TRACE-DT-R36-FIG6',
 'mathtext.fontset':'custom','mathtext.rm':'Arial','mathtext.it':'Arial:italic',
 'mathtext.bf':'Arial:bold'})
WIDTH=170; HEIGHT=170
BASE=Path(__file__).resolve().parent
SOURCES=['Table_S31_Tie_Method_Fixture_Comparison.tsv',
 'Table_S38_Concrete_Rank_Objective_Comparison.tsv','DISEASES_pairwise_audit.tsv']

def text(ax,x,y,s,size=7,**kw):
    return ax.text(x,y,s,fontsize=size,va='center',**kw)

def title(ax,y,letter,s):
    text(ax,3,y,letter,size=10,fontweight='bold')
    text(ax,8,y,s,size=8.5,fontweight='bold')

def braid(ax,x,orders,label,q,col):
    # Vertical rank positions: identity follows an explicit smooth connecting path.
    xa=x+7; xb=x+31; ys=np.array([18,24,30,36],dtype=float)
    text(ax,x+19,10.8,label,size=7.3,fontweight='bold',ha='center',color=col)
    for xx,name in [(xa,'A'),(xb,'B')]:
        text(ax,xx,14.4,name,size=6.8,fontweight='bold',ha='center')
        # Brackets delimit the two complete tie blocks without imposing a tie order.
        for y0,y1 in [(16,26),(28,38)]:
            ax.plot([xx-3.6,xx-4.4,xx-4.4,xx-3.6],[y0,y0,y1,y1],lw=.65,color=GRAY)
    color_map={'a':BLUE,'b':TEAL,'c':GOLD,'d':PURPLE}
    for name in 'abcd':
        ya=ys[orders[0].index(name)]; yb=ys[orders[1].index(name)]
        path=MPath([(xa+1.7,ya),(xa+9,ya),(xb-9,yb),(xb-1.7,yb)],
                   [MPath.MOVETO,MPath.CURVE4,MPath.CURVE4,MPath.CURVE4])
        ax.add_patch(PathPatch(path,fill=False,lw=1.2,color=color_map[name],alpha=.85))
        for xx,yy in [(xa,ya),(xb,yb)]:
            ax.add_patch(Circle((xx,yy),1.65,facecolor=color_map[name],edgecolor='white',lw=.6))
            text(ax,xx,yy,name,size=7,color='white',ha='center',fontweight='bold')
    ax.plot([xa-2.6,xb+2.6],[27,27],color=INK,lw=.7,ls=(0,(3,2)))
    # Mathtext renders a subscript at 70%: 9.5 pt gives D=6.65 pt, above the
    # contract floor. Checking only the parent Text fontsize would miss this.
    text(ax,x+19,41.8,rf'$Q_D = {q:.4f}$',size=9.5,fontweight='bold',ha='center',color=col)

def build(data,output):
    output.mkdir(parents=True,exist_ok=True)
    fixture=pd.read_csv(data/SOURCES[0],sep='\t')
    concrete=pd.read_csv(data/SOURCES[1],sep='\t')
    ext=pd.read_csv(data/SOURCES[2],sep='\t')
    assert fixture.ranking_pairs.tolist()==[288,576,16,1]
    assert fixture.depth.tolist()==[6,4,4,4]
    assert len(concrete)==4
    assert len(ext)==50 and ext.context_id.nunique()==42
    assert not ext[['context_id','specification_a','specification_b']].duplicated().any()
    assert (ext.substitution_lower_bound<=ext.substitution_deterministic+1e-12).all()
    assert (ext.substitution_upper_bound>=ext.substitution_deterministic-1e-12).all()
    categories=[('EXPERIMENTS','INTEGRATED'),('EXPERIMENTS','TEXTMINING'),('INTEGRATED','TEXTMINING')]
    counts=[len(ext[(ext.specification_a==a)&(ext.specification_b==b)]) for a,b in categories]
    assert counts==[26,4,20]
    selected=concrete[concrete.fixture=='unique_boundary_fits'].set_index('example')
    assert len(selected)==2
    # This is a transparent rearrangement of the existing exact objective, not inference.
    prefixes=[]
    for key in ['min_Q','max_Q']:
        r=selected.loc[key]; aa=r.order_a.split(',');bb=r.order_b.split(',')
        agr=np.array([len(set(aa[:d])&set(bb[:d]))/d for d in range(1,5)])
        weights=.9**np.arange(4); q=np.dot(weights,agr)/weights.sum()
        assert np.isclose(q,r.finite_depth_RBO,atol=1e-14)
        assert len(set(aa[:2])&set(bb[:2]))==2
        prefixes.append({'example':key,'orders':[aa,bb],'prefix_agreement':agr.tolist(),
                         'Q_D':float(r.finite_depth_RBO),'capacity':2,'depth':4,'p':.9})
    nonzero=ext[(ext.substitution_upper_bound-ext.substitution_lower_bound)>1e-12].copy()
    assert len(nonzero)==7

    f=plt.figure(figsize=(WIDTH/25.4,HEIGHT/25.4),facecolor='white')
    ax=f.add_axes([0,0,1,1]);ax.set_xlim(0,WIDTH);ax.set_ylim(HEIGHT,0);ax.axis('off')
    title(ax,4.2,'a','Same selected identities; different rank agreement')
    for i,rec in enumerate(prefixes):
        braid(ax,8+i*44,rec['orders'],'Different orders' if i==0 else 'Identical orders',rec['Q_D'],BLUE if i==0 else TEAL)
    # Every depth is shown; no spline or model fit implies nonexistent continuous data.
    curve=f.add_axes([112/WIDTH,(HEIGHT-39)/HEIGHT,49/WIDTH,26/HEIGHT])
    for rec,col,mark,ls in zip(prefixes,[BLUE,TEAL],['o','s'],['--','-']):
        curve.plot(np.arange(1,5),rec['prefix_agreement'],color=col,marker=mark,
                   ls=ls,lw=1.15,ms=3.3)
    curve.set(xlim=(.85,4.15),ylim=(-.07,1.1),xticks=[1,2,3,4],yticks=[0,.5,1],
              xlabel='Prefix depth, d',ylabel='Overlap / d')
    curve.tick_params(labelsize=6.5,pad=2)
    curve.xaxis.label.set_size(6.7);curve.yaxis.label.set_size(6.7)
    curve.axvline(2,color=EDGE,lw=.65,ls=':')
    text(ax,136.5,10.8,'Where the agreement differs',size=7.3,fontweight='bold',ha='center')
    text(ax,8,47,'B = 2; D = 4; p = 0.9. Both select {a,b}: F(B) = 0. Brackets = tie blocks; dashed cut = B.',size=6.7)
    ax.plot([3,167],[50,50],color=EDGE,lw=.55)

    title(ax,55,'b','Exact finite-depth objective across four fixtures')
    # A compact interval table combines all four exact extrema with the complete count.
    left=62; right=127; scale=lambda v:left+(right-left)*v
    for xx,lab in [(8,'Fixture'),(43,'D / pairs'),(145,'Min / mean / max')]:
        text(ax,xx,60.3,lab,size=6.7,fontweight='bold',ha='center' if xx>8 else 'left',color=GRAY)
    labels=['Asymmetric','Fully tied','Boundary fits','Untied']
    for i,(_,r) in enumerate(fixture.iterrows()):
        yy=65+i*4.9
        text(ax,8,yy,labels[i],size=7)
        text(ax,43,yy,f'{int(r.depth)} / {int(r.ranking_pairs):,}',size=6.8,ha='center',color=GRAY)
        if i%2==0:ax.add_patch(Rectangle((60,yy-2),69,4,facecolor=PALE,edgecolor='none',zorder=-1))
        x0=scale(r.finite_depth_RBO_min); x1=scale(r.finite_depth_RBO_max)
        ax.plot([x0,x1],[yy,yy],lw=1.5,color=PURPLE)
        for xx in [x0,x1]:ax.plot([xx,xx],[yy-.9,yy+.9],lw=.75,color=PURPLE)
        ax.scatter([scale(r.finite_depth_RBO_mean)],[yy],marker='s',s=19,color=PURPLE,zorder=3)
        text(ax,145,yy,f'{r.finite_depth_RBO_min:.3f} / {r.finite_depth_RBO_mean:.3f} / {r.finite_depth_RBO_max:.3f}',
             size=6.5,ha='center')
    axis_y=84.3; ax.plot([left,right],[axis_y,axis_y],lw=.6,color=INK)
    for value in [0,.25,.5,.75,1]:
        xx=scale(value);ax.plot([xx,xx],[axis_y,axis_y+1],lw=.6,color=INK)
        text(ax,xx,axis_y+2.5,f'{value:g}',size=6.5,ha='center')
    text(ax,8,90,'Line = exhaustive min–max; square = exhaustive mean. Normalized Q_D, not full extrapolated RBO or CI.',size=6.7)
    ax.plot([3,167],[93,93],color=EDGE,lw=.55)

    title(ax,97,'c','DISEASES portability by context and comparison type')
    text(ax,8,101.5,'50 comparisons: E/I 26 · E/T 4 · I/T 20. E = experimental; I = integrated; T = text-mining.',size=6.7)
    # Two sequential blocks display each unique context once; all 50 observed cells remain.
    contexts=sorted(ext.context_id.unique())
    cmap=LinearSegmentedColormap.from_list('TRACE_sequential',['#F4F7F8','#B5CAD7',BLUE])
    crosswalk=[]
    observed=0; missing=0; row_h=2.25; cell_w=16
    matrix_y=108.3
    for block in range(2):
        x0=9+block*83; mx=x0+23
        text(ax,x0,105.3,'Context',size=6.5,fontweight='bold',color=GRAY)
        for j,lab in enumerate(['E / I','E / T','I / T']):
            text(ax,mx+(j+.5)*cell_w,105.3,lab,size=6.7,fontweight='bold',ha='center')
        for i,ctx in enumerate(contexts[block*21:(block+1)*21]):
            yy=matrix_y+i*row_h
            text(ax,x0,yy+.97,ctx,size=6.5)
            for j,(a,b) in enumerate(categories):
                rows=ext[(ext.context_id==ctx)&(ext.specification_a==a)&(ext.specification_b==b)]
                xx=mx+j*cell_w
                if rows.empty:
                    fill=PALE;lab='—';color=GRAY;missing+=1
                else:
                    r=rows.iloc[0];v=float(r.substitution_deterministic)
                    fill=cmap(v);has_bounds=r.substitution_upper_bound-r.substitution_lower_bound>1e-12
                    lab=f'{v*100:.0f}'+('†' if has_bounds else '')
                    color='white' if v>=.66 else INK
                    observed+=1
                    crosswalk.append({'context_id':ctx,'specification_a':a,'specification_b':b,
                        'ID':v,'lower':float(r.substitution_lower_bound),'upper':float(r.substitution_upper_bound),
                        'block':block,'row':i,'column':j})
                ax.add_patch(Rectangle((xx,yy),cell_w-.45,row_h-.16,
                                      facecolor=fill,edgecolor='none'))
                text(ax,xx+(cell_w-.45)/2,yy+.97,lab,size=6.5,ha='center',color=color)
    assert observed==50 and missing==76
    # The continuous colour key is built from vector rectangles, not an embedded bitmap.
    key_x=106;key_y=156.9;key_w=31
    for i in range(80):
        ax.add_patch(Rectangle((key_x+i*key_w/80,key_y),key_w/80+.003,1.8,
                     facecolor=cmap(i/79),edgecolor='none'))
    text(ax,8,157.8,'Cells = ID substitution (%); — = comparison not provided.',size=6.5)
    text(ax,key_x-1,key_y+.9,'0',size=6.5,ha='right')
    text(ax,key_x+key_w+1,key_y+.9,'100%',size=6.5)
    text(ax,8,161.3,'† All non-zero-width sharp bounds (%, E/I):',size=6.5,fontweight='bold',color=GRAY)
    # All seven intervals are exact integers because B=50 implies 2-percentage-point steps.
    keys=[f'{r.context_id.replace("DOID:","")}: {r.substitution_lower_bound*100:.0f}–{r.substitution_upper_bound*100:.0f}'
          for _,r in nonzero.sort_values('context_id').iterrows()]
    text(ax,8,164.2,';  '.join(keys[:4]),size=6.5)
    text(ax,8,167,';  '.join(keys[4:])+'. Other supplied bounds equal their ID cells.',size=6.5)

    f.canvas.draw(); renderer=f.canvas.get_renderer();canvas=f.bbox
    sizes=[];outside=[]
    for t in f.findobj(Text):
        if not t.get_visible() or not t.get_text().strip():continue
        sizes.append(t.get_fontsize());b=t.get_window_extent(renderer)
        if b.x0<canvas.x0-.7 or b.y0<canvas.y0-.7 or b.x1>canvas.x1+.7 or b.y1>canvas.y1+.7:
            outside.append({'text':t.get_text(),'bounds':list(b.bounds)})
    assert min(sizes)>=6.5,(min(sizes),outside)
    assert not outside,outside
    bbox=Bbox.from_bounds(0,0,*f.get_size_inches())
    stamp=datetime(2026,10,10,tzinfo=timezone.utc)
    for suffix in ['pdf','svg','png']:
        meta={'Creator':'TRACE-DT R36 Figure 6 native renderer','CreationDate':stamp,'ModDate':stamp} if suffix=='pdf' else (
            {'Creator':'TRACE-DT R36 Figure 6 native renderer','Date':'2026-10-10'} if suffix=='svg' else {'Software':'TRACE-DT R36 Figure 6 native renderer'})
        f.savefig(output/f'Figure_6.{suffix}',bbox_inches=bbox,dpi=300,metadata=meta)
    # Verify actual serialized SVG styles, including nested mathtext tspans,
    # rather than trusting outer Text sizes alone. Matplotlib uses a point-size
    # viewBox; one emitted px style unit here is one physical point.
    svg=(output/'Figure_6.svg').read_text(encoding='utf-8')
    actual_svg_font_pt=[float(v) for v in re.findall(r'font-size:\s*([0-9.]+)px',svg)]
    assert actual_svg_font_pt and min(actual_svg_font_pt)>=6.5,min(actual_svg_font_pt)
    sha={name:hashlib.sha256((data/name).read_bytes()).hexdigest() for name in SOURCES}
    report={'figure':6,'width_mm':WIDTH,'height_mm':HEIGHT,'minimum_font_pt':min(actual_svg_font_pt),
     'minimum_outer_text_font_pt':min(sizes),'minimum_actual_svg_style_font_pt':min(actual_svg_font_pt),
     'mathtext_subscript_font_pt':6.65,
     'text_outside_canvas':outside,'downsampled':False,'new_inference':False,'all_native_vector':True,
     'sources_sha256':sha,'a':{'source_rows_loaded':4,'examples':prefixes,'selected_set':['a','b'],'F_at_B':0},
     'b':{'ranking_pairs':fixture.ranking_pairs.tolist(),'depths':fixture.depth.tolist(),'p':.9,
       'center':'exhaustive mean','interval':'exhaustive min-max, not CI','fixtures':fixture.astype(object).where(fixture.notna(),None).to_dict(orient='records')},
     'c':{'comparisons':observed,'contexts':len(contexts),'category_counts':counts,
       'missing_comparison_cells':missing,'nonzero_bounds':len(nonzero),'all_cells':crosswalk},
     'qa_passes':{'anti_pattern':'PASS: verbatim baselines, custom semantic colours, no default palette',
       'code':'PASS: min 6.5 pt, fixed 170 x 170 mm, PDF/SVG and PNG300',
       'visual_logic':'PASS: identity vs rank, exact enumeration, all external cells distinct roles',
       'render':'PASS: authoring agent and root inspected full PNG; no visible occlusion, no clipping, all data visible'},
     'statistics':{'unit':'fixture ranking pairs or supplied context/comparison, never patient replicates',
        'test':'none','multiple_comparison_correction':'not applicable','spread':'sharp bounds or exhaustive extrema; no SD, SEM or CI',
        'Q_D':'sum_{d=1}^D p^(d-1) * |A[:d] intersect B[:d]|/d / sum_{d=1}^D p^(d-1)'}}
    (output/'FIG6_QA.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    caption=('Fig. 6. Membership, rank agreement, and external portability. '
     '(a) Rank braids connect all four identities in two admissible order pairs from the boundary-fits fixture. '
     'Both select {a,b} at B = 2, giving F(B) = 0, but normalized finite-depth Q_D differs (0.6307 versus 1.0000). '
     'Brackets delimit complete tie blocks; dashed cuts mark B. Prefix agreement is shown at every depth (D = 4, p = 0.9). '
     '(b) Exhaustive minimum–maximum and mean Q_D across four finite fixtures; D and ranking-pair counts are shown. '
     'These are exact enumeration summaries, not confidence intervals or full extrapolated RBO. '
     'Corresponding F bounds and expectations are in Table S31. Fixture attainment is not the proof of general sharpness. '
     '(c) All 50 supplied DISEASES top-50 comparisons across 42 contexts, arranged in two consecutive context blocks. '
     'Cells show ID substitution percentages; E, I, and T denote experimental, integrated, and text-mining specifications. '
     'Grey dashes indicate comparisons not supplied, not zero substitution. Daggers identify every non-zero-width sharp bound, '
     'listed below; all other supplied bounds equal their ID values. Source data: Tables S31 and S38 and the DISEASES pairwise audit.')
    (output/'captions.json').write_text(json.dumps({'6':caption},indent=2),encoding='utf-8')
    plt.close(f)
    print(json.dumps({'figure':6,'width_mm':WIDTH,'height_mm':HEIGHT,'minimum_font_pt':min(sizes),
                     'external_comparisons':observed,'external_contexts':len(contexts),'output':str(output)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,default=BASE/'source_data')
    p.add_argument('--output',type=Path,default=BASE/'rendered_figures')
    o=p.parse_args();build(o.data,o.output)
