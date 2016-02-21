from Database                import Database
from Utils.WorkloadGenerator import WorkloadGenerator
from Storage.File            import StorageFile
from Storage.Page            import Page
from Storage.SlottedPage     import SlottedPage

# Path to the folder containing csvs (on ugrad cluster)
dataDir = '/home/cs416/datasets/tpch-sf0.01/'

# Pick a page class, page size, scale factor, and workload mode:
StorageFile.defaultPageClass = Page   # Contiguous Page
pageSize = 4096                       # 4Kb
scaleFactor = 0.5                     # Half of the data
workloadMode = 1                      # Sequential Reads

# Run! Throughput will be printed afterwards.
# Note that the reported throughput ignores the time
# spent loading the dataset.
wg = WorkloadGenerator()
wg.runWorkload(dataDir, scaleFactor, pageSize, workloadMode)
