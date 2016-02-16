import functools, math, struct
from struct import Struct
from io     import BytesIO

from Catalog.Identifiers import PageId, FileId, TupleId
from Catalog.Schema import DBSchema
from Storage.Page import PageHeader, Page

from bitstring import BitArray

###########################################################
# DESIGN QUESTION 1: should this inherit from PageHeader?
# If so, what methods can we reuse from the parent?
#
class SlottedPageHeader(PageHeader):
  """
  A slotted page header implementation. This should store a slot bitmap
  implemented as a memoryview on the byte buffer backing the page
  associated with this header. Additionally this header object stores
  the number of slots in the array, as well as the index of the next
  available slot.

  The binary representation of this header object is: (numSlots, nextSlot, slotBuffer)

  >>> import io
  >>> buffer = io.BytesIO(bytes(4096))
  >>> ph     = SlottedPageHeader(buffer=buffer.getbuffer(), tupleSize=16)
  >>> ph2    = SlottedPageHeader.unpack(buffer.getbuffer())
  >>> ph == ph2
  True

  ## Dirty bit tests
  >>> ph.isDirty()
  False
  >>> ph.setDirty(True)
  >>> ph.isDirty()
  True
  >>> ph.setDirty(False)
  >>> ph.isDirty()
  False

  ## Tuple count tests
  >>> ph.hasFreeTuple()
  True

  # First tuple allocated should be at the first slot.
  # Notice this is a slot index, not an offset as with contiguous pages.
  >>> ph.nextFreeTuple() == 0
  True

  >>> ph.numTuples()
  1

  >>> tuplesToTest = 10
  >>> [ph.nextFreeTuple() for i in range(0, tuplesToTest)]
  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
  
  >>> ph.numTuples() == tuplesToTest+1
  True

  >>> ph.hasFreeTuple()
  True

  # Check space utilization
  >>> ph.usedSpace() == (tuplesToTest+1)*ph.tupleSize
  True

  >>> ph.freeSpace() == 4096 - (ph.headerSize() + ((tuplesToTest+1) * ph.tupleSize))
  True

  >>> remainingTuples = int(ph.freeSpace() / ph.tupleSize)

  # Fill the page.
  >>> [ph.nextFreeTuple() for i in range(0, remainingTuples)] # doctest:+ELLIPSIS
  [11, 12, ...]

  >>> ph.hasFreeTuple()
  False

  # No value is returned when trying to exceed the page capacity.
  >>> ph.nextFreeTuple() == None
  True
  
  >>> ph.freeSpace() < ph.tupleSize
  True
  """


  def __init__(self, **kwargs):
    buffer=kwargs.get("buffer", None)
    self.flags           = kwargs.get("flags", b'\x00')
    self.pageCapacity = kwargs.get("pageCapacity", len(buffer))
    self.tupleSize = kwargs.get("tupleSize", None)
    self.bitmap=kwargs.get("bitmap", None)

    if buffer == None:
      raise ValueError("No backing buffer supplied for SlottedPageHeader")

    if self.bitmap == None:
      headerSizeWithoutBitmap = struct.Struct("chhh").size
      tupleCapacity = math.floor((8*(self.pageCapacity-headerSizeWithoutBitmap))/(1+(8*self.tupleSize)))
      bString = '0b' + ('0' * tupleCapacity)
      self.bitmap = BitArray(bString)
   
    self.binrepr   = struct.Struct("cHHH" + str(math.ceil(tupleCapacity/8)) + 's')
    self.size      = self.binrepr.size
    self.freeSpaceOffset = self.size
   
    buffer[0:self.size] = self.pack()

 #   super().__init__(buffer=buffer, flags=kwargs.get("flags", b'\x00'), self.tupleSize)
  
  def __eq__(self, other):
    # raise NotImplementedError
    return (    self.flags == other.flags
            and self.tupleSize == other.tupleSize
            and self.pageCapacity == other.pageCapacity
            and self.freeSpaceOffset == other.freeSpaceOffset 
            and self.bitmap == other.bitmap)

  def __hash__(self):
    raise NotImplementedError

  def headerSize(self):
    return self.size

  # Flag operations.
  def flag(self, mask):
    return (ord(self.flags) & mask) > 0

  def setFlag(self, mask, set):
    if set:
      self.flags = bytes([ord(self.flags) | mask])
    else:
      self.flags = bytes([ord(self.flags) & ~mask])

  # Dirty bit accessors
  def isDirty(self):
    return self.flag(PageHeader.dirtyMask)

  def setDirty(self, dirty):
    self.setFlag(PageHeader.dirtyMask, dirty)

  def numTuples(self):
    return self.bitmap.count(1)

  # Returns the space available in the page associated with this header.
  def freeSpace(self):
    space = self.bitmap.count(0)

    text_file = open("last.txt", "a")
    text_file.write(str(space) + ", ")
    text_file.close()
    return space * self.tupleSize

  # Returns the space used in the page associated with this header.
  def usedSpace(self):
    return self.numTuples() * self.tupleSize
    # raise NotImplementedError


  # Slot operations.
  def offsetOfSlot(self, slot):
    raise NotImplementedError

  def hasSlot(self, slotIndex):
    raise NotImplementedError

  def getSlot(self, slotIndex):
    raise NotImplementedError

  def setSlot(self, slotIndex, slot):
    raise NotImplementedError

  def resetSlot(self, slotIndex):
    raise NotImplementedError

  def freeSlots(self):
    raise NotImplementedError

  def usedSlots(self):
    raise NotImplementedError

  # Tuple allocation operations.
  
  # Returns whether the page has any free space for a tuple.
  def hasFreeTuple(self):
    # raise NotImplementedError
    findTuple = self.bitmap.find('0b0', 0, self.pageCapacity)
    if findTuple == ():
      return False
    else:
      return True

  # Returns the tupleIndex of the next free tuple.
  # This should also "allocate" the tuple, such that any subsequent call
  # does not yield the same tupleIndex.
  def nextFreeTuple(self):
    nextTuple = self.bitmap.find('0b0', 0, self.pageCapacity)

    if nextTuple == ():
      return None

    self.bitmap[nextTuple[0]] = '0b1'
    return nextTuple[0]
    # raise NotImplementedError

  def nextTupleRange(self):
    raise NotImplementedError

  # Create a binary representation of a slotted page header.
  # The binary representation should include the slot contents.
  def pack(self):
    self.bitmap.append('0b' + ('0'*(8 - len(self.bitmap)%8)))

    return self.binrepr.pack(
              self.flags, self.tupleSize,
              self.freeSpaceOffset, self.pageCapacity, self.bitmap.bytes)
    # raise NotImplementedError

  # Create a slotted page header instance from a binary representation held in the given buffer.
  @classmethod
  def unpack(cls, buffer):

    headerSizeWithoutBitmap = struct.Struct("chhh").size
    tupleCapacity = math.floor((8*(self.pageCapacity-headerSizeWithoutBitmap))/(1+(8*self.tupleSize)))
    bString = '0b' + ('0' * tupleCapacity)
    bitmap = BitArray(bString)
   
    binrepr   = struct.Struct("cHHH" + str(math.ceil(tupleCapacity/8)) + 's')
    values = binrepr.unpack_from(buffer)

    for i in range(0,tupleCapacity):
      bitmap[i] = values[4][i]

    if len(values) == 5:
      return cls(buffer=buffer, flags=values[0], tupleSize=values[1],
                 freeSpaceOffset=values[2], pageCapacity=values[3], 
                 bitmap=bitmap)
    # raise NotImplementedError



######################################################
# DESIGN QUESTION 2: should this inherit from Page?
# If so, what methods can we reuse from the parent?
#
class SlottedPage(Page):
  """
  A slotted page implementation.

  Slotted pages use the SlottedPageHeader class for its headers, which
  maintains a set of slots to indicate valid tuples in the page.

  A slotted page interprets the tupleIndex field in a TupleId object as
  a slot index.

  >>> from Catalog.Identifiers import FileId, PageId, TupleId
  >>> from Catalog.Schema      import DBSchema

  # Test harness setup.
  >>> schema = DBSchema('employee', [('id', 'int'), ('age', 'int')])
  >>> pId    = PageId(FileId(1), 100)
  >>> p      = SlottedPage(pageId=pId, buffer=bytes(4096), schema=schema)

  # Validate header initialization
  >>> p.header.numTuples() == 0 and p.header.usedSpace() == 0
  True

  # Create and insert a tuple
  >>> e1 = schema.instantiate(1,25)
  >>> tId = p.insertTuple(schema.pack(e1))

  >>> tId.tupleIndex
  0

  # Retrieve the previous tuple
  >>> e2 = schema.unpack(p.getTuple(tId))
  >>> e2
  employee(id=1, age=25)

  # Update the tuple.
  >>> e1 = schema.instantiate(1,28)
  >>> p.putTuple(tId, schema.pack(e1))

  # Retrieve the update
  >>> e3 = schema.unpack(p.getTuple(tId))
  >>> e3
  employee(id=1, age=28)

  # Compare tuples
  >>> e1 == e3
  True

  >>> e2 == e3
  False

  # Check number of tuples in page
  >>> p.header.numTuples() == 1
  True

  # Add some more tuples
  >>> for tup in [schema.pack(schema.instantiate(i, 2*i+20)) for i in range(10)]:
  ...    _ = p.insertTuple(tup)
  ...

  # Check number of tuples in page
  >>> p.header.numTuples()
  11

  # Test iterator
  >>> [schema.unpack(tup).age for tup in p]
  [28, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38]

  # Test clearing of first tuple
  >>> tId = TupleId(p.pageId, 0)
  >>> sizeBeforeClear = p.header.usedSpace()  
  >>> p.clearTuple(tId)
  
  >>> schema.unpack(p.getTuple(tId))
  employee(id=0, age=0)

  >>> p.header.usedSpace() == sizeBeforeClear
  True

  # Check that clearTuple only affects a tuple's contents, not its presence.
  >>> [schema.unpack(tup).age for tup in p]
  [0, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38]

  # Test removal of first tuple
  >>> sizeBeforeRemove = p.header.usedSpace()
  >>> p.deleteTuple(tId)

  >>> [schema.unpack(tup).age for tup in p]
  [20, 22, 24, 26, 28, 30, 32, 34, 36, 38]
  
  # Check that the page's slots have tracked the deletion.
  >>> p.header.usedSpace() == (sizeBeforeRemove - p.header.tupleSize)
  True

  """

  headerClass = SlottedPageHeader

  # Slotted page constructor.
  #
  # REIMPLEMENT this as desired.
  #
  # Constructors keyword arguments:
  # buffer       : a byte string of initial page contents.
  # pageId       : a PageId instance identifying this page.
  # header       : a SlottedPageHeader instance.
  # schema       : the schema for tuples to be stored in the page.
  # Also, any keyword arguments needed to construct a SlottedPageHeader.
  def __init__(self, **kwargs):
    buffer = kwargs.get("buffer", None)
    if buffer:
      BytesIO.__init__(self, buffer)
      self.pageId = kwargs.get("pageId", None)
      header      = kwargs.get("header", None)
      schema      = kwargs.get("schema", None)

      if self.pageId and header:
        self.header = header
      elif self.pageId:
        self.header = self.initializeHeader(**kwargs)
      else:
        raise ValueError("No page identifier provided to page constructor.")
      
      # raise NotImplementedError

    else:
      raise ValueError("No backing buffer provided to page constructor.")


  # Header constructor override for directory pages.
  def initializeHeader(self, **kwargs):
    schema = kwargs.get("schema", None)
    if schema:
      return SlottedPageHeader(buffer=self.getbuffer(), tupleSize=schema.size)
    else:
      raise ValueError("No schema provided when constructing a slotted page.")

  # Tuple iterator.
  def __iter__(self):
    iterTuple = self.header.bitmap.find('0b1')
    if iterTuple == ():
      self.iterTupleIdx = 0
    else:
      self.iterTupleIdx = iterTuple[0]
    return self
    # raise NotImplementedError

  def __next__(self):

    t = self.getTuple(TupleId(self.pageId, self.iterTupleIdx))
    
    if t:
      nextTuple = self.header.bitmap.find('0b1', self.iterTupleIdx + 1)
      if nextTuple == ():
        self.iterTupleIdx = -1        
      else:
        self.iterTupleIdx = nextTuple[0]
      return t
    else:
      raise StopIteration
    # raise NotImplementedError

  # Tuple accessor methods

  # Returns a byte string representing a packed tuple for the given tuple id.
  def getTuple(self, tupleId):

    if tupleId.tupleIndex < 0:
      return None

    tupleIndex = tupleId.tupleIndex

    view = self.getbuffer()
    offset = tupleIndex * self.header.tupleSize + self.header.size
    tupleBytes = view[offset: offset + self.header.tupleSize]

    if not self.header.bitmap[tupleIndex]:
      return None

    return tupleBytes

    # return Page.getTuple(self, tupleId)

    # raise NotImplementedError

  # Updates the (packed) tuple at the given tuple id.
  def putTuple(self, tupleId, tupleData):
    super().putTuple(tupleId, tupleData)
    # raise NotImplementedError

  # Adds a packed tuple to the page. Returns the tuple id of the newly added tuple.
  def insertTuple(self, tupleData):
    bitTuple = self.header.bitmap.find('0b0', 0, self.header.pageCapacity)

    if bitTuple == ():
      return None

    tupleID = TupleId(self.pageId, bitTuple[0])

    view = self.getbuffer()
    view[self.header.size + bitTuple[0] * self.header.tupleSize : self.header.size + bitTuple[0] * self.header.tupleSize + self.header.tupleSize] = tupleData
    self.header.bitmap[bitTuple[0]:bitTuple[0] + 1] = 1

    return tupleID


    # raise NotImplementedError

  # Zeroes out the contents of the tuple at the given tuple id.
  def clearTuple(self, tupleId):
    super().clearTuple(tupleId)
    # raise NotImplementedError

  # Removes the tuple at the given tuple id, shifting subsequent tuples.
  def deleteTuple(self, tupleId):
    self.header.bitmap[tupleId.tupleIndex * self.header.tupleSize] = '0b0'
    # raise NotImplementedError

  # Returns a binary representation of this page.
  # This should refresh the binary representation of the page header contained
  # within the page by packing the header in place.
  def pack(self):
    raise NotImplementedError

  # Creates a Page instance from the binary representation held in the buffer.
  # The pageId of the newly constructed Page instance is given as an argument.
  @classmethod
  def unpack(cls, pageId, buffer):
    raise NotImplementedError


if __name__ == "__main__":
    import doctest
    doctest.testmod()
