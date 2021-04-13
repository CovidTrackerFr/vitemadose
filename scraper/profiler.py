import time
import statistics
import numpy
from terminaltables import SingleTable
from multiprocessing import Queue, Process
from multiprocessing.pool import Pool
from functools import wraps

class ProfiledPool(Pool):
    def __init__(self, processes):
        self.profiler = Profiling()
        super().__init__(processes=processes, **self.profiler.pool_args())

    def __enter__(self):
        self.profiler.__enter__()
        super().__enter__()
        return self

    def __exit__(self, *args, **kwargs):
        super().__exit__(*args, **kwargs)
        self.profiler.__exit__(*args, **kwargs)

class Profiling:
    _current_queue = None
    def pool_args(self):
        return {
            "initializer": Profiling.init_child,
            "initargs": (self.collecting_q,)
        }

    def __init__(self):
        self.result_q = Queue()
        self.collecting_q = Queue()

    def __enter__(self):
      self.reader = Process(target=Profiling.read_profiling_result, args=(self.collecting_q, self.result_q,))
      self.reader.start()

    def __exit__(self, exc_type, exc_value, traceback):
      self.collecting_q.put(None)
      self.collecting_q.close()
      self.summary = self.result_q.get()
      self.result_q.close()
      self.reader.join()

    def measure(section):
        def decorator(fn):
            @wraps(fn)
            def with_profiling(*args, **kwargs):
                q = Profiling._current_queue
                if q is None:
                    return fn(*args, **kwargs)
                start_time = time.time()
                error = None
                try:
                  ret = fn(*args, **kwargs)
                except Exception as e:
                  error = e
                elapsed_time = time.time() - start_time
                q.put_nowait((section, elapsed_time))
                if error is None:
                  return ret
                else:
                  raise error

            return with_profiling

        return decorator

    def print_summary (self, keys=None):
      summary = self.summary
      keys = keys if keys is not None else sorted(summary.keys())
      datatable = [['Section', 'Count', 'Min', 'Avg', '50%', '80%', '95%', 'Max']]
      for section in keys:
        stats = summary[section]
        datatable.append([
          section,
          stats['count'],
          stats['min'],
          stats['avg'],
          stats['median'],
          stats['p80'],
          stats['p95'],
          stats['max'],
        ])

      table = SingleTable(datatable)
      print (table.table)

    def read_profiling_result(collecting_q, result_q):
        sink = ProfilerSink()
        for section, duration in iter(collecting_q.get, None):
          sink.append(section, duration)

        result_q.put(sink.summary())

    def init_child(queue):
      Profiling._current_queue = queue

class ProfilerSink:
    def __init__(self):
      self.sections_duration = {}

    def append(self, section, duration):
        if section not in self.sections_duration:
            self.sections_duration[section] = []
        self.sections_duration[section].append(duration)

    def summary(self):
      summary = {}
      for section, durations in self.sections_duration.items():
        p80, p95 = numpy.percentile(durations, [80, 95])
        summary[section] = {
            'count': len(durations),
            'min': round(min(durations) * 1000),
            'max': round(max(durations) * 1000),
            'avg': round(statistics.fmean(durations) * 1000),
            'median': round(statistics.median(durations) * 1000),
            'p80': round(p80 * 1000),
            'p95': round(p95 * 1000),
        }

      return summary
