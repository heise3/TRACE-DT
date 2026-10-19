# Academic Figure Skill Asset Confirmation (verified against assets/figures/)
# Fig2(a) mechanism + connected scores -> LineTrend/plot_posttraining.py -> param inherit
# Fig2(b) distinct contrast families + sharp bounds -> BarAblation/plot_bar_ablation.py -> param inherit
# Fig3(a,b) exact-bound table-forest -> cross-type inherit BarAblation -> param inherit
# Fig3(c) observed operational partition + full operator-score matrix -> cross-type inherit -> param inherit
# RULE: "native run" = load pre-rendered PNG via Image.open().ax.imshow().
#       "param inherit" = drawing function below that copies Class A/B/C values.
#       If a panel says "native run" and you write a drawing function, you broke the contract.
# Candidate templates contain performance time courses or single Spearman scores;
# they cannot truthfully express a finite synthetic reversal or exact-bound means.
# Parameter inheritance keeps direct labels, flat native marks, shared scales and
# clean spines; no performance values, inferred CI, baseline reductions or density.
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
from matplotlib.patches import Rectangle, FancyBboxPatch, Circle
from matplotlib.text import Text
from matplotlib.transforms import Bbox
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json
import pandas as pd
import numpy as np

# Semantics override only after all three unchanged baseline blocks.
INK = '#20262C'; BLUE = '#355C7D'; TEAL = '#007F75'; GOLD = '#9B6E22'
PURPLE = '#80658A'; GRAY = '#616B73'; EDGE = '#D7DDE1'; PALE = '#F3F5F6'
SOURCE_FILL = '#EDF2F6'; LINEAGE_FILL = '#F3EEF5'
mpl.rcParams.update({'text.color':INK, 'axes.labelcolor':INK,
                     'xtick.color':INK, 'ytick.color':INK, 'axes.edgecolor':INK,
                     'svg.hashsalt':'TRACE-DT-R36-FIG2-3',
                     'mathtext.fontset':'custom','mathtext.rm':'Arial',
                     'mathtext.it':'Arial:italic','mathtext.bf':'Arial:bold'})
HERE=Path(__file__).resolve().parent
MIN_FONT=6.5
qa=[]
crosswalk=[]

def canvas(height):
    fig=plt.figure(figsize=(170/25.4,height/25.4),facecolor='white')
    ax=fig.add_axes([0,0,1,1]); ax.set(xlim=(0,170),ylim=(0,height)); ax.set_axis_off()
    return fig,ax

def txt(ax,x,y,text,size=7,color=INK,ha='left',va='center',bold=False,**kwargs):
    return ax.text(x,y,text,fontsize=size,color=color,ha=ha,va=va,
                   fontweight='bold' if bold else 'normal',linespacing=1.2,**kwargs)

def heading(ax,x,y,letter,title):
    txt(ax,x,y,letter,size=10,bold=True)
    txt(ax,x+7,y,title,size=8.5,bold=True)

def line(ax,x1,y1,x2,y2,color=EDGE,lw=.65,**kwargs):
    ax.plot([x1,x2],[y1,y2],color=color,lw=lw,**kwargs)

def arrow(ax,x1,y1,x2,y2,color=GRAY):
    ax.annotate('',xy=(x2,y2),xytext=(x1,y1),
                arrowprops={'arrowstyle':'-|>','lw':.9,'color':color,'mutation_scale':7})

def read(data,name):
    return pd.read_csv(data/name,sep='\t')

def save(fig,num,height,output,data,sources,panels):
    fig.canvas.draw(); renderer=fig.canvas.get_renderer(); bounds=fig.bbox
    bad=[]; sizes=[]
    for t in fig.findobj(Text):
        if not t.get_visible() or not t.get_text().strip(): continue
        sizes.append(t.get_fontsize()); b=t.get_window_extent(renderer)
        if b.x0<bounds.x0-.8 or b.y0<bounds.y0-.8 or b.x1>bounds.x1+.8 or b.y1>bounds.y1+.8:
            bad.append({'text':t.get_text(),'bbox_pixels':list(b.bounds)})
    assert min(sizes)>=MIN_FONT,(num,min(sizes))
    assert not bad,(num,bad)
    stamp=datetime(2026,10,10,tzinfo=timezone.utc)
    fixed_canvas=Bbox.from_bounds(0,0,*fig.get_size_inches())
    for ext in ['svg','pdf','png']:
        metadata={'CreationDate':stamp,'ModDate':stamp,'Creator':'TRACE-DT R36 native Matplotlib renderer'} if ext=='pdf' else (
                 {'Date':'2026-10-10','Creator':'TRACE-DT R36 native Matplotlib renderer'} if ext=='svg' else {'Software':'TRACE-DT R36 native Matplotlib renderer'})
        fig.savefig(output/f'Figure_{num}.{ext}',bbox_inches=fixed_canvas,dpi=300,metadata=metadata)
    hashes={name:hashlib.sha256((data/name).read_bytes()).hexdigest() for name in sources}
    crosswalk.append({'figure':str(num),'width_mm':170,'height_mm':height,'sources_sha256':hashes,
                      'panels':panels,'data_downsampled':False,'new_inference':False})
    qa.append({'figure':str(num),'minimum_font_pt':min(sizes),'text_outside_canvas':bad,
               'width_mm':170,'height_mm':height,'vector_master':True,
               'all_designated_panel_rows_used':True,'inferred_uncertainty':False,
               'four_pass_notes':{
                 'AP':'Verbatim baselines; custom semantic palette; native PDF/SVG; direct labels; no four-sided chart borders.',
                 'CL':'170 mm journal width, minimum font 6.5 pt, 300 dpi PNG, embedded TrueType font setting, .6 pt spines.',
                 'VI':'Every interval is a mean of exact pairwise sharp bounds; no CI or invented SD/SEM/p value; all designated panel rows used; source scope recorded.',
                 'VV':'Text canvas extents checked automatically; rendered figures require final human visual inspection.'}})
    plt.close(fig)

def figure2(data,output):
    height=155;fig,ax=canvas(height)
    heading(ax,6,148,'a','A change of normalizer reverses the order')
    txt(ax,13,139,'Two synthetic vectors',size=7,bold=True)
    txt(ax,13,134,'Not a platform replay',size=6.5,color=GRAY)
    for y,label,col,values in [(121,'A',BLUE,[1.0]),(106,'B',GOLD,[1.0,.8])]:
        txt(ax,8,y,label,size=8.5,color=col,bold=True)
        for j,value in enumerate(values):
            x=19+j*11
            ax.add_patch(Circle((x,y),4.1,facecolor='white',edgecolor=col,lw=1.1))
            txt(ax,x,y,f'{value:g}',size=7,ha='center',color=col,bold=True)
        txt(ax,13,y-7,f'n = {len(values)}',size=6.5,color=GRAY)
    line(ax,43,100,43,139)
    txt(ax,74,139,'Fixed numerators; alternative normalizers',size=7,ha='center',bold=True)
    txt(ax,56,128,'Numerator',size=6.5,ha='center',color=GRAY)
    txt(ax,78,128,'Finite h(n)',size=6.5,ha='center',color=GRAY)
    txt(ax,99,128,'Fixed h(1000)',size=6.5,ha='center',color=GRAY)
    for y,col,values in [(119,BLUE,['1.00','1.00','1.643935']),
                         (107,GOLD,['1.20','1.25','1.643935'])]:
        for x,value in zip([56,78,99],values):
            ax.add_patch(Rectangle((x-9,y-4.3),18,8.6,facecolor=SOURCE_FILL if col==BLUE else '#F6F0E5',edgecolor='none'))
            txt(ax,x,y,value,size=7,ha='center',color=col,bold=True)
    txt(ax,74,94,'h(n) = Σ 1/i² (i = 1...n);  score = numerator / h',size=6.5,ha='center',color=GRAY)
    # Direct labels replace a floating legend; markers redundantly encode A / B.
    score_ax=fig.add_axes([119/170,99/height,39/170,36/height])
    hh=sum(i**-2 for i in range(1,1001)); av=[1.0,1/hh];bv=[.96,1.2/hh]
    score_ax.plot([0,1],av,'-o',color=BLUE,lw=1.35,ms=4)
    score_ax.plot([0,1],bv,'--s',color=GOLD,lw=1.35,ms=4)
    score_ax.set(xlim=(-.18,1.20),ylim=(.55,1.06),xticks=[0,1],
                 xticklabels=['Finite','Fixed'],yticks=[.6,.8,1.0])
    score_ax.tick_params(labelsize=6.5,length=2.4)
    score_ax.spines['left'].set_color(EDGE);score_ax.spines['bottom'].set_color(EDGE)
    for x,y,text,col,off in [(0,av[0],'A  1.000',BLUE,7),(0,bv[0],'B  0.960',GOLD,-10),
                              (1,av[1],f'{av[1]:.3f}',BLUE,-10),(1,bv[1],f'{bv[1]:.3f}',GOLD,8)]:
        score_ax.annotate(text,(x,y),xytext=(0,off),textcoords='offset points',fontsize=6.5,ha='center',color=col)
    txt(ax,139,90,'A > B  →  A < B',size=7,ha='center',bold=True)
    line(ax,6,85,164,85,lw=.7)

    heading(ax,6,78,'b','B01 contrasts belong to two non-additive families')
    txt(ax,13,71,'23 contexts per contrast · points: ID means · rails: lower/upper-bound means · not CI',size=6.5,color=GRAY)
    table=read(data,'R17_B01_COMPONENT_ABLATION_SUMMARY.tsv')
    assert len(table)==5 and set(table.contexts)=={23}
    lookup=table.set_index('ablation_id')
    labels=[('ABL_WEIGHT_EQUAL_ONLY','Equal weights',63,BLUE,'o'),
            ('ABL_UPPER_ARITHMETIC_WEIGHTED_ONLY','Upper weighted arithmetic',53,BLUE,'o'),
            ('ABL_UPPER_NORMALIZER_OBSERVED_ONLY','Upper finite-length normalizer',43,BLUE,'o'),
            ('ABL_WITHIN_OBSERVED_HARMONIC_ONLY','Rebuilt: within finite-length',25,PURPLE,'s'),
            ('ABL_WITHIN_MAX_ONLY','Rebuilt: within maximum',15,PURPLE,'s')]
    # Both families use the same axis, but no connecting flow / stacked total.
    plot=fig.add_axes([75/170,12/height,73/170,53/height])
    plot.set(xlim=(0,50),ylim=(12,65),xticks=[0,10,20,30,40,50],yticks=[])
    plot.spines['left'].set_visible(False);plot.spines['bottom'].set_color(EDGE)
    plot.tick_params(axis='x',labelsize=6.5,length=2.5)
    plot.set_xlabel('Top-50 substitution against B01 (%)',fontsize=7,labelpad=2)
    for y in [43,53,63,15,25]:
        plot.hlines(y,0,50,color=EDGE,lw=.5,zorder=0,alpha=.6)
    for name,label,y,col,marker in labels:
        row=lookup.loc[name]
        lo=100*row.mean_substitution_lower_bound;hi=100*row.mean_substitution_upper_bound
        center=100*row.mean_substitution_deterministic
        plot.plot([lo,hi],[y,y],color=col,lw=2.1,solid_capstyle='round',zorder=2)
        plot.vlines([lo,hi],y-.9,y+.9,color=col,lw=.8,zorder=3)
        plot.scatter(center,y,s=29,c=col,marker=marker,zorder=4,edgecolors='white',linewidths=.5)
        txt(ax,13,y,label,size=7)
        txt(ax,158,y,f'{center:.1f}%',size=7.5,ha='right',color=col,bold=True)
    ax.add_patch(Rectangle((7,39),1.5,28,facecolor=BLUE,edgecolor='none'))
    ax.add_patch(Rectangle((7,11),1.5,18,facecolor=PURPLE,edgecolor='none'))
    txt(ax,13,67,'Released source scores fixed',size=6.5,color=BLUE,bold=True)
    txt(ax,13,29.7,'Retained-record scores reconstructed',size=6.5,color=PURPLE,bold=True)
    txt(ax,158,67.5,'ID mean',size=6.5,ha='right',color=GRAY)
    save(fig,2,height,output,data,['R17_B01_COMPONENT_ABLATION_SUMMARY.tsv'],{
        'a':{'kind':'explicit_synthetic_fixture','vectors':{'A':[1.0],'B':[1.0,.8]},
             'numerators':[1.0,1.2],'finite_denominators':[1.0,1.25],'fixed_denominator':hh,
             'finite_scores':[av[0],bv[0]],'fixed_scores':[av[1],bv[1]],
             'formula':'sum_i x_(i)/i^2 divided by h_n or fixed h_1000','replicates':'not biological; two deterministic vectors'},
        'b':{'source_rows':len(table),'contexts_per_contrast':23,'finite_budget':50,
             'family_ids':{'released_fixed':[x[0] for x in labels[:3]],'retained_reconstructed':[x[0] for x in labels[3:]]},
             'plotted_columns':['mean_substitution_lower_bound','mean_substitution_deterministic','mean_substitution_upper_bound'],
             'values_percent':[{'id':x[0],'lower':float(100*lookup.loc[x[0]].mean_substitution_lower_bound),
                               'ID':float(100*lookup.loc[x[0]].mean_substitution_deterministic),
                               'upper':float(100*lookup.loc[x[0]].mean_substitution_upper_bound)} for x in labels],
             'center':'mean ID realization','interval':'mean pairwise exact lower / upper sharp bounds; NOT CI',
             'test':'none','multiplicity':'not applicable','families_additive':False}})

def forest_header(ax,x,y,title):
    txt(ax,x,y,title,size=6.5,color=GRAY)

def figure3(data,output):
    height=165;fig,ax=canvas(height)
    heading(ax,6,158,'a','Five declared processing choices')
    heading(ax,96,158,'b','Aggregation depends on grouping')
    factors=read(data,'Figure_3_A_factor_effects.tsv')
    assert len(factors)==5 and set(factors.substitution_deterministic_count)=={368}
    factor_names={'O1':'Evidence unitization','O2':'Grouping basis','O3':'Score scale',
                  'O4':'Within-group aggregation','O5':'Across-group aggregation'}
    plot_a=fig.add_axes([44/170,112/height,37/170,35/height])
    plot_a.set(xlim=(0,85),ylim=(-.55,4.55),xticks=[0,20,40,60,80],yticks=[])
    plot_a.spines['left'].set_visible(False);plot_a.spines['bottom'].set_color(EDGE)
    plot_a.tick_params(labelsize=6.5,length=2.5)
    plot_a.set_xlabel('Top-50 substitution (%)',fontsize=6.5,labelpad=2)
    forest_header(ax,13,151,'Choice / 368 matched pairs')
    forest_header(ax,88,151,'ID (%)')
    factor_payload=[]
    for i,r in factors.iterrows():
        yy=4-i; y=112+(yy+.55)/5.1*35
        txt(ax,7,y,r.direct_toggle_factor,size=7,color=GRAY,bold=True)
        txt(ax,13,y,factor_names[r.direct_toggle_factor],size=6.5)
        lo=100*r.substitution_lower_bound_mean;hi=100*r.substitution_upper_bound_mean;center=100*r.substitution_deterministic_mean
        plot_a.hlines(yy,0,85,color=EDGE,lw=.45,alpha=.7)
        plot_a.hlines(yy,lo,hi,color=BLUE,lw=1.9,zorder=2)
        plot_a.vlines([lo,hi],yy-.1,yy+.1,color=BLUE,lw=.75,zorder=2)
        plot_a.scatter(center,yy,c=BLUE,s=25,edgecolor='white',lw=.5,zorder=3,clip_on=False)
        txt(ax,89,y,f'{center:.2f}' if center<.1 else f'{center:.1f}',size=7,ha='right',color=BLUE,bold=True)
        factor_payload.append({'factor':r.direct_toggle_factor,'label':factor_names[r.direct_toggle_factor],
                               'n':int(r.substitution_deterministic_count),'lower_percent':float(lo),'ID_percent':float(center),'upper_percent':float(hi)})
    cond=read(data,'Figure_3_BC_O2_conditioned.tsv')
    # O3 is a separate supplementary question already present in this full source;
    # Fig.3b preserves the originally designated O4 / O5 question (4 of 6 rows).
    rows=cond[cond.direct_toggle_factor.isin(['O4','O5'])].sort_values(['direct_toggle_factor','O2_stratum'])
    assert len(rows)==4 and set(rows.substitution_deterministic_count)=={184}
    plot_b=fig.add_axes([123/170,112/height,33/170,35/height])
    plot_b.set(xlim=(0,85),ylim=(-.6,3.6),xticks=[0,20,40,60,80],yticks=[])
    plot_b.spines['left'].set_visible(False);plot_b.spines['bottom'].set_color(EDGE)
    plot_b.tick_params(labelsize=6.5,length=2.5)
    plot_b.set_xlabel('Top-50 substitution (%)',fontsize=6.5,labelpad=2)
    forest_header(ax,103,151,'O2 stratum / 184 pairs')
    txt(ax,165,151,'ID (%)',size=6.5,ha='right',color=GRAY)
    conditional_payload=[]
    for i,(_,r) in enumerate(rows.iterrows()):
        yy=3-i;y=112+(yy+.6)/4.2*35; col=BLUE if r.O2_stratum==0 else PURPLE
        marker='o' if r.O2_stratum==0 else 's';group='source' if r.O2_stratum==0 else 'lineage'
        txt(ax,103,y,f'{r.direct_toggle_factor}  {group}',size=6.5,color=col)
        lo=100*r.substitution_lower_bound_mean;hi=100*r.substitution_upper_bound_mean;center=100*r.substitution_deterministic_mean
        plot_b.hlines(yy,0,85,color=EDGE,lw=.45,alpha=.7)
        plot_b.hlines(yy,lo,hi,color=col,lw=1.9,zorder=2)
        plot_b.vlines([lo,hi],yy-.1,yy+.1,color=col,lw=.75)
        plot_b.scatter(center,yy,c=col,s=25,marker=marker,edgecolor='white',lw=.5,zorder=3,clip_on=False)
        txt(ax,165,y,f'{center:.2f}' if center<2 else f'{center:.1f}',size=7,ha='right',color=col,bold=True)
        conditional_payload.append({'factor':r.direct_toggle_factor,'grouping':group,'n':184,
                                    'lower_percent':float(lo),'ID_percent':float(center),'upper_percent':float(hi)})
    txt(ax,6,99,'Points: mean ID realization. Capped rails: mean exact pairwise bounds, not confidence intervals.',size=6.5,color=GRAY)
    line(ax,6,95,164,95,lw=.7)

    heading(ax,6,89,'c','The same two records move the active aggregation stage')
    rec=read(data,'Table_S36_Grouping_Example_Records.tsv')
    ops=read(data,'Table_S37_Grouping_Example_Operators.tsv')
    receipt=json.loads((data/'FOCUSED_ANALYSIS_RECEIPT.json').read_text(encoding='utf-8'))
    case=receipt['selected_target']; control='ENSG00000011485'
    assert case=='ENSG00000018625'
    case_rec=rec[rec.targetId==case].sort_values('score',ascending=False)
    case_ops=ops[ops.targetId==case].sort_values('operator_code')
    control_ops=ops[ops.targetId==control]
    assert len(case_rec)==2 and len(case_ops)==8 and len(control_ops)==8
    assert np.ptp(control_ops.recomputed_score.to_numpy())<1e-14
    txt(ax,13,82,f'{case}  ·  urinary bladder cancer  ·  O1 = O3 = 0',size=7,bold=True)
    txt(ax,13,75,'Fixed EuropePMC records',size=6.5,color=GRAY)
    for yy,(_,r) in zip([65,52],case_rec.iterrows()):
        ax.add_patch(Circle((17,yy),4.4,facecolor=PALE,edgecolor=GRAY,lw=.7))
        txt(ax,17,yy,f'{r.score:.2f}',size=7,ha='center',bold=True)
        pub=r.canonical_key.split('=')[-1]
        txt(ax,24,yy,f'PMID {pub}',size=6.5)
    # Two native compact grouping glyphs make the operational difference visible.
    txt(ax,62,75,'Source partition',size=6.5,color=BLUE,ha='center',bold=True)
    txt(ax,62,46,'Lineage partition',size=6.5,color=PURPLE,ha='center',bold=True)
    ax.add_patch(FancyBboxPatch((48,57),28,12,boxstyle='round,pad=.1,rounding_size=1.4',
                              facecolor=SOURCE_FILL,edgecolor=BLUE,lw=.8))
    for x,s in [(55,'0.88'),(68,'0.04')]:
        ax.add_patch(Circle((x,63),3.8,facecolor='white',edgecolor=BLUE,lw=.7));txt(ax,x,63,s,size=6.5,color=BLUE,ha='center')
    for x,s in [(53,'0.88'),(70,'0.04')]:
        ax.add_patch(FancyBboxPatch((x-6,29),12,12,boxstyle='round,pad=.1,rounding_size=1.2',
                                  facecolor=LINEAGE_FILL,edgecolor=PURPLE,lw=.8))
        txt(ax,x,35,s,size=6.5,color=PURPLE,ha='center')
    # Both records enter a common collection rail before either partition.
    # Do not draw one row to source and the other row to lineage.
    line(ax,42,69,44,69,color=GRAY,lw=.7)
    line(ax,44,69,44,48,color=GRAY,lw=.7)
    line(ax,42,48,44,48,color=GRAY,lw=.7)
    arrow(ax,44,63,47,63,BLUE)
    line(ax,44,48,44,35,color=PURPLE,lw=.9)
    arrow(ax,44,35,46,35,PURPLE)
    txt(ax,62,52,'1 group → within matters',size=6.5,color=BLUE,ha='center')
    txt(ax,62,24,'2 singletons → across matters',size=6.5,color=PURPLE,ha='center')
    line(ax,78,63,82,63,color=BLUE,lw=.9)
    line(ax,82,63,82,52,color=BLUE,lw=.9)
    arrow(ax,82,52,86,52,BLUE)
    arrow(ax,78,35,85,35,PURPLE)
    # Full 2 × 4 matrix covers ALL eight source/lineage O4/O5 variants, not four selected scores.
    txt(ax,125,75,'All 8 scores: columns = within / across',size=6.5,ha='center',color=GRAY)
    columns=[('Maximum','Mean'),('Maximum','Finite'),('Finite','Mean'),('Finite','Finite')]
    tile_x=[88,107,126,145];tile_w=18
    for x,(within,across) in zip(tile_x,columns):
        txt(ax,x+tile_w/2,68,within,size=6.5,ha='center')
        txt(ax,x+tile_w/2,61,'/ '+across.lower(),size=6.5,ha='center')
    score_matrix=[]
    for yy,grouping,col,fill in [(52,'datasource',BLUE,SOURCE_FILL),(35,'lineage',PURPLE,LINEAGE_FILL)]:
        scores=[]
        for x,(within,across) in zip(tile_x,columns):
            within_key='maximum' if within=='Maximum' else 'finite_harmonic'
            across_key='arithmetic' if across=='Mean' else 'finite_harmonic'
            row=case_ops[(case_ops.grouping==grouping)&(case_ops.within==within_key)&(case_ops.across==across_key)]
            assert len(row)==1
            score=float(row.iloc[0].recomputed_score);scores.append(score)
            ax.add_patch(Rectangle((x,yy-5.1),tile_w,10.2,facecolor=fill,edgecolor='white',lw=.5))
            txt(ax,x+tile_w/2,yy,f'{score:.3f}',size=8,ha='center',color=col,bold=True)
        score_matrix.append(scores)
    txt(ax,125,24,'Groups are operational partitions, not biological replicates.',size=6.5,ha='center',color=GRAY)
    # Context for the mechanism: finite-universe group geometry, exactly same denominator.
    geometry=read(data,'Figure_3_D_group_geometry.tsv')
    geom=geometry[(geometry.stratum=='all_hard_negative')&(geometry.row_collapse=='canonical-unit')]
    assert len(geom)==2 and set(geom.target_context_pairs)=={107497}
    geometry_payload=[]
    txt(ax,6,17,'All groups singleton\n(canonical units)',size=6.5,bold=True)
    for x,group,label,col in [(49,'datasource','Source',BLUE),(103,'provenance','Lineage',PURPLE)]:
        r=geom[geom.grouping==group].iloc[0];value=float(r.fraction_pairs_with_all_groups_singleton)
        txt(ax,x,17,f'{label}  {100*value:.1f}%',size=6.5,color=col,bold=True)
        ax.add_patch(Rectangle((x,11.5),42,2.7,facecolor=PALE,edgecolor='none'))
        ax.add_patch(Rectangle((x,11.5),42*value,2.7,facecolor=col,edgecolor='none'))
        geometry_payload.append({'grouping':group,'denominator':107497,'numerator':int(r.pairs_with_all_groups_singleton),'fraction':value})
    txt(ax,164,17,'n = 107,497 pairs',size=6.5,ha='right',color=GRAY)
    txt(ax,6,5.5,'Singleton control: PPP5C, one row → 0.590 in all 8 variants. Full record keys / scores: Tables S36–S37.',size=6.5,color=GRAY)
    save(fig,3,height,output,data,['FOCUSED_ANALYSIS_RECEIPT.json','Figure_3_A_factor_effects.tsv','Figure_3_BC_O2_conditioned.tsv','Figure_3_D_group_geometry.tsv',
                                'Table_S36_Grouping_Example_Records.tsv','Table_S37_Grouping_Example_Operators.tsv'],{
        'a':{'source_rows':len(factors),'matched_pairs_per_factor':368,'values':factor_payload},
        'b':{'source_rows':len(cond),'plotted_rows':len(rows),'excluded_from_this_panel':
             {'rows':2,'reason':'O3 stratum rows are outside the pre-existing panel-b O4/O5 question, not omitted analytic results'},
             'values':conditional_payload,'same_x_scale_as_a':[0,85]},
        'c':{'observed_example':case,'example_selection_rule':receipt['selection_rule'],'case_source_rows':2,'case_operator_rows':8,'scores':score_matrix,
             'columns':columns,'rows':['source','lineage'],'fixed_O1_O3':[0,0],
             'all_retained_record_rows':len(rec),'control_source_rows':1,'control_operator_rows':8,
             'control_score':float(control_ops.recomputed_score.iloc[0]),'singleton_geometry':geometry_payload,
             'geometry_source_rows':len(geometry),'geometry_plotted_rows':2,'geometry_designated_stratum':'all_hard_negative/canonical-unit',
             'replication_unit':'finite target-context pairs and specification comparisons, not biological replication'},
        'statistics':{'center':'ID mean','interval':'mean pairwise exact lower/upper bounds, NOT CI',
                      'tests':'none','multiple_testing':'not applicable'}})

CAPTIONS={
 '2':'Fig. 2. Normalization reversal and two distinct B01 contrast families. (a) Synthetic vectors A = [1] and B = [1, 0.8] have rank-weighted numerators 1 and 1.2. Finite-length normalization gives scores 1 and 0.96, whereas the fixed h1000 denominator gives approximately 0.608 and 0.730, reversing their order. These are illustrative calculations, not a platform replay. (b) Five comparisons against B01 across 23 contexts. Blue contrasts retain released datasource scores; purple contrasts reconstruct datasource scores from retained records. The reconstruction substitutes do not isolate lower-level normalization or aggregation alone. Points show ID-realized substitution means and capped rails show mean pairwise sharp lower and upper bounds. The two families are non-additive, and the rails are not confidence intervals.',
 '3':'Fig. 3. Grouping determines where aggregation changes selected identities. (a) Mean substitution for five direct factor toggles, with 368 matched specification pairs per factor. (b) O4 and O5 contrasts stratified by source versus lineage grouping, with 184 pairs per stratum on the same scale as (a). Points show ID means; capped rails show mean pairwise sharp bounds, not confidence intervals. (c) The two retained EuropePMC rows for ENSG00000018625 in urinary bladder cancer are grouped together by source but separately by lineage. Among upward-crossing targets, a fixed rule required one datasource, at least two retained rows and at least two resolved singleton lineage groups with unequal raw scores; selection used fewest retained rows, then fewest canonical units, then ascending Ensembl ID. The matrix gives all eight O4/O5 scores with O1 = O3 = 0. Canonical-unit singleton fractions use 107,497 target-context pairs; partitions are operational, not biological replicates. PPP5C is a one-row control with an unchanged 0.590 score in all eight variants. Full keys and scores are in Tables S36–S37.'
}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',type=Path,default=HERE/'source_data')
    parser.add_argument('--output',type=Path,default=HERE/'rendered_figures')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    figure2(args.data,args.output);figure3(args.data,args.output)
    (args.output/'FIG2_3_QA.json').write_text(json.dumps({'QA':qa,'source_crosswalk':crosswalk},indent=2),encoding='utf-8')
    (args.output/'captions.json').write_text(json.dumps(CAPTIONS,indent=2,ensure_ascii=False),encoding='utf-8')
    print('Rendered Fig.2 and Fig.3 from exact source tables:',args.output)

if __name__=='__main__':
    main()
