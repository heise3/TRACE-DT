from pathlib import Path
import os,shutil
R=Path(__file__).resolve().parents[1];D=R/'deliverables';os.environ['MPLCONFIGDIR']=str(R/'working/mplcache')
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none'})
# Existing stress-test figure moves unchanged to 4.
old=R.parent/'TRACE_DT_GIGASCIENCE_REVISION/deliverables'
for ext,folder in [('pdf','upload'),('png','editable_figures'),('svg','editable_figures')]:shutil.copy2(old/f'{folder}/Figure_3.{ext}',D/f'{folder}/Figure_4.{ext}')
def save(fig,n):
 for ext,folder in [('pdf','upload'),('png','editable_figures'),('svg','editable_figures')]:fig.savefig(D/f'{folder}/Figure_{n}.{ext}',bbox_inches='tight',dpi=180)
 plt.close(fig)
a=pd.read_csv(R/'analysis/Table_S50_Official_Unrestricted_Cells.tsv',sep='\t');a=a[(a.score=='associationScore')&(a.min_rows==1)]
fig,(ax,bx)=plt.subplots(1,2,figsize=(8.2,5.0),gridspec_kw={'width_ratios':[1,1.05]})
for i,pool in enumerate(['unrestricted','restricted']):
 g=a[a.pool==pool];n=int(g.necessary_n.sum());t=int(g.selected_tie_n.sum());u=int(g.possible_unchosen_n.sum())
 ax.bar(i,n,color='#197C80');ax.bar(i,t,bottom=n,color='#4267A7');ax.bar(i,u,bottom=n+t,color='#C78C2D');ax.text(i,n+t+u+25,f'{n:,} + {t} + {u}',ha='center',fontsize=8);ax.text(i,550,f'{int(g.set_valued.sum())}/23\nambiguous',ha='center',color='white',weight='bold')
ax.set_xticks([0,1],['Unrestricted','Eligibility-restricted'],fontsize=8);ax.set_ylim(0,1420);ax.set_ylabel('Target–cancer memberships');ax.set_title('A  Membership under official scoring',loc='left',fontsize=10,weight='bold')
from matplotlib.patches import Patch
fig.legend(handles=[Patch(color='#197C80',label='Necessary'),Patch(color='#4267A7',label='Selected tie choices'),Patch(color='#C78C2D',label='Possible, unselected')],loc='lower center',ncols=3,frameon=False,fontsize=8)
p=pd.read_csv(R/'analysis/Table_S52_Official_Pool_Comparisons.tsv',sep='\t')
for dx,pool,col in [(-.16,'unrestricted','#197C80'),(.16,'restricted','#8E4A78')]:
 vals=[p[p.comparison==f'{pool}_associationScore_min1_vs_min{n}'].realized_substitution.mean()*100 for n in [2,3]]
 bx.bar([x+dx for x in [0,1]],vals,width=.29,color=col,label=pool.capitalize())
 for x,v in zip([0,1],vals):bx.text(x+dx,v+1,f'{v:.1f}%',ha='center',fontsize=8)
bx.set_xticks([0,1],['At least 2 rows','At least 3 rows']);bx.set_ylim(0,44);bx.set_ylabel('Mean realized substitution (%)');bx.set_title('B  Record-filter replacement cost',loc='left',fontsize=10,weight='bold');bx.legend(frameon=False,fontsize=7,loc='upper left')
fig.subplots_adjust(left=.1,right=.98,bottom=.2,top=.9,wspace=.45);save(fig,2)
d=pd.read_csv(R/'analysis/Table_S53_DISEASES_Real_View_Comparisons.tsv',sep='\t');d['label']=d.context_id+'  '+d.specification_a.str.replace('EXPERIMENTS','E').str.replace('INTEGRATED','I').str.replace('TEXTMINING','T')+'–'+d.specification_b.str.replace('EXPERIMENTS','E').str.replace('INTEGRATED','I').str.replace('TEXTMINING','T');d=d.sort_values(['substitution_deterministic','context_id'])
fig,ax=plt.subplots(figsize=(7.4,10.2))
for i,r in enumerate(d.itertuples()):
 ax.plot([r.substitution_lower_bound*100,r.substitution_upper_bound*100],[i,i],color='#C78C2D' if r.bound_width>0 else '#77818B',lw=3)
 ax.scatter(r.substitution_deterministic*100,i,s=13,color='#197C80',zorder=3)
ax.set_yticks(range(len(d)),d.label,fontsize=7);ax.invert_yaxis();ax.set_xlim(27,103);ax.set_xlabel('Exchanged identities (%)');ax.set_title('DISEASES: all 50 comparisons of resource-provided views',loc='left',fontsize=11,weight='bold');ax.grid(axis='x',alpha=.16)
fig.text(.33,.02,'E: experiments  ·  I: integrated  ·  T: text mining\nPoints: identifier realization; lines: exact attainable bounds\n7/50 pairs have non-zero-width bounds (maximum 4 percentage points).',fontsize=8)
fig.subplots_adjust(left=.33,bottom=.11,right=.97,top=.95);save(fig,3)
