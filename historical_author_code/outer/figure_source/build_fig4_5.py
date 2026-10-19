# Academic Figure Skill Asset Confirmation (verified against assets/figures/)
# (4a,5b) discrete frontier / score slopegraph -> LineTrend/plot_sweep.py -> param inherit
# (4b,4c) nested finite memberships -> BarComposition/plot_brute_force.py -> param inherit
# (4c,5a) exact counts / binary decisions -> heatmap/plot_composition.py -> param inherit
# (5c) paired frozen scores + marginal frequencies -> MarginalDensity/plot_VariableCorrelation.py -> param inherit
# RULE: "native run" = load pre-rendered PNG via Image.open().ax.imshow().
#       "param inherit" = drawing function below that copies Class A/B/C values.
#       If a panel says "native run" and you write a drawing function, you broke the contract.
# Semantic incompatibilities: native templates hard-code model datasets, bootstrap tests,
# independent category totals or quality-filtered microbial regression; these are not
# finite nested memberships and frozen target scores. No native template is relabelled.
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
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.transforms import Bbox
from matplotlib.text import Text
from matplotlib.ticker import NullLocator
from matplotlib.colors import to_rgb
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import numpy as np
import pandas as pd

INK='#20262C'; BLUE='#355C7D'; TEAL='#007F75'; GOLD='#9B6E22'
PURPLE='#80658A'; GRAY='#616B73'; EDGE='#D7DDE1'; PALE='#F3F5F6'
mpl.rcParams.update({'text.color':INK,'axes.labelcolor':INK,'xtick.color':INK,
    'ytick.color':INK,'axes.edgecolor':INK,'svg.hashsalt':'TRACE-DT-R36-FIG4-5',
    'hatch.linewidth':.4})

BASE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--data',type=Path,default=BASE/'source_data')
parser.add_argument('--output',type=Path,default=BASE/'rendered_figures')
opt=parser.parse_args(); DATA=opt.data; OUT=opt.output
OUT.mkdir(parents=True,exist_ok=True)
QA=[]; CROSSWALK=[]
def load(name):
    path=DATA/name
    if not path.exists(): path=BASE/'additional_source_data'/name
    if not path.exists(): raise FileNotFoundError(name)
    return pd.read_csv(path,sep='\t')
def source_path(name):
    return DATA/name if (DATA/name).exists() else BASE/'additional_source_data'/name
def figure(height): return plt.figure(figsize=(170/25.4,height/25.4),facecolor='white')
def axmm(f,x,y,w,h): return f.add_axes([x/170,y/(f.get_figheight()*25.4),w/170,h/(f.get_figheight()*25.4)])
def ft(f,x,y,text,size=7,**kw):
    return f.text(x/170,y/(f.get_figheight()*25.4),text,fontsize=size,**kw)
def heading(f,x,y,letter,text):
    ft(f,x,y,letter,size=10,fontweight='bold',va='bottom')
    ft(f,x+5,y,text,size=8.5,fontweight='bold',va='bottom')
def off(ax): ax.set_axis_off()
def light(col,a): return tuple((1-a)+a*np.array(to_rgb(col)))
def finish(f,num,sources,panels):
    for ax in f.axes:
        if not ax.axison: continue
        xlo,xhi=sorted(ax.get_xlim()); ylo,yhi=sorted(ax.get_ylim())
        ax.set_xticks([x for x in ax.get_xticks() if xlo<=x<=xhi])
        ax.set_yticks([y for y in ax.get_yticks() if ylo<=y<=yhi])
    f.canvas.draw(); rend=f.canvas.get_renderer(); sizes=[]; outside=[]
    for t in f.findobj(Text):
        if not t.get_visible() or not t.get_text().strip():continue
        sizes.append(t.get_fontsize()); b=t.get_window_extent(rend)
        if b.x0<f.bbox.x0-1 or b.y0<f.bbox.y0-1 or b.x1>f.bbox.x1+1 or b.y1>f.bbox.y1+1:
            outside.append({'text':t.get_text(),'bounds':list(b.bounds)})
    assert min(sizes)>=6.5,(num,min(sizes))
    assert not outside,(num,outside)
    stamp=datetime(2026,10,10,tzinfo=timezone.utc)
    canvas=Bbox.from_bounds(0,0,*f.get_size_inches())
    for ext in ('svg','pdf','png'):
        meta=({'Date':'2026-10-10','Creator':'TRACE-DT R36 native figure renderer'} if ext=='svg' else
            {'CreationDate':stamp,'ModDate':stamp,'Creator':'TRACE-DT R36 native figure renderer'} if ext=='pdf' else
            {'Software':'TRACE-DT R36 native figure renderer'})
        f.savefig(OUT/f'Figure_{num}.{ext}',bbox_inches=canvas,dpi=300,metadata=meta)
    QA.append({'figure':num,'width_mm':170,'height_mm':f.get_figheight()*25.4,
        'minimum_font_pt':min(sizes),'text_outside_canvas':outside,'data_downsampled':False,
        'new_inference':False,'native_vectors':True,'passes_0_1_2':'passed source checks; pass 3 visual inspection required'})
    CROSSWALK.append({'figure':num,'sources_sha256':{name:hashlib.sha256(source_path(name).read_bytes()).hexdigest() for name in sources},
        'panels':panels,'statistics':'Finite-universe descriptive; no statistical test, sampling CI, fitted model, or biological replication claim.'})
    plt.close(f)

# Figure 4: finite guarantees separate from retained-evidence structure.
front=load('Figure_4_A_frequency_frontier.tsv').sort_values('threshold')
contexts=load('Figure_4_B_context_32of32.tsv').sort_values(['possible_32','necessary_32','context_name'],ascending=[False,False,True]).reset_index(drop=True)
coh=load('Table_S18_Cohort_Summary.tsv').set_index('cohort')
assert len(front)==32 and front.threshold.tolist()==list(range(1,33))
assert len(contexts)==23
assert np.all(front.necessary<=front.deterministic) and np.all(front.deterministic<=front.possible)
assert contexts[['necessary_32','deterministic_32','possible_32']].sum().tolist()==[90,133,532]
assert np.all(contexts.necessary_32<=contexts.deterministic_32) and np.all(contexts.deterministic_32<=contexts.possible_32)
f=figure(170)
heading(f,6,160,'a','Selection guarantees across 32 specifications')
ft(f,17,154,'Necessary (N)',size=6.5,color=TEAL)
ft(f,45,154,'ID realized',size=6.5,color=BLUE)
ft(f,69,154,'Possible (P)',size=6.5,color=GOLD)
ax=axmm(f,17,111,75,40)
x=front.threshold.to_numpy(); n=front.necessary.to_numpy(); i=front.deterministic.to_numpy(); p=front.possible.to_numpy()
ax.fill_between(x,n,i,step='post',color=BLUE,alpha=.11,linewidth=0)
ax.fill_between(x,i,p,step='post',color=GOLD,alpha=.10,linewidth=0)
for arr,col,ls,mark in [(n,TEAL,'-','o'),(i,BLUE,'--','s'),(p,GOLD,':','D')]:
    ax.step(x,arr,where='post',color=col,lw=1.2,ls=ls)
    ax.scatter(x[[0,7,15,23,31]],arr[[0,7,15,23,31]],s=13,marker=mark,facecolors='white' if col==GOLD else col,edgecolors=col,lw=.65,zorder=3)
ax.axvline(32,lw=.4,color=EDGE,zorder=0)
for val,col,txt,dy in [(90,TEAL,'N  90',-2),(133,BLUE,'ID  133',2),(532,GOLD,'P  532',0)]:
    ax.annotate(txt,xy=(32,val),xytext=(5,dy),textcoords='offset points',fontsize=6.5,color=col,va='center')
ax.set(xlim=(1,38),ylim=(65,13000),yscale='log',xticks=[1,8,16,24,32],yticks=[100,1000,10000],
    xlabel='Minimum selected specifications',ylabel='Target–context pairs (log scale)')
ax.set_yticklabels(['100','1,000','10,000'])
ax.yaxis.set_minor_locator(NullLocator());ax.tick_params(labelsize=6.5,length=2.5,pad=2)
ax.xaxis.label.set_fontsize(7); ax.yaxis.label.set_fontsize(7)
ft(f,17,100,'Bands show nested membership counts, not confidence intervals.',size=6.5,color=GRAY)
heading(f,105,160,'b','One retained positive row')
axb=axmm(f,105,112,57,39);off(axb);axb.set(xlim=(0,100),ylim=(0,3))
cohort_keys=['necessary_32','deterministic_32_not_necessary','possible_32_not_deterministic']
cohort_labels=['Necessary all 32','ID-only all 32','Possible-only all 32']
singleton_counts=[]
for j,(key,label,col) in enumerate(zip(cohort_keys,cohort_labels,[TEAL,BLUE,GOLD])):
    r=coh.loc[key]; numerator=int(r.retained_row_singleton_n);denominator=int(r.n);pct=100*numerator/denominator
    assert np.isclose(pct/100,r.retained_row_singleton_fraction)
    singleton_counts.append([numerator,denominator]); yy=2.45-j
    axb.text(0,yy+.24,label,fontsize=6.7,va='bottom')
    axb.text(100,yy+.24,f'{pct:.1f}%',fontsize=6.7,va='bottom',ha='right',color=col)
    axb.add_patch(Rectangle((0,yy-.16),100,.33,fc=PALE,ec='none'))
    axb.add_patch(Rectangle((0,yy-.16),pct,.33,fc=col,ec='none'))
    axb.text(3,yy,f'{numerator}/{denominator}',fontsize=6.7,color='white',va='center')
assert singleton_counts==[[76,90],[41,43],[388,399]]
ft(f,105,103,'Mutually exclusive cohorts',size=6.5,color=GRAY)
heading(f,6,91,'c','All-32 memberships across all 23 cancer contexts')
labels=axmm(f,5,15,61,70); off(labels);labels.set(xlim=(0,1),ylim=(23,0))
matrix=axmm(f,67,15,29,70);off(matrix);matrix.set(xlim=(0,3),ylim=(23,0))
bars=axmm(f,105,15,57,70);bars.set(xlim=(0,80),ylim=(23,0),yticks=[],xticks=[0,20,40,60,80],xlabel='All-32 target–context pairs')
bars.spines['left'].set_visible(False);bars.tick_params(labelsize=6.5,length=2.5,pad=2);bars.xaxis.label.set_fontsize(7)
for j,(label,col,mark) in enumerate([('N',TEAL,'o'),('ID',BLUE,'s'),('P',GOLD,'D')]):
    ft(f,67+(j+.5)*29/3,87,label,size=7,fontweight='bold',color=col,ha='center')
ft(f,105,87,'Nested counts: N / ID / P',size=7,color=GRAY)
extensions=[]
for j,r in contexts.iterrows():
    y=j+.5
    if j%2==0:
        labels.add_patch(Rectangle((0,j),1,1,fc=PALE,ec='none'))
        bars.add_patch(Rectangle((0,j),80,1,fc=PALE,ec='none',zorder=0))
    labels.text(.015,y,r.context_name,fontsize=6.5,va='center')
    vals=[int(r.necessary_32),int(r.deterministic_32),int(r.possible_32)]
    for k,(v,col) in enumerate(zip(vals,[TEAL,BLUE,GOLD])):
        matrix.add_patch(Rectangle((k+.03,j+.07),.94,.86,fc=light(col,.06+.44*v/80),ec='white',lw=.4))
        matrix.text(k+.5,y,str(v),fontsize=6.5,ha='center',va='center',color=INK)
    widths=[vals[0],vals[1]-vals[0],vals[2]-vals[1]];start=0;extensions.append(widths)
    for width,col,hatch in zip(widths,[TEAL,BLUE,GOLD],['','','///']):
        if width:bars.add_patch(Rectangle((start,j+.24),width,.52,facecolor=light(col,.8),edgecolor=col,linewidth=.4,hatch=hatch))
        start+=width
    assert start==vals[-1]
ft(f,5,2.8,'Bars partition possible counts into N, ID − N and P − ID; these are finite sets, not biological replication.',size=6.5,color=GRAY)
finish(f,4,['Figure_4_A_frequency_frontier.tsv','Figure_4_B_context_32of32.tsv','Table_S18_Cohort_Summary.tsv'],{
    'a':{'thresholds':32,'series':3,'all32_counts':[90,133,532],'interval':'set-membership envelope, not CI'},
    'b':{'cohorts':3,'singleton_counts':singleton_counts,'denominator_unit':'target-context pairs'},
    'c':{'contexts':23,'sort':'possible count descending; necessary count descending; name ascending',
        'nested_counts_total':[90,133,532],'exact_extensions_N_IDminusN_PminusID':extensions}})

# Figure 5: exact per-specification case decisions + a full competitive displacement view.
cases=load('R26_DETERMINISTIC_MAIN_CASES.tsv').sort_values('case_order')
chain=load('Table_S21_Case_Record_Chain.tsv')
trajectory=load('R17_DETERMINISTIC_CASE_TRAJECTORIES.tsv')
assert len(trajectory)==128 and len(cases)==4
cut=load('Table_S25_PPP5C_Cutoff_Comparison.tsv')
competitors=load('Table_S26_PPP5C_All_Competitors.tsv')
cross=competitors[competitors.crossed_PPP5C_upward]
assert len(competitors)==6086 and len(cross)==495
assert sum(competitors.targetId=='ENSG00000011485')==1
f=figure(170)
heading(f,6,160,'a','Four fixed cases across the full specification grid')
ft(f,6,154,'Frozen Open Targets 26.06 evidence · columns follow five-bit codes 00000 → 11111',size=6.5,color=GRAY)
grid=axmm(f,57,100,92,50);off(grid);grid.set(xlim=(0,32),ylim=(0,18.5))
for k in range(5):
    yy=17.2-k
    grid.text(-.7,yy,f'O{k+1}',ha='right',va='center',fontsize=6.5)
    for j in range(32):
        bit=(j>>(4-k))&1
        grid.add_patch(Rectangle((j+.08,yy-.34),.84,.68,fc=GRAY if bit else 'white',ec=EDGE,lw=.4))
for j in [0,7,15,23,31]:grid.text(j+.5,18.25,str(j+1).zfill(2),ha='center',va='center',fontsize=6.5)
ft(f,153,146,'Bits',size=6.5,color=GRAY)
ft(f,153,141,'□ 0',size=6.5,color=GRAY)
ft(f,153,136,'■ 1',size=6.5,color=GRAY)
gene_specs=[('C19orf33','Ovarian',TEAL,'necessary_selection_count'),('PAGE4','Hepatocellular',BLUE,'deterministic_selection_count'),('PPP5C','Bladder',BLUE,'deterministic_selection_count'),('FGFR2','Colorectal',GRAY,'primary_eligibility_blocked_count')]
decision_counts=[];case_rows=[]
for j,((gene,context,col,field),(_,r)) in enumerate(zip(gene_specs,cases.iterrows())):
    g=trajectory[trajectory.targetId==r.targetId].copy().sort_values('operator_code')
    assert len(g)==32 and g.operator_code.astype(int).tolist()==[int(format(i,'05b')) for i in range(32)]
    own=chain[chain.targetId==r.targetId]; case_rows.append(len(own))
    yy=10.7-j*3.1
    pos_y=100+yy/18.5*50
    ft(f,6,pos_y+.8,gene,size=7.5,fontweight='bold',va='center')
    ft(f,6,pos_y-3.0,f'{context} · {len(own)} retained '+('row' if len(own)==1 else 'rows'),size=6.5,color=GRAY,va='center')
    if j==0:
        values=g.necessary_selected.to_numpy(dtype=bool);assert values.sum()==32
    elif j<3:
        values=g.selected_top50.to_numpy(dtype=bool);assert values.sum()==int(r[field])
    else:
        values=np.ones(32,dtype=bool);assert int(r[field])==32 and not g.scored.any()
    count=int(values.sum());decision_counts.append(count)
    for k,active in enumerate(values):
        grid.add_patch(Rectangle((k+.05,yy-.82),.90,1.64,fc=col if active and j<3 else PALE if j==3 else 'white',ec=col if active and j<3 else EDGE,lw=.4))
        if j==3:
            grid.plot([k+.20,k+.80],[yy-.50,yy+.50],color=GRAY,lw=.6)
            grid.plot([k+.20,k+.80],[yy+.50,yy-.50],color=GRAY,lw=.6)
    ft(f,153,pos_y+.2,f'{count}/32',size=8,color=col,fontweight='bold',va='center')
    ft(f,153,pos_y-3.0,'necessary' if j==0 else 'selected' if j<3 else 'rule-blocked',size=6.5,color=col,va='center')
assert decision_counts==[32,16,8,32] and case_rows==[1,1,1,12]
ft(f,6,94,'White = not selected; × = rule-blocked (not biological negative). Filled cells retain the reported case-specific state.',size=6.5,color=GRAY)
heading(f,6,84,'b','Fixed score; moving cutoff')
ax=axmm(f,18,22,45,51)
ax.plot([0,1],cut.PPP5C_score,color=BLUE,lw=1.3,marker='o',ms=3.5)
ax.plot([0,1],cut.cutoff_score,color=GOLD,lw=1.3,ls='--',marker='s',ms=3.5)
for j,r in cut.iterrows():
    ax.annotate(f'Rank {int(r.PPP5C_rank)}',(j,r.PPP5C_score),xytext=(0,9),textcoords='offset points',ha='center',fontsize=6.5,color=BLUE)
    ax.annotate(f'{r.cutoff_score:.4f}',(j,r.cutoff_score),xytext=(0,-12 if j==0 else 9),textcoords='offset points',ha='center',fontsize=6.5,color=GOLD)
ax.set(xlim=(-.2,1.2),ylim=(.45,1.01),yticks=[.5,.6,.7,.8,.9,1],xticks=[0,1],xticklabels=['01000','01001'],ylabel='Score',xlabel='Specification')
ax.tick_params(labelsize=6.5,pad=2,length=2.5);ax.xaxis.label.set_fontsize(7);ax.yaxis.label.set_fontsize(7)
ft(f,18,78,'PPP5C 0.590',size=6.7,color=BLUE)
ft(f,44,78,'Top-50 cutoff',size=6.7,color=GOLD)
ft(f,7,10,'Own score unchanged;',size=6.5,color=GRAY)
ft(f,7,6,'495 additional targets outrank it.',size=6.5,color=GRAY)
heading(f,82,84,'c','Competitive displacement')
ax=axmm(f,92,15,60,60)
bins=np.linspace(0,1,26)
allx=competitors.operator_score_O5_0.to_numpy(); ally=competitors.operator_score_O5_1.to_numpy()
cx=cross.operator_score_O5_0.to_numpy(); cy=cross.operator_score_O5_1.to_numpy()
assert np.isfinite(allx).all() and np.isfinite(ally).all()
assert np.all((allx>=0)&(allx<=1)) and np.all((ally>=0)&(ally<=1))
assert np.all((cx<=.59+1e-14)&(cy>.59))
ax.add_patch(Rectangle((0,.59),.59,.41,facecolor=GOLD,alpha=.08,edgecolor='none',zorder=0))
ax.plot([0,1],[0,1],color=GRAY,lw=.65,ls='--',zorder=1)
ax.scatter(allx,ally,c=GRAY,s=3,alpha=.30,linewidths=0,zorder=2)
ax.scatter(cx,cy,c=GOLD,s=4.5,alpha=.80,linewidths=0,zorder=3)
ax.axhline(.59,color=BLUE,lw=.75);ax.axvline(.59,color=BLUE,lw=.75)
ax.scatter([.59],[.59],c=BLUE,s=36,marker='*',zorder=6)
example=competitors[competitors.targetId=='ENSG00000018625'].iloc[0]
ex=float(example.operator_score_O5_0);ey=float(example.operator_score_O5_1)
ax.scatter([ex],[ey],facecolors='none',edgecolors=PURPLE,s=37,lw=1.0,zorder=7)
ax.annotate('Two-row case\nFig. 3c',xy=(ex,ey),xytext=(.69,.84),fontsize=6.5,color=PURPLE,
    arrowprops={'arrowstyle':'-','color':PURPLE,'lw':.6},ha='left')
ax.text(.96,.11,'6,086 scored targets\n495 upward crossers',ha='right',va='center',transform=ax.transAxes,fontsize=6.5)
ax.set(xlim=(-.015,1.015),ylim=(-.015,1.015),aspect='equal',xticks=[0,.2,.4,.6,.8,1],yticks=[0,.2,.4,.6,.8,1],xlabel='Score under 01000',ylabel='Score under 01001')
ax.tick_params(labelsize=6.5,length=2.5,pad=2);ax.xaxis.label.set_fontsize(7);ax.yaxis.label.set_fontsize(7)
top=axmm(f,92,76.5,60,6.0); right=axmm(f,153.5,15,7.0,60)
hx,edges=np.histogram(allx,bins);hy,_=np.histogram(ally,bins);hcx,_=np.histogram(cx,bins);hcy,_=np.histogram(cy,bins)
assert hx.sum()==hy.sum()==6086 and hcx.sum()==hcy.sum()==495
top.stairs(hx,edges,fill=True,color=light(GRAY,.40),lw=.5)
top.stairs(hcx,edges,fill=True,color=light(GOLD,.85),lw=.5)
top.set(xlim=(-.015,1.015),ylim=(0,max(hx)*1.05));off(top)
right.stairs(hy,edges,fill=True,color=light(GRAY,.40),orientation='horizontal',lw=.5)
right.stairs(hcy,edges,fill=True,color=light(GOLD,.85),orientation='horizontal',lw=.5)
right.set(ylim=(-.015,1.015),xlim=(0,max(hy)*1.05));off(right)
ft(f,163,48,f'Marginal counts (max {int(max(hy)):,})',size=6.5,rotation=90,ha='center',va='center',color=GRAY)
top.text(.98,.80,f'Max {int(max(hx)):,}',transform=top.transAxes,ha='right',va='center',fontsize=6.5,color=GRAY)
finish(f,5,['R26_DETERMINISTIC_MAIN_CASES.tsv','R17_DETERMINISTIC_CASE_TRAJECTORIES.tsv','Table_S21_Case_Record_Chain.tsv','Table_S25_PPP5C_Cutoff_Comparison.tsv','Table_S26_PPP5C_All_Competitors.tsv'],{
    'a':{'cases':4,'specifications_each':32,'trajectory_rows':128,'retained_rows':case_rows,'decision_counts':decision_counts,'denominator_unit':'declared specifications, not biological replicates','FGFR2_status':'primary eligibility blocked all32; unresolved ancestry also affects 16'},
    'b':{'PPP5C_scores':cut.PPP5C_score.tolist(),'ranks':cut.PPP5C_rank.tolist(),'cutoffs':cut.cutoff_score.tolist(),'specifications':cut.code.tolist()},
    'c':{'points_total':6086,'includes_PPP5C':True,'other_targets':6085,'upward_crossers':495,'all_points_drawn':True,'histogram_bins':bins.tolist(),'histogram_totals':[int(hx.sum()),int(hy.sum())],'highlighted_histogram_totals':[int(hcx.sum()),int(hcy.sum())],'example':'ENSG00000018625','example_coordinates':[ex,ey],'marginals':'exact frequency counts, no KDE or fitted distribution'}})

(OUT/'FIG4_5_QA.json').write_text(json.dumps(QA,indent=2),encoding='utf-8')
(OUT/'FIG4_5_SOURCE_CROSSWALK.json').write_text(json.dumps(CROSSWALK,indent=2),encoding='utf-8')
print('Rendered native Figure 4 and 5:',OUT)
