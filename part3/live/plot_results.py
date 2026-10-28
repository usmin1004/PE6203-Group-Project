"""Render the measured attack subset with Pygal (pip install pygal)."""
import json
from pathlib import Path
import pygal
from pygal.style import Style
root=Path(__file__).resolve().parent
data=json.loads((root/'summary.json').read_text())
style=Style(background='white',plot_background='white',foreground='#213547',foreground_strong='#102235',
    foreground_subtle='#d7e0e8',colors=('#2067bb','#cf6844','#6d7783'),font_family='Arial',
    title_font_size=23,label_font_size=16,major_label_font_size=16,legend_font_size=16,value_font_size=14)
ks=[0,1,3,5]
chart=pygal.XY(width=1050,height=560,style=style,show_dots=True,dots_size=5,stroke_style={'width':3},
    range=(0,100),y_labels=[0,20,40,60,80,100],x_title='Review budget k',y_title='Safe completion proxy (%)',
    legend_at_bottom=True,show_minor_x_labels=True,truncate_legend=-1)
chart.title='AgentDojo attack subset: 6 pairs per setting, one run'
chart.x_labels=ks
for policy,label in [('checklist_policy','Checklist'),('full_escalate_policy','Full escalate'),('full_approve_policy','Full approve (reused)')]:
    rows={r['k']:r for r in data if r['policy']==policy and r['mode']=='attack' and r['complete']}
    values=[100*rows[0 if policy=='full_approve_policy' else k]['safe_completion_proxy'] for k in ks]
    chart.add(label,list(zip(ks,values)))
chart.render_to_file(str(root/'attack_tcr_curve.svg'))
bar=pygal.Bar(width=1050,height=540,style=style,range=(0,16),y_labels=[0,4,8,12,16],x_title='Review budget k',
    y_title='Actual reviewer calls (total)',legend_at_bottom=True,truncate_legend=-1)
bar.title='HITL totals on the same attack subset'
bar.x_labels=[str(k) for k in ks]
for policy,label in [('checklist_policy','Checklist: all tasks'),('full_escalate_policy','Full escalate: all tasks')]:
    rows={r['k']:r for r in data if r['policy']==policy and r['mode']=='attack' and r['complete']}
    bar.add(label,[rows[k]['hitl_all'] for k in ks])
rows={r['k']:r for r in data if r['policy']=='full_escalate_policy' and r['mode']=='attack' and r['complete']}
bar.add('Full escalate: safe-success tasks',[rows[k]['hitl_safe_success'] for k in ks])
bar.render_to_file(str(root/'attack_hitl_totals.svg'))
