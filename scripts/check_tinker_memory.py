"""Exercise Tinker's Project memory tab against the real Brain CLI offscreen.

Uses only a disposable source/store. Select checkout mode with a Tinker root, or
installed mode to require both packages and the Brain command inside sys.prefix.
"""
import json,os,sys,tempfile,time,subprocess
from pathlib import Path
import argparse
parser=argparse.ArgumentParser()
mode=parser.add_mutually_exclusive_group(required=True)
mode.add_argument('--tinker-root',type=Path)
mode.add_argument('--installed',action='store_true')
parser.add_argument('--screenshot',type=Path,required=True)
parser.add_argument('--verification',action='store_true',help='Exercise explicit observer receipt display and readback')
args=parser.parse_args()
brain_root=Path(__file__).resolve().parents[1]
if not args.installed:
 sys.path.insert(0,str(brain_root))
 sys.path.insert(0,str(args.tinker_root.resolve()))
from brain.core import Brain,initialize,digest
from brain.state import ProjectState
from PySide6.QtWidgets import QApplication
from ui.project_memory import ProjectMemoryPanel
from services.coding.project import ProjectController
from ui.project import ProjectPanel
import brain.core,ui.project_memory,PySide6
imports={name:str(Path(module.__file__).resolve()) for name,module in
         [('brain',brain.core),('tinker_memory',ui.project_memory)]}
if args.installed:
 for path in imports.values():
  if not Path(path).is_relative_to(Path(sys.prefix).resolve()):
   raise RuntimeError('Installed check imported code outside the isolated environment')
app=QApplication([])
def pump(fn):
 stop=time.monotonic()+15
 while not fn() and time.monotonic()<stop:app.processEvents();time.sleep(.01)
 assert fn()
with tempfile.TemporaryDirectory() as d:
 root=Path(d);source=root/'source';source.mkdir();(source/'decision.md').write_text('# Decision\nUse local retained evidence because source files may be unavailable.\n')
 (source/'support.md').write_text('# Decision\nKeep local retained evidence because original sources may disappear.\n')
 (source/'pyproject.toml').write_text('[project]\nname = "example-tool"\n')
 for n in range(1,6):
  (source/f'mission-{n}.md').write_text(f'# Mission\nPlanning marker {n}: keep this project objective available for review.\n')
 if args.verification:
  subprocess.run(['git','init','-q',str(source)],check=True)
  subprocess.run(['git','-C',str(source),'add','.'],check=True)
  subprocess.run(['git','-C',str(source),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                  'commit','-qm','fixture'],check=True)
 initialize(root/'store');b=Brain(root/'store');pid=b.ingest(source)['project_id']
 state=ProjectState(b,pid)
 items={i['claims'][0]['path']:i for i in state.view()['items'].values()}
 survivor,absorbed=items['decision.md'],items['support.md']
 state.consolidate(survivor['id'],absorbed['id'],'Both support retaining local evidence.')
 b.relate(pid,absorbed['claims'][0]['record_id'],survivor['claims'][0]['record_id'],
          'supersedes','Later review treats these as successive decisions; grouping needs review.')
 if args.verification:
  receipt=root/'verification'
  subprocess.run([sys.executable,str(brain_root/'scripts/run_verification.py'),'--cwd',str(source),
      '--output',str(receipt),'--scope','Synthetic process emits verification marker',
      '--environment','Disposable local fixture','--',sys.executable,'-c','print("VERIFICATION_MARKER")'],
      check=True,capture_output=True)
  event=state.verify(survivor['id'],receipt,'Fixture observer',
                    'Observed marker only; no application behavior claimed',observed=True)
 if args.installed:
  launcher=Path(sys.prefix)/'bin'/'brain'
  if not launcher.is_file():raise RuntimeError('Installed Brain command is missing')
 else:
  launcher=root/'brain';launcher.write_text('#!'+sys.executable+'\nimport sys\nsys.path.insert(0,'+repr(str(brain_root))+')\nfrom brain.__main__ import main\nraise SystemExit(main())\n');launcher.chmod(0o700)
 before={str(p):digest(p.read_bytes()) for p in b.root.rglob('*') if p.is_file()}
 c=ProjectController();view=ProjectPanel(c);panel=view.memory
 view.resize(1000,1000);view.show();view.tabs.setCurrentWidget(panel)
 panel.executable.setText(str(launcher));panel.store.setText(str(b.root));panel.load.click()
 pump(lambda:panel._process is None)
 assert panel.projects.currentData()==pid,panel.status.text()
 panel.show_briefing.click();pump(lambda:panel._process is None)
 assert 'local retained evidence' in panel.briefing.toPlainText(),panel.status.text()
 assert 'Planning marker 5' not in panel.briefing.toPlainText()
 panel.detail.setCurrentIndex(1)
 assert not panel.briefing.toPlainText() and panel._process is None
 panel.show_briefing.click();pump(lambda:panel._process is None)
 assert 'Planning marker 5' in panel.briefing.toPlainText()
 assert 'Observed configuration' in panel.briefing.toPlainText()
 assert 'Consolidation needs review' in panel.briefing.toPlainText()
 assert 'Combined support from 1' in panel.briefing.toPlainText()
 paths={panel.references.item(i).data(256).get('path') for i in range(panel.references.count())}
 assert {'decision.md','support.md','pyproject.toml'} <= paths
 row=next(i for i in range(panel.references.count()) if panel.references.item(i).data(256).get('path')=='support.md')
 panel.references.setCurrentRow(row);panel.open_evidence.click();pump(lambda:panel._process is None)
 assert 'local retained evidence' in panel.evidence.toPlainText(),panel.status.text()
 if args.verification:
  assert 'historical — review required' in panel.briefing.toPlainText()
  assert 'does not verify the whole item' in panel.briefing.toPlainText()
  row=next(i for i in range(panel.references.count()) if panel.references.item(i).data(256).get('kind')=='receipt')
  panel.references.setCurrentRow(row);panel.open_evidence.click();pump(lambda:panel._process is None)
  assert 'VERIFICATION_MARKER' in panel.evidence.toPlainText(),panel.status.text()
  assert event['verification_bundle']['receipt_sha256'] in panel.evidence.toPlainText()
 assert before=={str(p):digest(p.read_bytes()) for p in b.root.rglob('*') if p.is_file()}
 assert not c.selection and not c.attached
 # Hide sensitive temporary paths from the presentation artifact, without starting reads.
 panel.executable.blockSignals(True);panel.store.blockSignals(True)
 panel.executable.setText('/path/to/brain');panel.store.setText('/path/to/Brain-store')
 panel.executable.blockSignals(False);panel.store.blockSignals(False)
 panel.briefing.find('Scoped verification' if args.verification else 'Consolidation needs review');panel.briefing.ensureCursorVisible()
 app.processEvents();view.grab().save(str(args.screenshot.resolve()))
 c.revoke();assert not panel.briefing.toPlainText() and not panel.evidence.toPlainText()
 assert panel.detail.currentData()==3
 panel.shutdown();c.shutdown();view.close();app.processEvents()
 print(json.dumps({'scoped_verification_receipt_checked':args.verification,'expanded_view_reveals_omitted_context':True,'detail_change_requires_reload':True,'revoke_restores_brief':True,'consolidation_conflict_visible':True,'grouped_support_evidence_loaded':True,'configuration_section_visible':True,'real_cli_project_list':True,'briefing_loaded':True,'retained_evidence_loaded':True,'store_byte_unchanged':True,'model_context_unchanged':True,'owner_revoke_cleared':True,'qt':PySide6.__version__,'mode':'offscreen','installed_packages':args.installed,'imports':imports},indent=2))
