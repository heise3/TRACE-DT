# Asset confirmation: copied the verified R32 production renderer before reconstruction.
# Scanned BarComposition, BarAblation, LineTrend and MarginalDensity asset directories.
# Generic performance/CI/density templates are not applicable to sharp-bound summaries.
# Native primitives and all source-table rows are retained; no downsampling or new inference.
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
from matplotlib.patches import Rectangle, FancyBboxPatch
from matplotlib.transforms import Bbox
from matplotlib.text import Text
from pathlib import Path
import argparse, hashlib, json
from datetime import datetime,timezone
import pandas as pd
import numpy as np

# Task-specific semantic palette; baseline above is intentionally left verbatim.
BLUE='#355C7D'; TEAL='#007F75'; GOLD='#9B6E22'; PURPLE='#80658A'
GRAY='#8A9198'; PALE='#F3F5F6'; EDGE='#D7DDE1'; INK='#20262C'
mpl.rcParams.update({'text.color':INK,'axes.labelcolor':INK,'xtick.color':INK,
                     'ytick.color':INK,'axes.edgecolor':INK,'mathtext.fontset':'custom',
                     'mathtext.rm':'Arial','mathtext.it':'Arial:italic','mathtext.bf':'Arial:bold',
                     'svg.hashsalt':'TRACE-DT-R33'})
H=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--data',type=Path,default=H/'source_data')
parser.add_argument('--output',type=Path,default=H/'rendered_figures')
opt=parser.parse_args(); S=opt.data; OUT=opt.output; OUT.mkdir(parents=True,exist_ok=True)
receipts=[]; qa=[]
def read(name): return pd.read_csv(S/name,sep='\t')
case_id=json.loads((S/'FOCUSED_ANALYSIS_RECEIPT.json').read_text(encoding='utf-8'))['selected_target']
records=read('Table_S36_Grouping_Example_Records.tsv')
ops=read('Table_S37_Grouping_Example_Operators.tsv')
def fig(h): return plt.figure(figsize=(170/25.4,h/25.4),facecolor='white')
def panel(f,rect,letter,label):
    ax=f.add_axes(rect); x,y,w,h=rect
    f.text(x-.026,y+h+.024,letter,fontsize=10,fontweight='bold',va='bottom')
    f.text(x,y+h+.024,label,fontsize=8.5,fontweight='bold',va='bottom')
    return ax
def off(ax): ax.set_axis_off(); ax.set_xlim(0,1); ax.set_ylim(0,1)
def box(ax,x,y,w,h,text='',color=BLUE,fill='white',size=7,bold=False):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.004,rounding_size=0.014',
                              edgecolor=color,facecolor=fill,linewidth=.7))
    if text: ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=size,
                     fontweight='bold' if bold else 'normal',linespacing=1.25)
def arrow(ax,start,end,color=GRAY):
    ax.annotate('',xy=end,xytext=start,arrowprops={'arrowstyle':'-|>','lw':.8,'color':color,'mutation_scale':7})
def ranges(ax,d,y,lo,hi,center,color=BLUE,marker='o',scale=100):
    for j,(_,r) in enumerate(d.iterrows()):
        yy=y[j]; ax.hlines(yy,scale*r[lo],scale*r[hi],color=color,lw=1.4)
        ax.scatter(scale*r[center],yy,s=23,marker=marker,color=color,zorder=3)
def save(f,num,sources,panels):
    # Remove locator ticks outside the declared limits (Matplotlib does not draw them).
    for ax in f.axes:
        if not ax.axison: continue
        xlo,xhi=sorted(ax.get_xlim());ylo,yhi=sorted(ax.get_ylim())
        ax.set_xticks([v for v in ax.get_xticks() if xlo<=v<=xhi])
        ax.set_yticks([v for v in ax.get_yticks() if ylo<=v<=yhi])
    f.canvas.draw(); renderer=f.canvas.get_renderer(); bounds=f.bbox
    bad=[]; sizes=[]
    for t in f.findobj(Text):
        if not t.get_visible() or not t.get_text().strip(): continue
        sizes.append(t.get_fontsize()); b=t.get_window_extent(renderer)
        if b.x0<bounds.x0-1 or b.y0<bounds.y0-1 or b.x1>bounds.x1+1 or b.y1>bounds.y1+1:
            bad.append({'text':t.get_text(),'bounds':list(b.bounds)})
    assert min(sizes)>=6.5,(num,min(sizes))
    assert not bad,(num,bad)
    # Explicit fixed canvas overrides the baseline's tight cropping without changing final size.
    canvas=Bbox.from_bounds(0,0,*f.get_size_inches())
    stamp=datetime(2026,10,10,tzinfo=timezone.utc)
    for ext in ['pdf','svg','png']:
        metadata={'CreationDate':stamp,'ModDate':stamp,'Creator':'TRACE-DT R33 native figure renderer'} if ext=='pdf' else (
                 {'Date':'2026-10-10','Creator':'TRACE-DT R33 native figure renderer'} if ext=='svg' else {'Software':'TRACE-DT R33 native figure renderer'})
        f.savefig(OUT/f'Figure_{num}.{ext}',bbox_inches=canvas,dpi=300,metadata=metadata)
    source_hashes={name:hashlib.sha256((S/name).read_bytes()).hexdigest() for name in sources}
    receipts.append({'figure':str(num),'width_mm':170,'height_mm':f.get_figheight()*25.4,
                     'sources_sha256':source_hashes,'panels':panels,
                     'statistics':'finite-universe descriptive; exact bounds/enumeration, no CI or tests'})
    qa.append({'figure':str(num),'minimum_font_pt':min(sizes),'text_outside_canvas':bad,
               'data_downsampled':False,'statistics_inferred':False})
    plt.close(f)

# Figure 1: workflow first; actual and synthetic objects explicitly separated.
f=fig(134); ax=panel(f,[.04,.64,.92,.27],'a','From fixed evidence to capacity-limited identities');off(ax)
steps=[('Fixed evidence','Rows + provenance'),('Declared processing','O1 collapse · O2 group\nO3 score scale'),
       ('Score construction','O4 within group\nO5 across groups'),('Top-B boundary','Strictly above + tie\nB seats, not one order'),
       ('TRACE-DT output','Necessary · possible\nID realization')]
for j,(head,sub) in enumerate(steps):
    x=.005+j*.203;box(ax,x,.40,.18,.51,color=EDGE,fill=PALE)
    ax.text(x+.09,.77,head,ha='center',fontsize=7.2,fontweight='bold')
    ax.text(x+.09,.58,sub,ha='center',va='center',fontsize=6.7,linespacing=1.4)
    if j<4:arrow(ax,(x+.185,.65),(x+.202,.65),BLUE)
ax.text(.015,.18,'Five declared binary choices',fontsize=7,color=BLUE)
ax.text(.455,.18,'32 specifications',fontsize=8,fontweight='bold',ha='center')
ax.text(.985,.18,'Report identities + exact bounds',fontsize=7,ha='right')
ax=panel(f,[.04,.33,.43,.23],'b','Observed colorectal comparison');off(ax)
observed=read('Figure_1_A_deterministic_global_mean_matched_example.tsv').iloc[0]
assert int(observed.intersection_deterministic)==28
shared=int(observed.intersection_deterministic);replaced=50-shared
ax.text(.0,.90,'B = 50; same retained evidence',fontsize=7)
for j,code in enumerate([observed.operator_code_a,observed.operator_code_b]):
    yy=.58-j*.27; ax.text(.0,yy+.06,str(int(code)).zfill(5),va='center',fontsize=7)
    ax.add_patch(Rectangle((.23,yy),.74*shared/50,.13,facecolor=BLUE))
    ax.add_patch(Rectangle((.23+.74*shared/50,yy),.74*replaced/50,.13,facecolor=GOLD if j==0 else PURPLE))
ax.text(.23,.05,f'{shared} shared  /  {replaced} replaced',fontsize=7,fontweight='bold')
ax=panel(f,[.55,.33,.41,.23],'c','Synthetic membership at B = 2');off(ax)
ax.text(.0,.92,'H = {a}; T = {b,c,d}; one tie seat',fontsize=7)
for i,(label,sel,col,mark,hollow) in enumerate([('Necessary',{'a'},TEAL,'o',False),('Possible',set('abcd'),GOLD,'D',True),('ID realized',{'a','b'},BLUE,'s',False)]):
    yy=.68-i*.27; ax.text(.0,yy,label,fontsize=7,va='center')
    for j,name in enumerate('abcd'):
        active=name in sel;xx=.43+j*.17
        ax.scatter(xx,yy,s=122,marker=mark,facecolors=('white' if hollow else col) if active else PALE,
                   edgecolors=col if active else EDGE,linewidth=.9,zorder=3)
        ax.text(xx,yy,name,ha='center',va='center',fontsize=6.7,color=INK if hollow or not active else 'white')
ax=panel(f,[.04,.035,.92,.205],'d','Global comparison summary');off(ax)
global_row=read('Figure_1_C_global_tie_bounds.tsv').iloc[0]
vals=100*np.array([global_row.mean_lower_bound_global_F,global_row.deterministic_global_F,global_row.mean_upper_bound_global_F])
xx=.16+.62*(vals-vals[0])/(vals[-1]-vals[0]);ax.plot([xx[0],xx[2]],[.56,.56],color=EDGE,lw=3,zorder=1)
for x,v,lab,col,mark in zip(xx,vals,['Lower-bound mean','ID mean','Upper-bound mean'],[TEAL,BLUE,GOLD],['o','s','D']):
    ax.scatter(x,.56,s=33,c=col,marker=mark,zorder=3)
    ax.text(x,.88,f'{v:.1f}%',ha='center',fontsize=12,fontweight='bold',color=col)
    ax.text(x,.28,lab,ha='center',fontsize=7)
ax.text(.50,.0,f'{int(global_row.within_context_pairs):,} pairwise comparisons · exact-bound means, not CI',ha='center',fontsize=6.8)
save(f,1,['Figure_1_A_deterministic_global_mean_matched_example.tsv','Figure_1_C_global_tie_bounds.tsv'],
     {'a':{'kind':'schematic','specifications':32},'b':{'observed_pairs':1,'B':50,'shared':shared,'replaced':replaced},
      'c':{'kind':'synthetic','B':2},'d':{'comparisons':11408,'values_percent':vals.tolist(),'uncertainty':'pairwise sharp-bound means'}})

# Figure 2: discrete mechanism and empirically distinct attribution families.
f=fig(112);ax=panel(f,[.10,.23,.24,.64],'a','Normalizer reversal')
hh=sum(i**-2 for i in range(1,1001));aa=[1,1/hh];bb=[.96,1.2/hh]
ax.plot([0,1],aa,'-o',color=BLUE,lw=1.2,ms=4,label='A = [1]')
ax.plot([0,1],bb,'--s',color=GOLD,lw=1.2,ms=4,label='B = [1, 0.8]')
ax.set(xticks=[0,1],xticklabels=['Finite\nlength','Fixed\nh1000'],xlim=(-.17,1.17),ylim=(.55,1.06),ylabel='Illustrative unweighted score')
ax.legend(loc='lower left',fontsize=7,bbox_to_anchor=(0,.15))
ax.text(0,-.23,'Two synthetic vectors;\nnot a platform replay',transform=ax.transAxes,fontsize=7,va='top')
ax=panel(f,[.64,.23,.32,.64],'b','Two B01 contrast families')
b=read('R17_B01_COMPONENT_ABLATION_SUMMARY.tsv'); order=[0,3,4,1,2]; ys=[0,1,2,4,5]
labels=['Equal weights','Upper arithmetic','Upper finite norm.','Rebuilt: within finite','Rebuilt: within max.']
for j,y in zip(order,ys):
    r=b.iloc[j];col=BLUE if y<3 else PURPLE;mark='o' if y<3 else 's'
    ax.hlines(y,100*r.mean_substitution_lower_bound,100*r.mean_substitution_upper_bound,color=col,lw=1.5)
    ax.scatter(100*r.mean_substitution_deterministic,y,c=col,marker=mark,s=26,zorder=3)
    ax.text(100*r.mean_substitution_upper_bound+2,y,f'{100*r.mean_substitution_deterministic:.1f}%',va='center',fontsize=7,color=col)
ax.axhline(3,color=EDGE,lw=.7)
ax.set(yticks=ys,yticklabels=labels,xlim=(0,62),ylim=(6.05,-1.15),xlabel='Substitution against B01 (%)')
ax.tick_params(axis='y',length=0,pad=7)
ax.text(.0,.99,'Released datasource scores fixed',transform=ax.transAxes,va='top',fontsize=7,color=BLUE)
ax.text(.0,.435,'Datasource scores reconstructed',transform=ax.transAxes,fontsize=7,color=PURPLE)
ax.text(.0,-.23,'23 contexts · exact-bound means\nNon-additive contrasts; not CI',transform=ax.transAxes,fontsize=7,va='top')
save(f,2,['R17_B01_COMPONENT_ABLATION_SUMMARY.tsv'],{'a':{'kind':'synthetic','conditions':2,'A':aa,'B':bb},
     'b':{'contrasts':5,'contexts':23,'families':[3,2],'values_percent':b.mean_substitution_deterministic.mul(100).tolist()}})

# Figure 3: equal upper axes and a full-width, real retained-record flow.
f=fig(153);a=read('Figure_3_A_factor_effects.tsv');ax=panel(f,[.12,.67,.31,.245],'a','Direct factor toggles')
ranges(ax,a,list(range(len(a))),'substitution_lower_bound_mean','substitution_upper_bound_mean','substitution_deterministic_mean')
ax.set(yticks=range(len(a)),yticklabels=a.direct_toggle_factor,xlim=(-3,85),ylim=(4.65,-.65),xlabel='Substitution (%)',xticks=[0,20,40,60,80])
d=read('Figure_3_BC_O2_conditioned.tsv');d=d[d.direct_toggle_factor.isin(['O4','O5'])].sort_values(['direct_toggle_factor','O2_stratum'])
ax=panel(f,[.66,.67,.30,.245],'b','Aggregation × grouping')
for i,(_,r) in enumerate(d.iterrows()):
    col=BLUE if r.O2_stratum==0 else PURPLE;mark='o' if r.O2_stratum==0 else 's'
    ax.hlines(i,100*r.substitution_lower_bound_mean,100*r.substitution_upper_bound_mean,color=col,lw=1.4)
    ax.scatter(100*r.substitution_deterministic_mean,i,c=col,marker=mark,s=23,zorder=3)
ax.set(yticks=range(4),yticklabels=['O4 / source','O4 / lineage','O5 / source','O5 / lineage'],xlim=(-3,85),ylim=(3.6,-.6),xlabel='Substitution (%)',xticks=[0,20,40,60,80])
f.text(.12,.595,'Points: ID means; lines: exact-bound means (not CI)',fontsize=7)
ax=panel(f,[.04,.075,.92,.43],'c','Same records; different aggregation stage');off(ax)
raw=records[records.targetId==case_id].score.sort_values(ascending=False).tolist();assert len(raw)==2
def score(grouping,within,across):
    r=ops[(ops.targetId==case_id)&(ops.grouping==grouping)&(ops.within==within)&(ops.across==across)]
    assert len(r)==1;return float(r.iloc[0].recomputed_score)
mx=score('datasource','maximum','arithmetic');fi=score('datasource','finite_harmonic','arithmetic')
ma=score('lineage','maximum','arithmetic');lf=score('lineage','maximum','finite_harmonic')
ax.text(.0,.94,f'{case_id} · urinary bladder cancer',fontsize=7.5,fontweight='bold')
ax.text(.0,.84,f'Two EuropePMC rows: {raw[0]:.2f} and {raw[1]:.2f} · O1 = O3 = 0',fontsize=7)
ax.text(.0,.60,'Source',fontsize=7.5,color=BLUE,fontweight='bold',va='center')
box(ax,.17,.50,.19,.22,f'One group\n[{raw[0]:.2f}, {raw[1]:.2f}]',BLUE,PALE)
arrow(ax,(.37,.61),(.43,.61),BLUE)
box(ax,.44,.50,.28,.22,f'Within max  {mx:.3f}\nWithin finite  {fi:.3f}',BLUE)
arrow(ax,(.73,.61),(.79,.61),BLUE)
ax.text(.81,.61,'One group:\nacross unchanged',fontsize=7,va='center')
ax.text(.0,.29,'Lineage',fontsize=7.5,color=PURPLE,fontweight='bold',va='center')
box(ax,.17,.17,.09,.22,f'{raw[0]:.2f}',PURPLE,PALE)
box(ax,.28,.17,.09,.22,f'{raw[1]:.2f}',PURPLE,PALE)
arrow(ax,(.38,.28),(.43,.28),PURPLE)
box(ax,.44,.17,.28,.22,'Two singleton groups\nwithin unchanged',PURPLE)
arrow(ax,(.73,.28),(.79,.28),PURPLE)
ax.text(.81,.28,f'Across mean  {ma:.3f}\nAcross finite  {lf:.3f}',fontsize=7,va='center',fontweight='bold')
geometry=read('Figure_3_D_group_geometry.tsv');geometry=geometry[(geometry.stratum=='all_hard_negative')&(geometry.row_collapse=='canonical-unit')]
gsource=geometry[geometry.grouping=='datasource'].iloc[0];glin=geometry[geometry.grouping=='provenance'].iloc[0]
assert gsource.target_context_pairs==glin.target_context_pairs==107497
f.text(.04,.034,f'All groups singleton: source {100*gsource.fraction_pairs_with_all_groups_singleton:.1f}% / lineage {100*glin.fraction_pairs_with_all_groups_singleton:.1f}% (n = 107,497 pairs)',fontsize=6.8)
control=ops[ops.targetId=='ENSG00000011485'].recomputed_score;assert np.ptp(control)<1e-15
f.text(.04,.014,f'Control: PPP5C, one row → {control.iloc[0]:.3f} in all 8 variants. Full keys/scores: Tables S36–S37.',fontsize=6.8)
save(f,3,['Figure_3_A_factor_effects.tsv','Figure_3_BC_O2_conditioned.tsv','Figure_3_D_group_geometry.tsv','Table_S36_Grouping_Example_Records.tsv','Table_S37_Grouping_Example_Operators.tsv'],
     {'a':{'rows':len(a)},'b':{'rows':len(d),'x_scale_same_as_a':True},'c':{'observed_rows':2,'example_scores':[mx,fi,ma,lf],
     'singleton_denominator':107497,'singleton_fractions':[float(gsource.fraction_pairs_with_all_groups_singleton),float(glin.fraction_pairs_with_all_groups_singleton)],'control_variants':8}})

# Figure 4: preserve successful chart hierarchy, clarify mutually exclusive cohort labels.
f=fig(174);ax=panel(f,[.12,.715,.33,.205],'a','Selection-frequency frontier');front=read('Figure_4_A_frequency_frontier.tsv');xx=front.iloc[:,0]
for key,col,ls,marker,label in [('possible',GOLD,':','D','Possible'),('deterministic',BLUE,'--','s','ID realized'),('necessary',TEAL,'-','o','Necessary')]:
    ax.plot(xx,front[next(v for v in front.columns if key in v)],color=col,ls=ls,lw=1.3,marker=marker,markevery=[0,7,15,23,31],ms=3,label=label)
ax.set(yscale='log',xlabel='Minimum selected specifications',ylabel='Target–context pairs',xticks=[1,8,16,24,32])
ax.legend(fontsize=6.8,loc='upper right')
ax=panel(f,[.74,.715,.22,.205],'b','Retained-row structure');coh=read('Table_S18_Cohort_Summary.tsv').set_index('cohort')
cohort_names=['necessary_32','deterministic_32_not_necessary','possible_32_not_deterministic'];counts=[]
for i,(name,col) in enumerate(zip(cohort_names,[TEAL,BLUE,GOLD])):
    r=coh.loc[name];value=100*r.retained_row_singleton_fraction;counts.append([int(r.retained_row_singleton_n),int(r.n)])
    ax.barh(i,value,color=col,height=.53)
    ax.text(4,i,f'{int(r.retained_row_singleton_n)}/{int(r.n)}',va='center',fontsize=7,color='white')
ax.set(yticks=range(3),yticklabels=['Necessary\nall 32','ID-only\nall 32','Possible-only\nall 32'],xlim=(0,100),ylim=(2.65,-.65),xlabel='One positive row (%)',xticks=[0,50,100])
ax.tick_params(axis='y',length=0,pad=6)
context=read('Figure_4_B_context_32of32.tsv').sort_values('context_name').reset_index(drop=True)
ax=panel(f,[.44,.085,.52,.52],'c','All-32 memberships across 23 contexts')
for i,r in context.iterrows():
    ax.hlines(i,r.necessary_32,r.possible_32,color=EDGE,lw=1.25)
    ax.scatter(r.necessary_32,i-.16,c=TEAL,s=19,marker='o',zorder=4)
    ax.scatter(r.deterministic_32,i,c=BLUE,s=20,marker='s',zorder=4)
    ax.scatter(r.possible_32,i+.16,facecolors='white',edgecolors=GOLD,s=27,marker='D',lw=.9,zorder=5)
ax.set(yticks=range(len(context)),yticklabels=context.context_name,xlabel='Target–context pairs',ylim=(len(context)-.4,-.7))
ax.tick_params(axis='y',labelsize=6.7,length=0,pad=6)
for col,marker,label in [(TEAL,'o','Necessary'),(BLUE,'s','ID realized'),(GOLD,'D','Possible')]:
    ax.scatter([],[],facecolors='white' if label=='Possible' else col,edgecolors=col,marker=marker,label=label,s=22)
ax.legend(loc='lower right',fontsize=7)
f.text(.44,.024,'Grey connectors: state ranges, not CI. Vertical offsets are display-only.',fontsize=6.8)
save(f,4,['Figure_4_A_frequency_frontier.tsv','Figure_4_B_context_32of32.tsv','Table_S18_Cohort_Summary.tsv'],
     {'a':{'thresholds':len(front),'curves':3},'b':{'cohorts':3,'singleton_counts':counts},'c':{'contexts':len(context),'states_per_context':3,'sort':'context_name ascending'}})

# Figure 5: smaller case cards; full, undownsampled competition dominates.
f=fig(138);ax=panel(f,[.04,.765,.92,.17],'a','Four fixed numerical cases');off(ax)
cases=read('R26_DETERMINISTIC_MAIN_CASES.tsv').sort_values('case_order');chain=read('Table_S21_Case_Record_Chain.tsv')
case_specs=[('C19orf33','Ovarian',TEAL,'Necessary','necessary_selection_count'),('PAGE4','Hepatocellular',BLUE,'Selected','deterministic_selection_count'),('PPP5C','Bladder',BLUE,'Selected','deterministic_selection_count'),('FGFR2','Colorectal',GRAY,'Rule-blocked','primary_eligibility_blocked_count')]
for j,((gene,ctx,col,lab,field),(_,r)) in enumerate(zip(case_specs,cases.iterrows())):
    x=.005+j*.25;box(ax,x,.03,.235,.90,color=EDGE)
    ax.plot([x+.005,x+.23],[.90,.90],color=col,lw=2)
    subset=chain[chain.targetId==r.targetId];assert len(subset)>0
    ax.text(x+.013,.75,gene,fontsize=8,fontweight='bold')
    ax.text(x+.013,.56,ctx,fontsize=6.7)
    ax.text(x+.013,.34,f'{lab} {int(r[field])}/32',fontsize=7,color='#616B73' if gene=='FGFR2' else col,fontweight='bold')
    source='Atlas' if gene=='PAGE4' else ('5 sources' if gene=='FGFR2' else 'EuropePMC')
    ax.text(x+.013,.12,f'{len(subset)} row'+('s' if len(subset)!=1 else '')+' / '+source,fontsize=6.6)
cut=read('Table_S25_PPP5C_Cutoff_Comparison.tsv');ax=panel(f,[.10,.195,.28,.475],'b','Own score fixed; cutoff moves')
ax.plot([0,1],cut.PPP5C_score,'-o',color=BLUE,lw=1.4,ms=4,label='PPP5C')
ax.plot([0,1],cut.cutoff_score,'--s',color=GOLD,lw=1.4,ms=4,label='50th score')
for i,r in cut.iterrows():
    ax.annotate(f'Rank {int(r.PPP5C_rank)}',(i,r.PPP5C_score),xytext=(0,10),textcoords='offset points',ha='center',fontsize=7,color=BLUE)
    ax.annotate(f'{r.cutoff_score:.4f}',(i,r.cutoff_score),xytext=(0,9),textcoords='offset points',ha='center',fontsize=7,color=GOLD)
ax.set(xticks=[0,1],xticklabels=['01000','01001'],xlim=(-.19,1.19),ylim=(.43,1.01),ylabel='Score',xlabel='Specification')
ax.legend(loc='upper left',fontsize=7)
competitors=read('Table_S26_PPP5C_All_Competitors.tsv');cross=competitors[competitors.crossed_PPP5C_upward]
assert len(competitors)==6086 and len(cross)==495
assert sum(competitors.targetId=='ENSG00000011485')==1
ax=panel(f,[.55,.17,.42,.50],'c','Competitive displacement')
ax.add_patch(Rectangle((0,.59),.59,.43,facecolor=GOLD,alpha=.055,edgecolor='none',zorder=0))
ax.plot([0,1],[0,1],ls='--',lw=.65,color=GRAY,zorder=1)
ax.scatter(competitors.operator_score_O5_0,competitors.operator_score_O5_1,c=GRAY,s=4.1,alpha=.38,lw=0,zorder=2)
ax.scatter(cross.operator_score_O5_0,cross.operator_score_O5_1,c=GOLD,s=6,alpha=.80,lw=0,zorder=3)
ax.axhline(.59,color=BLUE,lw=.75);ax.axvline(.59,color=BLUE,lw=.75)
ax.scatter([.59],[.59],c=BLUE,s=44,marker='*',zorder=5)
example=competitors[competitors.targetId==case_id].iloc[0]
ax.scatter([example.operator_score_O5_0],[example.operator_score_O5_1],facecolors='none',edgecolors=PURPLE,s=64,lw=1.25,zorder=6)
ax.annotate('Two-row case\nFig. 3c',xy=(example.operator_score_O5_0,example.operator_score_O5_1),xytext=(.72,.85),
            fontsize=6.8,ha='left',color=PURPLE,arrowprops={'arrowstyle':'-','color':PURPLE,'lw':.7})
ax.text(.98,.055,'6,086 scored targets\n495 cross PPP5C upward',transform=ax.transAxes,ha='right',fontsize=7)
ax.set(xlim=(-.015,1.02),ylim=(-.015,1.02),xlabel='Score under 01000',ylabel='Score under 01001',aspect='equal',xticks=[0,.2,.4,.6,.8,1],yticks=[0,.2,.4,.6,.8,1])
f.text(.04,.035,'PPP5C = 0.590 in both specifications. Gold region: score crosses from ≤0.590 to >0.590.',fontsize=6.8)
f.text(.04,.015,'Same frozen scored pool; all points shown. Cases illustrate computation, not therapeutic validity.',fontsize=6.8)
save(f,5,['R26_DETERMINISTIC_MAIN_CASES.tsv','Table_S21_Case_Record_Chain.tsv','Table_S25_PPP5C_Cutoff_Comparison.tsv','Table_S26_PPP5C_All_Competitors.tsv','Table_S36_Grouping_Example_Records.tsv'],
     {'a':{'cases':4,'retained_rows':[1,1,1,12]},'b':{'specifications':2,'target_scores':cut.PPP5C_score.tolist(),'ranks':cut.PPP5C_rank.tolist(),'cutoffs':cut.cutoff_score.tolist()},
      'c':{'points_total':len(competitors),'includes_PPP5C':True,'other_targets':len(competitors)-1,'highlighted_upward_crossers':len(cross),'example':case_id,'example_coordinates':[float(example.operator_score_O5_0),float(example.operator_score_O5_1)]}})

# Figure 6: concrete ranking ribbons precede finite fixtures and external portability.
f=fig(143);ax=panel(f,[.04,.655,.92,.29],'a','Same selected set; different rank-weighted agreement');off(ax)
concrete=read('Table_S38_Concrete_Rank_Objective_Comparison.tsv')
objcols={'a':BLUE,'b':TEAL,'c':GOLD,'d':PURPLE}
chosen=[]
for j,example_name in enumerate(['min_Q','max_Q']):
    row=concrete[(concrete.fixture=='unique_boundary_fits')&(concrete.example==example_name)].iloc[0];chosen.append(row)
    x=.01+j*.51;ax.text(x,.93,'Different orders' if j==0 else 'Identical orders',fontsize=7.5,fontweight='bold')
    for k,(lab,order) in enumerate([('A',row.order_a.split(',')),('B',row.order_b.split(','))]):
        yy=.60-k*.28;ax.text(x,yy+.055,lab,fontsize=7,va='center')
        for q,name in enumerate(order):
            px=x+.047+q*.072;box(ax,px,yy,.055,.12,name,objcols[name],objcols[name],size=7,bold=True)
            ax.texts[-1].set_color('white')
        # Complete tie blocks, with capacity cut separating the two blocks.
        for bx in [x+.04,x+.184]:
            ax.add_patch(Rectangle((bx,yy-.028),.137,.178,fill=False,edgecolor=EDGE,lw=.7))
        ax.plot([x+.18,x+.18],[yy-.045,yy+.18],color=INK,ls='--',lw=.8)
    ax.text(x+.047,.16,'Selected {a,b} · F(B) = 0',fontsize=7)
    ax.text(x+.047,.025,f'$Q_D$ = {row.finite_depth_RBO:.4f}',fontsize=8,fontweight='bold',color=BLUE)
f.text(.04,.610,'B = 2 · D = 4 · p = 0.9 · boxes delimit tie blocks; dashed cut = B',fontsize=7)
fixture=read('Table_S31_Tie_Method_Fixture_Comparison.tsv');ax=panel(f,[.20,.16,.205,.34],'b','Finite-depth $Q_D$')
for i,r in fixture.iterrows():
    ax.hlines(i,r.finite_depth_RBO_min,r.finite_depth_RBO_max,color=PURPLE,lw=1.5)
    ax.scatter(r.finite_depth_RBO_mean,i,color=PURPLE,s=23,marker='s',zorder=3)
ax.set(yticks=range(4),yticklabels=['Asymmetric\n288 pairs','Fully tied\n576 pairs','Boundary fits\n16 pairs','Untied\n1 pair'],xlim=(.25,1.04),ylim=(3.7,-.65),xlabel='Normalized $Q_D$',xticks=[.3,.5,.7,.9])
ax.tick_params(axis='y',length=0,pad=6)
ax.text(-.73,-.30,'Exhaustive extrema; square = mean.\nNot full extrapolated RBO.',transform=ax.transAxes,fontsize=6.8,va='top')
external=read('DISEASES_pairwise_audit.tsv');external['category']=external.specification_a+' / '+external.specification_b
cats=sorted(external.category.unique());ax=panel(f,[.70,.16,.26,.34],'c','DISEASES portability')
labelmap={'EXPERIMENTS':'Experimental','INTEGRATED':'Integrated','TEXTMINING':'Text-mining'};cat_counts=[]
for i,cat in enumerate(cats):
    group=external[external.category==cat].sort_values(['substitution_deterministic','context_id']);yy=i+np.linspace(-.30,.30,len(group));cat_counts.append(len(group))
    col=[BLUE,PURPLE,TEAL][i];mark=['o','s','D'][i]
    ax.hlines(yy,group.substitution_lower_bound,group.substitution_upper_bound,color=col,lw=.8,alpha=.72)
    ax.scatter(group.substitution_deterministic,yy,c=col,s=12,marker=mark,zorder=3)
labels=[f'{labelmap[c.split(" / ")[0]]} /\n{labelmap[c.split(" / ")[1]]} (n={sum(external.category==c)})' for c in cats]
ax.set(yticks=range(3),yticklabels=labels,xlim=(-.03,1.03),ylim=(2.6,-.6),xlabel='Top-50 substitution',xticks=[0,.5,1])
ax.tick_params(axis='y',length=0,pad=5,labelsize=6.7)
ax.text(-.48,-.30,'All 50 comparisons shown.\nPoints: ID; lines: exact bounds.',transform=ax.transAxes,fontsize=6.8,va='top')
assert cat_counts==[26,4,20]
save(f,6,['Table_S31_Tie_Method_Fixture_Comparison.tsv','Table_S38_Concrete_Rank_Objective_Comparison.tsv','DISEASES_pairwise_audit.tsv'],
     {'a':{'kind':'fixture','B':2,'D':4,'p':.9,'Q_D':[float(r.finite_depth_RBO) for r in chosen]},
      'b':{'fixtures':4,'ranking_pairs':fixture.ranking_pairs.tolist(),'center':'exhaustive mean','range':'exhaustive min/max'},
      'c':{'comparisons':len(external),'category_counts':cat_counts,'sort':'category, substitution_deterministic, context_id'}})

# S2: matching palette only, unchanged B01 numbers and contrast attribution.
f=fig(112);ax=panel(f,[.28,.23,.28,.64],'a','B01 contrasts');ys=[0,1,2,4,5]
for j,y in zip([0,3,4,1,2],ys):
    r=b.iloc[j];col=BLUE if y<3 else PURPLE
    ax.hlines(y,r.mean_substitution_lower_bound,r.mean_substitution_upper_bound,color=col,lw=1.4)
    ax.scatter(r.mean_substitution_deterministic,y,c=col,marker='o',s=24,zorder=3)
    ax.scatter(r.mean_substitution_expected_uniform_tie,y,facecolors='white',edgecolors=col,marker='s',s=22,zorder=3)
ax.axhline(3,color=EDGE,lw=.7);ax.set(yticks=ys,yticklabels=['Equal weights','Upper arithmetic','Upper finite','Rebuilt: within finite','Rebuilt: within max'],xlim=(.18,.49),ylim=(5.9,-.7),xlabel='Substitution against B01')
ax.scatter([],[],c=BLUE,label='ID realization',s=24);ax.scatter([],[],facecolors='white',edgecolors=BLUE,marker='s',label='IP expectation',s=22);ax.legend(fontsize=6.8,loc='lower right')
ax=panel(f,[.73,.23,.23,.64],'b','Original K contrasts')
shortlabels=['Equal weights','Within finite','Within max','Upper arithmetic','Upper finite']
for i,row in b.iterrows():
    col=BLUE if i in [0,3,4] else PURPLE
    ax.scatter(row.mean_substitution_deterministic,row.mean_chance_adjusted_stability_deterministic,color=col,marker=['o','^','v','s','D'][i],s=30,label=shortlabels[i])
ax.set(xlim=(.19,.47),ylim=(.53,.81),xlabel='ID substitution',ylabel='Chance-adjusted stability, K');ax.legend(fontsize=6.5,loc='upper right')
f.text(.04,.055,'Blue: released scores fixed. Purple: retained-record reconstruction substitutes.',fontsize=7)
f.text(.04,.028,'Original exact-bound means / IP expectations; not CI or biological accuracy.',fontsize=7)
save(f,'S2',['R17_B01_COMPONENT_ABLATION_SUMMARY.tsv'],{'a':{'contrasts':5,'contexts':23,'IP_expectations_shown':True},'b':{'points':5,'K_unchanged':True}})
(OUT/'FIGURE_SOURCE_CROSSWALK.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
(OUT/'FIGURE_RENDER_QA.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')
print('Rendered six main figures and S2:',OUT)
