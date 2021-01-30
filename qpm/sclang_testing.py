import tempfile
import datetime
import time
import json
import os.path
import re
import sclang_process as process
from sclang_process import ScLangProcess

def find_unit_test_quarks(include_gui=False):
	root = os.path.split(__file__)[0]
	paths = []

	unit_path = os.path.join(root, 'scscripts', 'UnitTesting')
	common_path = os.path.join(root, 'scscripts', 'CommonTests')
	gui_path = os.path.join(root, 'scscripts', 'CommonTestsGUI')

	if os.path.exists(unit_path):
		paths.append(unit_path)
	if os.path.exists(common_path):
		paths.append(common_path)
	if include_gui and os.path.exists(gui_path):
		paths.append(gui_path)

	return paths

def find_tests(sclang_path, print_output=False, includes=[], excludes=[]):
	code = process.load_script('list_tests')

	output, error = process.do_execute(sclang_path, code,
		includes=find_unit_test_quarks() + includes,
		excludes=excludes,
		print_output=print_output)

	if error:
		raise Exception(error)
	else:
		obj = json.loads(output)
		return obj

class SCTestRun:
	def __init__(self, sclang_path, test_plan=None, test_plan_path=None, excludes=[], includes=[], restarts=1, timeout=10*60):
		self.tests = dict()
		self.results = dict()
		self.sclang_path = sclang_path

		self.timeout = timeout
		self.restarts = restarts
		self.run_started = None
		self.process = None
		self.started = False
		self.duration = -1
		self.print_stdout = False
		self.includes = includes
		self.unit_test_quark_paths = find_unit_test_quarks()

		date = datetime.date.today()

		if test_plan_path:
			self.test_plan_path = test_plan_path
		else:
			fd, self.test_plan_path = tempfile.mkstemp('.json', 'SCTestRun_record_' + "_".join([str(date.day), str(date.month), str(date.year)]))

		if test_plan:
			self.test_plan = test_plan
			self.write_test_plan()
		else:
			self.read_test_plan()

	def add_test(self, suite, test):
		self.tests.setdefault(suite, list())
		self.tests[suite].append(test)

	def add_all_tests(self, suite):
		self.add_test(suite, "*")

	def set_results(self, results):
		self.results = results

	def update_results(self):
		results_string = ""
		with open(self.test_plan_path, 'r') as f:
			results_string = f.read()

		if results_string:
			try:
				results = json.loads(results_string)
				self.set_results(results)
			except Exception, e:
				# this is okay? might be in the middle of a write or something?
				print e
				pass
		else:
			raise Exception("Error reading test run record.")

	def write_test_plan(self):
		test_plan_string = json.dumps(self.test_plan, indent=2)
		with open(self.test_plan_path, "w") as f:
			f.write(test_plan_string)

	def read_test_plan(self):
		with open(self.test_plan_path, "r") as f:
			test_plan_string = f.read()
			test_plan = json.loads(test_plan_string, strict=False)
			if test_plan.get('tests'):
				self.test_plan = test_plan
			else:
				raise Exception('Test plan has no tests!')

	def run(self):
		start_time = time.time()
		if not(self.started) and not(self.all_tests_completed()):

			attempt = 0
			while not(self.all_tests_completed()) and self.restarts > 0:
				self.restarts -= 1
				self.started = True
				self.write_test_plan()
				code = process.load_script('test_runner')
				code = ('~testRecord = "%s";\n' % self.test_plan_path) + code

				self.process = ScLangProcess(self.sclang_path, print_output=self.print_stdout)
				self.process.exclude_extensions()

				for include in (self.includes + self.unit_test_quark_paths):
					self.process.include(include)

				self.process.launch()
				self.process.execute(code)
				self.process.wait_for(re.escape("******** DONE ********"), timeout=self.timeout, kill_on_error=False)

				self.read_test_plan()

			self.started = False

		end_time = time.time()
		self.duration = end_time - start_time

		return self.test_plan

	def all_tests_completed(self):
		for test in self.test_plan['tests']:
			completed = test.get('completed')
			if completed:
				pass
			else:
				return False
		return True


