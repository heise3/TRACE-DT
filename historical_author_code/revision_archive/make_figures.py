import os
from pathlib import Path
R=Path(__file__).resolve().parents[1]
os.environ['MPLCONFIGDIR']=str(R/'working/mplcache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import pandas as pd
OUT=R/'deliverables/upload';OUT.mkdir(parents=True,exist_ok=True)
EDIT=R/'deliverables/editable_figures';EDIT.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none','savefig.facecolor':'white'})
teal='#197C80';blue='#4267A7';gold='#C78C2D';gray='#6B7280'
def save(fig,n):
 fig.savefig(OUT/f'Figure_{n}.pdf',bbox_inches='tight')
 fig.savefig(EDIT/f'Figure_{n}.svg',bbox_inches='tight')
 fig.savefig(EDIT/f'Figure_{n}.png',dpi=180,bbox_inches='tight')
 plt.close(fig)
fig=plt.figure(figsize=(7.1,4.7)); ax=fig.add_axes([.03,.05,.94,.9]);ax.axis('off')
for y,title,txt,col in [(.86,'INPUT','Context · candidate · specification · finite score',blue),(.66,'DECLARE THE DECISION','Capacity B · candidate pool · tie definition',gray),(.12,'COMPARE LISTS','Exact attainable bounds on exchanged identities',teal)]:
 ax.add_patch(FancyBboxPatch((.05,y-.055),.9,.12,boxstyle='round,pad=0.012',edgecolor=col,facecolor='white',lw=1.4))
 ax.text(.5,y+.025,title,ha='center',va='center',fontsize=10,color=col,weight='bold')
 ax.text(.5,y-.02,txt,ha='center',va='center',fontsize=9)
ax.annotate('',xy=(.5,.73),xytext=(.5,.79),arrowprops={'arrowstyle':'->','color':gray})
ax.annotate('',xy=(.5,.51),xytext=(.5,.59),arrowprops={'arrowstyle':'->','color':gray})
ax.text(.5,.53,'WORKED EXAMPLE  ·  Capacity 2',ha='center',weight='bold')
ax.text(.5,.46,'Scores: a = 0.9; b = c = d = 0.5',ha='center')
for x,title,txt,col in [(.18,'Necessary','a',teal),(.5,'Selected by tie rule','b',blue),(.82,'Possible, unselected','c, d',gold)]:
 ax.text(x,.36,title,ha='center',color=col,fontsize=9,weight='bold')
 ax.text(x,.29,txt,ha='center',color=col,fontsize=16)
ax.text(.5,.22,'All admissible lists: {a,b}, {a,c}, {a,d}',ha='center',fontsize=9)
save(fig,1)
d=pd.read_csv(R/'analysis/Table_S46_Official_Score_Sensitivity.tsv',sep='\t');a=d[d.min_rows.eq(1)].sort_values(['set_valued','possible_n'],ascending=[False,False])
fig,(ax,bx)=plt.subplots(1,2,figsize=(8.1,7.4),gridspec_kw={'width_ratios':[1.6,1]})
y=list(range(len(a)))
ax.barh(y,a.necessary_n,color=teal,label='Necessary')
ax.barh(y,50-a.necessary_n,left=a.necessary_n,color=blue,label='Selected tie choices')
ax.barh(y,a.possible_n-50,left=50,color=gold,label='Possible, unselected')
ax.axvline(50,color=gray,lw=.8,ls='--');ax.set_yticks(y,a.context_name,fontsize=7.3);ax.invert_yaxis();ax.set_xlabel('Target–cancer memberships');ax.set_title('A  Released scoring in the study pool',loc='left',fontsize=10,weight='bold')
ax.legend(loc='lower right',fontsize=7,frameon=False)
cats=['Necessary\n1,080','Tie chosen\n70','Possible\nunchosen\n95']; vals=[253/1080*100,100,100]
bx.bar(range(3),vals,color=[teal,blue,gold]);bx.set_ylim(0,114);bx.set_xticks(range(3),cats,fontsize=7.3);bx.set_ylabel('One retained positive row (%)');bx.set_title('B  Evidence composition',loc='left',fontsize=10,weight='bold')
for i,v in enumerate(vals):bx.text(i,v+2,f'{v:.1f}%',ha='center',fontsize=9)
fig.subplots_adjust(left=.30,right=.98,bottom=.12,top=.93,wspace=.55)
save(fig,2)
fig,(ax,bx)=plt.subplots(1,2,figsize=(8.2,3.6),gridspec_kw={'width_ratios':[1,1.15]})
labels=['Necessary in all 32','ID in all 32; not always necessary','Possible in all 32; not always ID'];vals=[90,43,399]
ax.barh(range(3),vals,color=[teal,blue,gold]);ax.set_yticks(range(3),labels,fontsize=8);ax.invert_yaxis();ax.set_xlim(0,455);ax.set_xlabel('Target–cancer pairs');ax.set_title('A  Selection across all 32 specifications',loc='left',fontsize=9,weight='bold')
for i,v in enumerate(vals):ax.text(v+5,i,str(v),va='center',fontsize=9)
bx.plot([29.2279102384,52.7224754558],[0,0],color=gray,lw=3);bx.scatter([29.2279102384,43.858345021,52.7224754558],[0,0,0],c=[teal,blue,gold],s=65,zorder=3)
for x,label,dy in [(29.2279102384,'29.2%\nLower bound',.18),(43.858345021,'43.9%\nIdentifier list',-.34),(52.7224754558,'52.7%\nUpper bound',.18)]:bx.text(x,dy,label,ha='center',va='center',fontsize=8)
bx.set_xlim(23,59);bx.set_ylim(-.6,.6);bx.set_yticks([]);bx.spines['left'].set_visible(False);bx.set_xlabel('Exchanged identities (%)');bx.set_title('B  Mean pairwise substitution',loc='left',fontsize=9,weight='bold')
fig.subplots_adjust(left=.29,right=.98,wspace=.50,bottom=.2,top=.87)
save(fig,3)
